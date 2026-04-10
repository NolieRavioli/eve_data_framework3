"""analysis/killmail_enrichment.py — Fetch full killmail details from ESI.

Reads killmail_id + killmail_hash from personal ``character_killmails`` and
corp ``corp_killmails`` tables; fetches GET /killmails/{id}/{hash} (public endpoint,
no auth); writes the full JSON blob into the ``details_json`` column.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from core.io.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def _get_all_entity_ids() -> list[int]:
    private_root = Path(os.environ.get("EVE_PRIVATE_DATABASE_FOLDER", "_privateData"))
    return [int(d.name) for d in private_root.iterdir()
            if d.is_dir() and d.name.isdigit()]


def _enrich_killmails(entity_id: int, table: str) -> None:
    con = connect_entity(entity_id)
    try:
        try:
            rows = con.execute(
                f"SELECT killmail_id, killmail_hash FROM {table} WHERE details_json IS NULL"
            ).fetchall()
        except Exception:
            return
        for (km_id, km_hash) in rows:
            resp = esi_get(f"{ESI_BASE}/killmails/{km_id}/{km_hash}/")
            if resp.ok:
                con.execute(
                    f"UPDATE {table} SET details_json = ? WHERE killmail_id = ?",
                    [json.dumps(resp.json()), km_id]
                )
            elif resp.status_code == 404:
                con.execute(
                    f"UPDATE {table} SET details_json = 'null' WHERE killmail_id = ?",
                    [km_id]
                )
    finally:
        con.close()


def run_killmail_enrichment() -> None:
    """Enrich all unenriched killmails for personal and corp entities."""
    entity_ids = _get_all_entity_ids()
    for entity_id in entity_ids:
        try:
            _enrich_killmails(entity_id, "character_killmails")
        except Exception:
            logger.exception("[killmail_enrichment] char km failed for entity %s", entity_id)
        try:
            _enrich_killmails(entity_id, "corp_killmails")
        except Exception:
            logger.exception("[killmail_enrichment] corp km failed for entity %s", entity_id)
    logger.info("[killmail_enrichment] Done")
