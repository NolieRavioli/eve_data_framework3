"""Client credential management — Fernet encryption of OAuth client_id/secret.

Pure crypto + file I/O — no Flask dependency.
"""

import json
import logging
import os
from typing import Tuple

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

PUBLIC_DATA_FOLDER = os.getenv("PUBLIC_DATA_FOLDER", "_publicData")
CLIENT_CRED_FILE = os.path.join(PUBLIC_DATA_FOLDER, "client_cred")
KEY_FILE = os.path.join(PUBLIC_DATA_FOLDER, "key")


def _ensure_folder(path: str) -> None:
    os.makedirs(path, exist_ok=True)


class CredentialManager:
    logger = logging.getLogger("CredentialManager")

    @staticmethod
    def load_credentials() -> Tuple[str, str, str, str]:
        _ensure_folder(PUBLIC_DATA_FOLDER)
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
    def save_credentials(client_id: str, client_secret: str, redirect_uri: str, scopes: str) -> None:
        """Save OAuth credentials to disk (called from the web setup wizard)."""
        _ensure_folder(PUBLIC_DATA_FOLDER)
        if not os.path.exists(KEY_FILE):
            with open(KEY_FILE, "wb") as handle:
                handle.write(Fernet.generate_key())
        with open(KEY_FILE, "rb") as handle:
            fernet = Fernet(handle.read())
        creds = {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "scopes": scopes,
        }
        with open(CLIENT_CRED_FILE, "wb") as handle:
            handle.write(fernet.encrypt(json.dumps(creds).encode()))
        logger.info("Credentials saved at %s", CLIENT_CRED_FILE)

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
