"""analysis/affiliation_sync.py — Batch POST /characters/affiliation to enrich character rows.

Reads all unique character_ids from every personal DuckDB ``characters`` table,
batches them in groups of 1000, and POSTs to the public ESI affiliation endpoint
(no auth required).  Writes back corporation_id, alliance_id, faction_id to each
character's row and also updates ``auth_users`` corporation_id / alliance_id.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from core.io.entity_db import connect_entity
from core.io.writer import db_write
from core.esi import esi_post

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"
_BATCH = 1000

AFFILIATION_URL = f"{ESI_BASE}/characters/affiliation/"


def _get_all_owner_ids() -> list[int]:
    private_root = Path(os.environ.get("EVE_PRIVATE_DATABASE_FOLDER", "_privateData"))
    return [int(d.name) for d in private_root.iterdir()
            if d.is_dir() and d.name.isdigit()]


def run_affiliation_sync() -> None:
    """Batch-resolve corporation/alliance/faction for every character in the personal DBs."""
    owner_ids = _get_all_owner_ids()
    if not owner_ids:
        logger.info("[affiliation_sync] No owner DBs found.")
        return

    # Collect (owner_id, character_id) pairs from each DuckDB
    pairs: list[tuple[int, int]] = []
    for owner_id in owner_ids:
        try:
            con = connect_entity(owner_id)
            try:
                rows = con.execute("SELECT DISTINCT character_id FROM characters").fetchall()
                pairs.extend((owner_id, r[0]) for r in rows)
            finally:
                con.close()
        except Exception:
            logger.exception("[affiliation_sync] Failed reading chars for owner %s", owner_id)

    if not pairs:
        logger.info("[affiliation_sync] No characters found.")
        return

    logger.info("[affiliation_sync] Syncing affiliation for %s characters", len(pairs))

    # Batch ESI affiliation lookups
    char_ids = list({p[1] for p in pairs})
    results: dict[int, dict] = {}
    for i in range(0, len(char_ids), _BATCH):
        batch = char_ids[i:i + _BATCH]
        resp = esi_post(AFFILIATION_URL, json=batch)
        if resp.ok:
            for item in resp.json():
                results[item["character_id"]] = item
        else:
            logger.warning("[affiliation_sync] ESI %s for batch %s", resp.status_code, i)

    if not results:
        return

    # Write back to each owner's DuckDB characters table
    owner_chars: dict[int, list[int]] = {}
    for owner_id, char_id in pairs:
        owner_chars.setdefault(owner_id, []).append(char_id)

    for owner_id, char_ids_for_owner in owner_chars.items():
        try:
            con = connect_entity(owner_id)
            try:
                for char_id in char_ids_for_owner:
                    aff = results.get(char_id)
                    if not aff:
                        continue
                    con.execute("""
                        UPDATE characters SET
                            corporation_id = ?,
                            alliance_id = ?,
                            faction_id = ?
                        WHERE character_id = ?
                    """, [aff.get("corporation_id"), aff.get("alliance_id"),
                          aff.get("faction_id"), char_id])
            finally:
                con.close()
        except Exception:
            logger.exception("[affiliation_sync] Failed writing to owner %s", owner_id)

    # Also update auth_users in the public DuckDB
    import core.io.public as db
    pub_con = db.connect()
    try:
        for char_id, aff in results.items():
            pub_con.execute("""
                UPDATE auth_users SET
                    corporation_id = ?,
                    alliance_id = ?
                WHERE character_id = ?
            """, [aff.get("corporation_id"), aff.get("alliance_id"), char_id])
    finally:
        pub_con.close()

    logger.info("[affiliation_sync] Done — %s characters updated", len(results))
