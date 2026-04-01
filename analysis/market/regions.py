"""Fetch NPC station market orders from ESI and write them to the public DuckDB.

Owns the ``market_orders`` and ``market_region_cooldowns`` table DDL.
"""

import logging

from core.db.publicDB import connect as public_connect
from core.db import publicDB as sde_store
from core.queue.esi_req import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


# ── Table DDL — this collector OWNS market_orders + market_region_cooldowns ───

def ensure_tables(con) -> None:
    """Idempotent DDL for market tables."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS market_orders (
            order_id BIGINT PRIMARY KEY,
            type_id BIGINT,
            location_id BIGINT,
            region_id BIGINT,
            is_buy_order BOOLEAN,
            issued TIMESTAMP,
            duration BIGINT,
            price DOUBLE,
            order_range VARCHAR,
            volume_remain BIGINT,
            volume_total BIGINT,
            min_volume BIGINT,
            last_seen TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS market_region_cooldowns (
            region_id BIGINT PRIMARY KEY,
            refreshed_until TIMESTAMP
        )
    """)


# ── Worker ────────────────────────────────────────────────────────────────────

def fetch_all_market_data() -> None:
    con = public_connect(read_only=False)
    try:
        ensure_tables(con)
    finally:
        con.close()

    region_ids = sde_store.list_market_region_ids(skip_recently_refreshed=True)
    if not region_ids:
        logger.info("[MarketStation] All regions refreshed recently — nothing to do.")
        return
    logger.info("[MarketStation] Processing %s regions...", len(region_ids))

    for region_id in region_ids:
        url = f"{ESI_BASE}/markets/{region_id}/orders/"
        resp = esi_get(url, params={"order_type": "all", "page": 1, "datasource": "tranquility"})
        if not resp.ok:
            logger.warning("[MarketStation] %s on region %s page 1 — skipping", resp.status_code, region_id)
            continue
        orders = resp.json()
        if not orders:
            continue
        total_pages = int(resp.headers.get("X-Pages", 1))
        sde_store.upsert_market_orders([{**o, "region_id": region_id} for o in orders])
        sde_store.mark_region_market_refreshed(region_id)
        logger.info("[MarketStation] Region %s page 1/%s — %s orders inserted", region_id, total_pages, len(orders))

        for page in range(2, total_pages + 1):
            resp = esi_get(url, params={"order_type": "all", "page": page, "datasource": "tranquility"})
            if not resp.ok:
                logger.warning("[MarketStation] %s on region %s page %s — skipping", resp.status_code, region_id, page)
                continue
            orders = resp.json()
            if not orders:
                break
            sde_store.upsert_market_orders([{**o, "region_id": region_id} for o in orders])
            logger.info("[MarketStation] Region %s page %s/%s — %s orders inserted", region_id, page, total_pages, len(orders))

    logger.info("[MarketStation] Completed")

