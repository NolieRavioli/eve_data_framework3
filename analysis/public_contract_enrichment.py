"""analysis/public_contract_enrichment.py — Fetch bids and items for public contracts.

Reads unenriched ``public_contracts`` rows (items_json IS NULL or bids_json IS NULL)
and calls the public enrichment endpoints (no auth required).
"""

from __future__ import annotations

import json
import logging

import core.io.public as db
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def run_public_contract_enrichment() -> None:
    """Enrich public contracts with bids and items."""
    con = db.connect()
    try:
        rows = con.execute("""
            SELECT contract_id, type FROM public_contracts
            WHERE items_json IS NULL OR bids_json IS NULL
            LIMIT 2000
        """).fetchall()
    finally:
        con.close()

    if not rows:
        logger.info("[public_contracts] All contracts already enriched.")
        return

    logger.info("[public_contracts] Enriching %s contracts", len(rows))
    enriched = 0
    for (contract_id, contract_type) in rows:
        items_json = None
        bids_json = None

        resp = esi_get(f"{ESI_BASE}/contracts/public/items/{contract_id}/")
        if resp.ok:
            items_json = json.dumps(resp.json())
        elif resp.status_code == 404:
            items_json = "[]"

        if contract_type == "auction":
            resp = esi_get(f"{ESI_BASE}/contracts/public/bids/{contract_id}/")
            if resp.ok:
                bids_json = json.dumps(resp.json())
            elif resp.status_code == 404:
                bids_json = "[]"

        if items_json is not None or bids_json is not None:
            con = db.connect()
            try:
                con.execute("""
                    UPDATE public_contracts SET
                        items_json = COALESCE(?, items_json),
                        bids_json  = COALESCE(?, bids_json)
                    WHERE contract_id = ?
                """, [items_json, bids_json, contract_id])
            finally:
                con.close()
            enriched += 1

    logger.info("[public_contracts] Done — %s contracts enriched", enriched)
