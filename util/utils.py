# utils.py

import os
import time
import logging
import sqlite3
import requests
import yaml
from db.database import get_private_session
from db.models import Character
from util.auth import TokenDBManager, CredentialManager

logger = logging.getLogger(__name__)

CONFIG_PATH = "config.yaml"
PRIVATE_DATA_FOLDER = os.getenv("EVE_PRIVATE_DATABASE_FOLDER", "_privateData/")
ESI_BASE = "https://esi.evetech.net/latest"
HEADERS = {"Accept": "application/json"}
DATASOURCE = {"datasource": "tranquility"}

TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"

# ──────── Config Loader ─────────────────────────────────────────────────────────

def load_config(config_path: str = CONFIG_PATH) -> dict:
    """
    Loads Environment Variables from a config.yaml into os.environ.
    Returns the full config dict.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    env_vars = cfg.get("Environment Variables", {})
    if not isinstance(env_vars, dict):
        raise ValueError("Expected 'Environment Variables' to be a dictionary in config.yaml")

    for key, value in env_vars.items():
        if key not in os.environ:
            if isinstance(value, list):
                os.environ[key] = ",".join(str(v) for v in value)
            else:
                os.environ[key] = str(value)

    logger.info(f"Loaded {len(env_vars)} environment variables from {config_path}")
    return cfg

# ──────── Token / Character Utilities ───────────────────────────────────────────

def get_token(owner_id: int) -> dict:
    """
    Return { character_id: TokenRow } dict for all characters linked to an owner.
    If any tokens are expired, refresh them automatically and SAVE them.
    """
    token_map = {}
    now = time.time()
    session = get_private_session(owner_id)
    token_db = TokenDBManager(owner_id)
    try:
        tokens = session.query(Character).all()
        for token in tokens:
            if token.expires_at and token.expires_at < now:
                logger.info(f"Token expired for {token.character_id}, refreshing...")
                try:
                    refreshed = refresh_token(token.refresh_token)
                    # Update the SQLAlchemy model
                    token.access_token = refreshed["access_token"]
                    token.refresh_token = refreshed["refresh_token"]
                    token.expires_at = refreshed.get("expires_at", now + refreshed.get("expires_in", 1200))
                    token.scopes = refreshed.get("scope", token.scopes)
                    # Save to SQLAlchemy (private toon db)
                    session.commit()
                    # Save to raw SQLite (token db)
                    token_db.save_tokens(
                        character_id=token.character_id,
                        access_token=token.access_token,
                        refresh_token=token.refresh_token,
                        expires_at=token.expires_at,
                        scopes=token.scopes
                    )
                except Exception as e:
                    logger.error(f"[TokenManager] Failed to refresh token for {token.character_id}: {e}")
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

def refresh_token(refresh_token: str) -> dict:
    client_id, client_secret, _, _ = CredentialManager.load_credentials()
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret
        }
    )
    r.raise_for_status()
    token_data = r.json()
    token_data["expires_at"] = time.time() + token_data.get("expires_in", 1200)
    return token_data

# ──────── ESI Utilities ──────────────────────────────────────────────────────────

def safe_request(method, url, **kwargs):
    retries = 3
    backoff = 2
    for attempt in range(retries):
        try:
            resp = requests.request(method, url, timeout=30, **kwargs)
            if resp.status_code == 403:
                logger.warning(f"Access forbidden (403) for {url}. Skipping retries.")
                resp.raise_for_status()
            resp.raise_for_status()
            return resp
        except requests.HTTPError as e:
            if e.response.status_code == 403:
                raise
            logger.warning(f"Request failed ({attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(backoff)
                backoff *= 2
            else:
                raise

def get_portrait(character_id: int):
    """ get esi portraits """
    url = f"{ESI_BASE}/characters/{character_id}/portrait/"
    resp = requests.get(url, headers=HEADERS, params=DATASOURCE)
    resp.raise_for_status()
    return resp.json()


def batched(iterable, batch_size):
    """Yield successive batches of a list."""
    for i in range(0, len(iterable), batch_size):
        yield iterable[i:i + batch_size]

def get_all_region_ids():
    """Get all region IDs from ESI."""
    url = f"{ESI_BASE}/universe/regions/"
    resp = requests.get(url, headers=HEADERS, params=DATASOURCE)
    resp.raise_for_status()
    return resp.json()

def is_structure(structure_id: int) -> bool:
    """Check if a given ID is a structure via ESI."""
    url = f"{ESI_BASE}/universe/structures/{structure_id}/"
    r = requests.get(url, headers=HEADERS, params=DATASOURCE)
    return r

def resolve_names_to_ids(names: list[str]) -> dict:
    """Bulk convert system or structure names to IDs using ESI."""
    if not names:
        return {}

    response = requests.post(
        f"{ESI_BASE}/universe/ids/",
        headers=HEADERS,
        params={"datasource": "tranquility", "language": os.getenv("LANGUAGE", "en")},
        json=names,
    )
    response.raise_for_status()

    systems = response.json().get("systems", [])
    return {entry["name"]: entry["id"] for entry in systems}

