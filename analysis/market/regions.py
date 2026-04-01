"""Fetch NPC station market orders from ESI and write them to the public DuckDB.

Owns the ``market_orders`` and ``market_region_cooldowns`` table DDL.
"""

import logging
import time

import requests

from core.db.publicDB import connect as public_connect
from core.db import publicDB as sde_store
from core.plugin.adapters import raw_esi

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"
HEADERS = {"Accept": "application/json"}


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


# ── ESI helpers ───────────────────────────────────────────────────────────────

def fetch_with_retries(url: str, params: dict, max_retries: int = 3) -> requests.Response:
    backoff = 1
    for attempt in range(1, max_retries + 1):
        try:
            resp = raw_esi.get(url, headers=HEADERS, params=params)
            if resp.status_code == 420:
                logger.warning("[MarketStation] 420 rate limit on %s, sleeping 5s (attempt %s)", url, attempt)
                time.sleep(5)
                continue
            if resp.status_code in (429, 502, 503, 504):
                logger.warning(
                    "[MarketStation] %s on %s, retrying after %ss (attempt %s)",
                    resp.status_code, url, backoff, attempt,
                )
                time.sleep(backoff)
                backoff *= 2
                continue
            return resp
        except requests.RequestException as exc:
            logger.warning("[MarketStation] Request error on %s (attempt %s): %s", url, attempt, exc)
            time.sleep(backoff)
            backoff *= 2
    return raw_esi.get(url, headers=HEADERS, params=params)


def fetch_market_orders(region_id: int, page: int = 1) -> tuple[list, int]:
    url = f"{ESI_BASE}/markets/{region_id}/orders/"
    params = {"order_type": "all", "page": page, "datasource": "tranquility"}
    resp = fetch_with_retries(url, params)

    if resp.status_code in (400, 403, 404):
        logger.warning("[MarketStation] Bad response %s for region %s, page %s", resp.status_code, region_id, page)
        return [], 0

    resp.raise_for_status()
    return resp.json(), int(resp.headers.get("X-Pages", 1))


def save_orders_to_db(region_id: int, orders: list[dict]) -> None:
    logger.debug("[MarketStation] Saving %s orders for region %s", len(orders), region_id)
    rows = [{**order, "region_id": region_id} for order in orders]
    sde_store.upsert_market_orders(rows)


# ── main worker ───────────────────────────────────────────────────────────────

def fetch_all_market_data() -> None:
    # Ensure our tables exist before any writes
    con = public_connect(read_only=False)
    try:
        ensure_tables(con)
    finally:
        con.close()

    region_ids = sde_store.list_market_region_ids(skip_recently_refreshed=True)
    if not region_ids:
        logger.info("[MarketStation] All regions refreshed recently — nothing to do.")
        return
    logger.info("[MarketStation] Found %s regions to process (skipping recently refreshed)", len(region_ids))

    # ── Phase 1: seed — fetch page 1 of every region to count total pages ────
    logger.info("[MarketStation] Seeding page counts for %s regions...", len(region_ids))
    region_data: dict[int, tuple[list, int]] = {}
    for region_id in region_ids:
        try:
            first_page, total_pages = fetch_market_orders(region_id, page=1)
            region_data[region_id] = (first_page, total_pages)
        except Exception as exc:
            logger.error("[MarketStation] Failed seeding region %s: %s", region_id, exc)
            region_data[region_id] = ([], 0)

    total_pages_overall = sum(tp for _, tp in region_data.values())
    logger.info("[MarketStation] Total pages to fetch: %s across %s regions", total_pages_overall, len(region_ids))

    # ── Phase 2: fetch — remaining pages with cross-region ETA ───────────────
    pages_done = 0
    t0 = time.time()

    for region_id in region_ids:
        first_page, total_pages = region_data[region_id]
        try:
            if not first_page:
                logger.info("[MarketStation] No market data for region %s", region_id)
                pages_done += max(total_pages, 1)
                continue

            save_orders_to_db(region_id, first_page)
            sde_store.mark_region_market_refreshed(region_id)
            pages_done += 1

            for page in range(2, total_pages + 1):
                page_data, _ = fetch_market_orders(region_id, page)
                if not page_data:
                    break
                save_orders_to_db(region_id, page_data)
                pages_done += 1

                elapsed = time.time() - t0
                eta = (elapsed / pages_done) * (total_pages_overall - pages_done) if pages_done else 0
                if total_pages < 50 or page % 7 == 0:
                    logger.info(
                        "[MarketStation] Region %s: page %s/%s  |  overall %.1f%%  ETA %.0fs",
                        region_id, page, total_pages,
                        100 * pages_done / total_pages_overall if total_pages_overall else 100.0,
                        eta,
                    )

        except Exception as exc:
            logger.error("[MarketStation] Failed fetching market data for region %s: %s", region_id, exc)

    logger.info("[MarketStation] Completed fetch of all market data")

