"""collectors/alliance — Alliance-tier ESI collectors (write to per-alliance DuckDB)."""

from __future__ import annotations

import logging

import core.db.public as db
from core.auth.tokens import pick_token, fresh_token

logger = logging.getLogger(__name__)


def get_alliance_token_map() -> dict[int, tuple[int, str]]:
    """Return {alliance_id: (char_id, access_token)} — one token per alliance.

    Picks the first character whose auth_users row has that alliance_id.
    Tokens are freshened before returning; failed refreshes are skipped.
    """
    con = db.connect()
    try:
        rows = con.execute(
            "SELECT DISTINCT alliance_id, owner_id FROM auth_users WHERE alliance_id IS NOT NULL"
        ).fetchall()
    finally:
        con.close()

    result: dict[int, tuple[int, str]] = {}
    seen_alliances: set[int] = set()
    for alliance_id, owner_id in rows:
        if alliance_id in seen_alliances:
            continue
        try:
            char_id, token_data = pick_token(owner_id)
            _, fresh_data = fresh_token(owner_id, char_id, token_data)
            result[alliance_id] = (char_id, fresh_data["access_token"])
            seen_alliances.add(alliance_id)
        except Exception:
            logger.warning("[alliance] could not get token for owner %s", owner_id)
    return result
