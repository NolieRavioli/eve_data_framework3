"""collectors/public_data/loyalty.py — Loyalty store offers for all NPC corporations.

NPC corporation IDs are sourced from the SDE (``npcCorporations.jsonl``).

**Table ownership:** ``loyalty_offers``
"""

from __future__ import annotations

import logging

from core.db.public import connect as public_connect
from core.db.writer import db_executemany
import core.db.sde as sde
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS loyalty_offers (
            offer_id            INTEGER NOT NULL,
            corporation_id      BIGINT NOT NULL,
            type_id             INTEGER NOT NULL,
            quantity            INTEGER NOT NULL,
            lp_cost             INTEGER NOT NULL,
            isk_cost            BIGINT DEFAULT 0,
            ak_cost             INTEGER DEFAULT 0,
            required_items_json TEXT,
            fetched_at          TIMESTAMP DEFAULT now(),
            PRIMARY KEY (offer_id, corporation_id)
        )
    """)


def _get_npc_corp_ids() -> list[int]:
    """Return NPC corporation IDs from in-memory SDE cache."""
    try:
        # sde.get_npc_corp_ids() if available; otherwise fall back to DuckDB
        return sde.get_npc_corp_ids()
    except AttributeError:
        pass
    from core.db.public import connect as pub_connect
    import json
    con = pub_connect()
    try:
        rows = con.execute(
            "SELECT json FROM sde_npcCorporations"
        ).fetchall()
        return [json.loads(r[0])["corporationID"] for r in rows if r[0]]
    except Exception:
        logger.warning("[loyalty] Could not load NPC corp IDs from SDE")
        return []
    finally:
        con.close()


def fetch_loyalty_offers() -> None:
    """Fetch loyalty store offers for all NPC corporations."""
    con = public_connect(read_only=False)
    try:
        ensure_tables(con)
    finally:
        con.close()

    import json as _json
    corp_ids = _get_npc_corp_ids()
    logger.info("[loyalty] Fetching offers for %s NPC corps", len(corp_ids))
    total = 0
    for corp_id in corp_ids:
        resp = esi_get(f"{ESI_BASE}/loyalty/stores/{corp_id}/offers/")
        if not resp.ok:
            continue
        rows = []
        for offer in resp.json():
            req = _json.dumps(offer.get("required_items")) if offer.get("required_items") else None
            rows.append((offer["offer_id"], int(corp_id), offer["type_id"],
                         offer["quantity"], offer["lp_cost"],
                         offer.get("isk_cost", 0), offer.get("ak_cost", 0), req))
        if rows:
            db_executemany("""
                INSERT INTO loyalty_offers
                    (offer_id, corporation_id, type_id, quantity, lp_cost,
                     isk_cost, ak_cost, required_items_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (offer_id, corporation_id) DO UPDATE SET
                    quantity = excluded.quantity, lp_cost = excluded.lp_cost,
                    fetched_at = now()
            """, rows)
            total += len(rows)

    logger.info("[loyalty] Done — %s total offers", total)
