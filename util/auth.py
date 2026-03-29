import json
import logging
import os
from typing import Tuple

from cryptography.fernet import Fernet
from sqlalchemy import text

from db.database import get_private_session, initialize_private_database
from util import sde_store
from util.esi_rate_limiter import esi_get

logger = logging.getLogger(__name__)

PUBLIC_DATA_FOLDER = os.getenv("PUBLIC_DATA_PATH", "_publicData")
PRIVATE_DATA_FOLDER = os.getenv("EVE_PRIVATE_DATABASE_FOLDER", "_privateData")

CONFIG_FILE_PATH = os.getenv("CONFIG_FILE", "config.yaml")
CLIENT_CRED_FILE = os.path.join(PUBLIC_DATA_FOLDER, "client_cred")
KEY_FILE = os.path.join(PUBLIC_DATA_FOLDER, "key")

# Scopes are sourced from the generated manifest — do not edit by hand.
# Run `python -m util.esi_codegen` to regenerate when the ESI spec changes.
from esi.generated.manifest import ALL_SCOPES as _ALL_SCOPES

REQUIRED_SCOPES = " ".join(sorted(_ALL_SCOPES))


def ensure_folder(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def lookup_info(character_id: int) -> list:
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
        sde_store.ensure_public_database()
        initialize_private_database(owner_id)

    def save_tokens(
        self,
        character_id: int,
        access_token: str,
        refresh_token: str,
        expires_at: float,
        scopes: str,
    ) -> None:
        sde_store.link_public_user(self.owner_id, character_id)

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
