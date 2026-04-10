"""analysis/alliance_enrichment.py — Fill alliance details and member corp lists.

Reads all alliance_id values from the public ``alliances`` table (seeded by
``collectors/public_data/alliances.py``), fetches GET /alliances/{id} for
bare rows (name IS NULL), and GET /alliances/{id}/corporations for member corp IDs.
Both endpoints are public (no auth required).
"""

from __future__ import annotations

import logging

import core.db.public as db
from core.db.writer import db_write
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def run_alliance_enrichment() -> None:
    """Enrich bare alliance rows with details and member corp lists."""
    con = db.connect()
    try:
        rows = con.execute("""
            SELECT alliance_id FROM alliances
            WHERE name IS NULL OR member_corp_ids IS NULL
        """).fetchall()
    finally:
        con.close()

    if not rows:
        logger.info("[alliance_enrichment] All alliances already enriched.")
        return

    logger.info("[alliance_enrichment] Enriching %s alliances", len(rows))
    updated = 0
    for (alliance_id,) in rows:
        try:
            resp = esi_get(f"{ESI_BASE}/alliances/{alliance_id}/")
            if not resp.ok:
                continue
            d = resp.json()

            corps_resp = esi_get(f"{ESI_BASE}/alliances/{alliance_id}/corporations/")
            member_ids = corps_resp.json() if corps_resp.ok else None

            con = db.connect()
            try:
                con.execute("""
                    UPDATE alliances SET
                        name                    = COALESCE(name, ?),
                        ticker                  = COALESCE(ticker, ?),
                        creator_id              = COALESCE(creator_id, ?),
                        creator_corporation_id  = COALESCE(creator_corporation_id, ?),
                        executor_corporation_id = ?,
                        faction_id              = ?,
                        date_founded            = COALESCE(date_founded, ?),
                        member_corp_ids         = ?,
                        fetched_at              = now()
                    WHERE alliance_id = ?
                """, [d.get("name"), d.get("ticker"), d.get("creator_id"),
                      d.get("creator_corporation_id"), d.get("executor_corporation_id"),
                      d.get("faction_id"), d.get("date_founded"),
                      member_ids, alliance_id])
            finally:
                con.close()
            updated += 1
        except Exception:
            logger.exception("[alliance_enrichment] Failed for alliance %s", alliance_id)

    logger.info("[alliance_enrichment] Done — %s/%s alliances enriched", updated, len(rows))
