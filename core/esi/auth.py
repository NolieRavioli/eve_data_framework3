"""ESI OAuth management, credential storage, and token lifecycle helpers.

Merges the former ``esi/auth.py`` with the token helpers from ``workers/__init__.py``
(resolve_default_owner_id, pick_token, fresh_token).
"""

import json
import logging
import os
import time
from typing import Iterable, Optional, Tuple

import requests

from cryptography.fernet import Fernet
from sqlalchemy import text

from core.db.privateDB import get_private_session, initialize_private_database
from core.db.models import Character

logger = logging.getLogger(__name__)

PUBLIC_DATA_FOLDER = os.getenv("PUBLIC_DATA_FOLDER", "_publicData")
PRIVATE_DATA_FOLDER = os.getenv("EVE_PRIVATE_DATABASE_FOLDER", "_privateData")

CONFIG_FILE_PATH = os.getenv("CONFIG_FILE", "config.yaml")
CLIENT_CRED_FILE = os.path.join(PUBLIC_DATA_FOLDER, "client_cred")
KEY_FILE = os.path.join(PUBLIC_DATA_FOLDER, "key")

# Scopes are sourced from the generated manifest — do not edit by hand.
# Run `python -m util.esi_codegen` to regenerate when the ESI spec changes.
from core.esi.generated.manifest import ALL_SCOPES as _ALL_SCOPES

REQUIRED_SCOPES = " ".join(sorted(_ALL_SCOPES))


def ensure_folder(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def lookup_info(character_id: int) -> list:
    from core.queue.esi_req import esi_get
    url = f"https://esi.evetech.net/latest/characters/{character_id}/?datasource=tranquility"
    response = esi_get(url)
    response.raise_for_status()
    payload = response.json()
    return [
        payload["name"],
        payload["corporation_id"],
        payload["birthday"],
        payload.get("security_status"),
        payload.get("alliance_id"),
    ]


class CredentialManager:
    logger = logging.getLogger("CredentialManager")

    @staticmethod
    def load_credentials() -> Tuple[str, str, str, str]:
        ensure_folder(PUBLIC_DATA_FOLDER)
        if not os.path.exists(KEY_FILE):
            with open(KEY_FILE, "wb") as handle:
                handle.write(Fernet.generate_key())

        with open(KEY_FILE, "rb") as handle:
            fernet = Fernet(handle.read())

        if not os.path.exists(CLIENT_CRED_FILE):
            logger.info("No credentials found. Setup required.")
            return CredentialManager.setup_credentials(fernet)

        with open(CLIENT_CRED_FILE, "rb") as handle:
            creds = json.loads(fernet.decrypt(handle.read()).decode())
        return (
            creds["client_id"],
            creds["client_secret"],
            creds["redirect_uri"],
            creds["scopes"],
        )

    @staticmethod
    def setup_credentials(fernet: Fernet) -> Tuple[str, str, str, str]:
        import webbrowser

        webbrowser.open("https://developers.eveonline.com/applications")
        client_id = input("Client ID: ").strip()
        client_secret = input("Client Secret: ").strip()
        redirect_uri = input("Callback URL: ").strip()
        raw_scopes = input("Scopes (JSON list format): ").strip()

        try:
            scopes_list = json.loads(raw_scopes)
            scopes = " ".join(scopes_list)
        except Exception as exc:
            raise ValueError("Scopes must be a valid JSON list!") from exc

        creds = {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "scopes": scopes,
        }

        with open(CLIENT_CRED_FILE, "wb") as handle:
            handle.write(fernet.encrypt(json.dumps(creds).encode()))
        logger.info("Credentials saved at %s", CLIENT_CRED_FILE)
        return client_id, client_secret, redirect_uri, scopes


class TokenDBManager:
    logger = logging.getLogger("TokenDBManager")

    def __init__(self, owner_id: int):
        self.owner_id = owner_id
        from core.db import publicDB
        publicDB.ensure_public_database()
        initialize_private_database(owner_id)

    def save_tokens(
        self,
        character_id: int,
        access_token: str,
        refresh_token: str,
        expires_at: float,
        scopes: str,
    ) -> None:
        from core.db import publicDB
        publicDB.link_public_user(self.owner_id, character_id)

        name, corporation_id, birthday, security_status, alliance_id = lookup_info(character_id)

        session_priv = get_private_session(self.owner_id)
        try:
            session_priv.execute(
                text(
                    "INSERT OR REPLACE INTO characters "
                    "(character_id, name, corporation_id, birthday, "
                    "security_status, alliance_id, access_token, "
                    "refresh_token, expires_at, scopes) "
                    "VALUES (:cid, :nm, :corp, :bday, :sec, :alli, :at, :rt, :exp, :sc)"
                ),
                {
                    "cid": character_id,
                    "nm": name,
                    "corp": corporation_id,
                    "bday": birthday,
                    "sec": security_status,
                    "alli": alliance_id,
                    "at": access_token,
                    "rt": refresh_token,
                    "exp": expires_at,
                    "sc": scopes,
                },
            )
            session_priv.commit()
        finally:
            session_priv.close()


# ---------------------------------------------------------------------------
# Token retrieval and refresh helpers
# ---------------------------------------------------------------------------

TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"


def get_token(owner_id: int, character_ids: Optional[Iterable[int]] = None) -> dict:
    """Return ``{character_id: token_dict}`` for all characters of an owner.

    Expired tokens are refreshed automatically and persisted before returning.
    """
    token_map = {}
    selected_ids = (
        {int(value) for value in character_ids} if character_ids is not None else None
    )
    now = time.time()
    session = get_private_session(owner_id)
    token_db = TokenDBManager(owner_id)
    try:
        tokens = session.query(Character).all()
        for token in tokens:
            if selected_ids is not None and token.character_id not in selected_ids:
                continue
            if token.expires_at and token.expires_at < now:
                logger.info("Token expired for %s, refreshing...", token.character_id)
                try:
                    refreshed = refresh_token(token.refresh_token)
                    token.access_token = refreshed["access_token"]
                    token.refresh_token = refreshed["refresh_token"]
                    token.expires_at = refreshed.get(
                        "expires_at", now + refreshed.get("expires_in", 1200)
                    )
                    token.scopes = refreshed.get("scope", token.scopes)
                    session.commit()
                    token_db.save_tokens(
                        character_id=token.character_id,
                        access_token=token.access_token,
                        refresh_token=token.refresh_token,
                        expires_at=token.expires_at,
                        scopes=token.scopes,
                    )
                except Exception as exc:
                    logger.error(
                        "[TokenManager] Failed to refresh token for %s: %s",
                        token.character_id,
                        exc,
                    )
                    continue
            token_map[token.character_id] = {
                "corporation_id": token.corporation_id,
                "alliance_id": token.alliance_id,
                "security_status": token.security_status,
                "access_token": token.access_token,
                "refresh_token": token.refresh_token,
                "expires_at": token.expires_at,
                "scopes": token.scopes,
            }
    finally:
        session.close()
    return token_map


def refresh_token(refresh_token_str: str) -> dict:
    """Exchange a refresh token for a new access token via EVE SSO."""
    client_id, client_secret, _, _ = CredentialManager.load_credentials()
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token_str,
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    r.raise_for_status()
    token_data = r.json()
    token_data["expires_at"] = time.time() + token_data.get("expires_in", 1200)
    return token_data


# ---------------------------------------------------------------------------
# Token convenience helpers (absorbed from workers/__init__.py)
# ---------------------------------------------------------------------------

def resolve_default_owner_id() -> int | None:
    """Return the numerically smallest owner_id found in the private data folder, or None."""
    if not os.path.isdir(PRIVATE_DATA_FOLDER):
        return None
    owner_ids = [
        int(name)
        for name in os.listdir(PRIVATE_DATA_FOLDER)
        if name.isdigit() and os.path.isdir(os.path.join(PRIVATE_DATA_FOLDER, name))
    ]
    return min(owner_ids) if owner_ids else None


def pick_token(owner_id: int) -> tuple[int, dict]:
    """Load the first available token for owner_id; refresh if expired."""
    tokens = get_token(owner_id)
    char_id, token_data = sorted(tokens.items())[0]
    if token_data.get("expires_at") and token_data["expires_at"] < time.time():
        logger.info("[TokenRefresh] Token expired for %s, refreshing...", char_id)
        tokens = get_token(owner_id)
        char_id, token_data = sorted(tokens.items())[0]
    return char_id, token_data


def fresh_token(owner_id: int, char_id: int, token_data: dict) -> tuple[int, dict]:
    """Return the current token if still valid; re-pick only when within 30s of expiry."""
    expires_at = token_data.get("expires_at")
    if expires_at is not None and expires_at > time.time() + 30:
        return char_id, token_data
    return pick_token(owner_id)

