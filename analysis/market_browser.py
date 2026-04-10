"""analysis/market_browser.py — Universe-wide market orchestration.

Iterates all market regions tracked in ``sde_market_groups`` / ``sde_types``,
coordinates NPC-region order collection and structure discovery, then triggers
market history batch fetching.

This module contains no DDL — it calls raw collectors that own their tables.
"""

from __future__ import annotations

import logging

import core.db.public as db
import core.db.sde as sde

logger = logging.getLogger(__name__)


def run_market_browser() -> None:
    """Top-level orchestrator: collect market orders for all active regions."""
    from collectors.public_data.market import (
        fetch_region_orders,
        fetch_active_market_history,
    )
    from collectors.public_data.structures import discover_structures

    # 1. Discover / update known structures so structure orders can be fetched
    try:
        discover_structures()
    except Exception:
        logger.exception("[market_browser] Structure discovery failed — continuing")

    # 2. Collect NPC-region orders for every market region
    con = db.connect()
    try:
        region_rows = con.execute(
            "SELECT region_id FROM sde_mapRegions WHERE region_id IS NOT NULL"
        ).fetchall()
    except Exception:
        logger.warning("[market_browser] Could not read region list — falling back to SDE helper")
        region_rows = []
    finally:
        con.close()

    if not region_rows:
        # Fall back to SDE helper if the table name differs
        try:
            region_rows = [(r["region_id"],) for r in sde.get_market_regions()]
        except Exception:
            logger.exception("[market_browser] No region source available")
            return

    region_ids = [row[0] for row in region_rows if row[0]]
    logger.info("[market_browser] Fetching orders for %s regions", len(region_ids))

    for region_id in region_ids:
        try:
            fetch_region_orders(region_id)
        except Exception:
            logger.exception("[market_browser] fetch_region_orders failed for region %s", region_id)

    # 3. Refresh market history for types seen recently in orders
    try:
        fetch_active_market_history()
    except Exception:
        logger.exception("[market_browser] fetch_active_market_history failed — continuing")

    logger.info("[market_browser] Done.")
