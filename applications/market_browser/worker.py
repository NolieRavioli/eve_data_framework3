# applications/market_browser/worker.py
"""Background worker for refreshing market data for a single region."""

from __future__ import annotations

import logging

from applications._adapters import raw_esi, upsert_market_orders, mark_region_market_refreshed

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def refresh_region(region_id: int) -> None:
    """Fetch all market orders for *region_id* and persist them to DuckDB."""
    logger.info("Starting market refresh for region %s", region_id)
    url = f"{ESI_BASE}/markets/{region_id}/orders/"
    total_orders = 0

    resp = raw_esi.get(url, params={"order_type": "all", "page": 1, "datasource": "tranquility"})
    if not resp.ok:
        logger.warning("ESI %s fetching region %s — aborting", resp.status_code, region_id)
        return
    orders = resp.json()
    if not orders:
        logger.info("No orders for region %s", region_id)
        return
    total_pages = int(resp.headers.get("X-Pages", 1))
    upsert_market_orders([{**o, "region_id": region_id} for o in orders])
    mark_region_market_refreshed(region_id)
    total_orders += len(orders)
    logger.info("  Page 1/%d — %d orders", total_pages, len(orders))

    for page in range(2, total_pages + 1):
        resp = raw_esi.get(url, params={"order_type": "all", "page": page, "datasource": "tranquility"})
        if not resp.ok:
            logger.warning("ESI %s on page %d — skipping", resp.status_code, page)
            continue
        orders = resp.json()
        if not orders:
            break
        upsert_market_orders([{**o, "region_id": region_id} for o in orders])
        total_orders += len(orders)
        logger.info("  Page %d/%d — %d orders", page, total_pages, len(orders))

    logger.info("Market refresh complete for region %s — %d total orders", region_id, total_orders)
