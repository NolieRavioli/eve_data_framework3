# tools/market_browser/worker.py
"""Background worker for refreshing market data for a single region."""

from __future__ import annotations

import logging

from esi.public.market_station import fetch_market_orders, save_orders_to_db

logger = logging.getLogger(__name__)


def refresh_region(region_id: int) -> None:
    """Fetch all market orders for *region_id* and persist them to DuckDB.

    Called via the task queue (tools/_adapters.tasks.enqueue).
    """
    logger.info("Starting market refresh for region %s", region_id)
    page = 1
    total_orders = 0
    while True:
        orders, total_pages = fetch_market_orders(region_id, page=page)
        if not orders:
            break
        save_orders_to_db(region_id, orders)
        total_orders += len(orders)
        logger.info("  Page %d/%d — %d orders", page, total_pages, len(orders))
        if page >= total_pages:
            break
        page += 1
    logger.info("Market refresh complete for region %s — %d total orders", region_id, total_orders)
