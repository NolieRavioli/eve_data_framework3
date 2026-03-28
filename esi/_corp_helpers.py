# esi/_corp_helpers.py
"""Shared helpers for corp ESI fetchers."""
from datetime import datetime
from typing import Optional


def _dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def get_corp_id_for_char(owner_id: int, char_id: int) -> Optional[int]:
    """Look up cached corporation_id from the characters table."""
    from db.database import get_private_session
    from db.models import Character
    db = get_private_session(owner_id)
    char = db.get(Character, char_id)
    corp_id = char.corporation_id if char else None
    db.close()
    return corp_id


def fetch_paginated(url: str, access_token: str, esi_get_fn) -> list:
    """Generic paginated ESI GET helper."""
    results, page = [], 1
    headers = {"Authorization": f"Bearer {access_token}"}
    while True:
        resp = esi_get_fn(url, headers=headers, params={"page": page})
        resp.raise_for_status()
        data = resp.json()
        results.extend(data)
        if page >= int(resp.headers.get("x-pages", 1)):
            break
        page += 1
    return results
