"""Shared helpers for all background ESI worker modules."""
import os
import time

from config import PRIVATE_DATA_FOLDER
from esi.auth import get_token


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
    import logging
    logger = logging.getLogger(__name__)
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
