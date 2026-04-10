"""analysis/war_enrichment.py — Fetch full war details and recent killmails.

Reads unenriched ``wars`` rows (allies_json IS NULL) from the public DuckDB
and calls GET /wars/{war_id} + GET /wars/{war_id}/killmails (public endpoints).
"""

from __future__ import annotations

import json
import logging

import core.io.public as db
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def run_war_enrichment() -> None:
    """Enrich bare war rows with full details and killmails."""
    con = db.connect()
    try:
        rows = con.execute(
            "SELECT war_id FROM wars WHERE allies_json IS NULL LIMIT 500"
        ).fetchall()
    finally:
        con.close()

    if not rows:
        logger.info("[war_enrichment] All wars already enriched.")
        return

    logger.info("[war_enrichment] Enriching %s wars", len(rows))
    enriched = 0
    for (war_id,) in rows:
        try:
            resp = esi_get(f"{ESI_BASE}/wars/{war_id}/")
            if resp.status_code == 422:
                # War doesn't exist anymore
                continue
            if not resp.ok:
                continue
            d = resp.json()

            km_resp = esi_get(f"{ESI_BASE}/wars/{war_id}/killmails/")
            km_json = json.dumps(km_resp.json()) if km_resp.ok else None

            allies_json = json.dumps(d.get("allies", [])) if "allies" in d else "[]"
            aggressor = d.get("aggressor", {})
            defender = d.get("defender", {})

            con = db.connect()
            try:
                con.execute("""
                    UPDATE wars SET
                        aggressor_id    = ?,
                        aggressor_type  = ?,
                        defender_id     = ?,
                        defender_type   = ?,
                        declared        = ?,
                        started         = ?,
                        finished        = ?,
                        retracted       = ?,
                        mutual          = ?,
                        open_for_allies = ?,
                        allies_json     = ?,
                        killmails_json  = ?,
                        fetched_at      = now()
                    WHERE war_id = ?
                """, [aggressor.get("id"), aggressor.get("entity_type"),
                      defender.get("id"), defender.get("entity_type"),
                      d.get("declared"), d.get("started"), d.get("finished"), d.get("retracted"),
                      d.get("mutual", False), d.get("open_for_allies", False),
                      allies_json, km_json, war_id])
            finally:
                con.close()
            enriched += 1
        except Exception:
            logger.exception("[war_enrichment] Failed for war %s", war_id)

    logger.info("[war_enrichment] Done — %s/%s wars enriched", enriched, len(rows))
