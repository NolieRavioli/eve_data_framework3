"""collectors/corp — corporation-level ESI data collectors.

Each module owns DDL for its tables in the per-corp DuckDB file:
    `_privateData/<corporation_id>/<corporation_id>.duckdb`

Public helpers:
    get_corp_token_map() -> dict[int, tuple[int, str]]
        Returns {corporation_id: (character_id, access_token)} for every
        corporation associated with a known authenticated owner.
"""

from __future__ import annotations

import logging

import core.db.public as db
from core.auth.tokens import pick_token, fresh_token

logger = logging.getLogger(__name__)


def get_corp_token_map() -> dict[int, tuple[int, str]]:
    """Returns {corporation_id: (character_id, access_token)} for every corp.

    One token per corp — first available owner that has access.
    """
    con = db.connect()
    try:
        rows = con.execute("""
            SELECT DISTINCT corporation_id, owner_id
            FROM auth_users WHERE corporation_id IS NOT NULL
        """).fetchall()
    finally:
        con.close()

    result: dict[int, tuple[int, str]] = {}
    for corp_id, owner_id in rows:
        if corp_id in result:
            continue  # already have a token for this corp
        try:
            char_id, token_data = pick_token(owner_id)
            char_id, token_data = fresh_token(owner_id, char_id, token_data)
            result[corp_id] = (char_id, token_data["access_token"])
        except Exception:
            logger.warning("[corp] could not get token for corp=%s owner=%s", corp_id, owner_id)
    return result


__all__ = ["get_corp_token_map"]
