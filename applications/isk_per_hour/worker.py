# tools/isk_per_hour/worker.py
"""Background worker that computes ISK/hr rankings for all blueprints in a category."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from applications._adapters import storage

logger = logging.getLogger(__name__)


def compute_rankings(region_id: int, category_id: int) -> None:
    """
    Iterate every manufacturing blueprint whose product belongs to *category_id*
    and compute ISK/hr = (sell_price * units_per_run - mat_cost) / build_hours.

    Results are upserted into the ``isk_per_hour_results`` DuckDB table.
    """
    logger.info("ISK/hr compute starting — region=%s category=%s", region_id, category_id)

    con = storage.connect()
    try:
        # Blueprints whose product is in the requested category
        bp_rows = con.execute(
            """
            SELECT
                p.blueprint_type_id,
                p.product_type_id,
                p.quantity AS units_per_run,
                b.manufacturing_time,
                t.name_en   AS product_name,
                t.category_id
            FROM fact_blueprint_products AS p
            JOIN fact_blueprints AS b ON b.blueprint_type_id = p.blueprint_type_id
            JOIN dim_types AS t ON t.type_id = p.product_type_id
            WHERE p.activity = 'manufacturing'
              AND t.category_id = ?
              AND b.manufacturing_time > 0
            """,
            [category_id],
        ).fetchall()
    finally:
        con.close()

    if not bp_rows:
        logger.warning("No blueprints found for category %s", category_id)
        return

    logger.info("Found %d blueprints to evaluate", len(bp_rows))
    computed_at = datetime.now(timezone.utc)
    rows_to_upsert = []

    for bp_type_id, product_type_id, units_per_run, build_time_s, product_name, cat_id in bp_rows:
        # Fetch bill of materials
        con = storage.connect()
        try:
            mat_rows = con.execute(
                """
                SELECT material_type_id, quantity
                FROM fact_blueprint_materials
                WHERE blueprint_type_id = ? AND activity = 'manufacturing'
                """,
                [bp_type_id],
            ).fetchall()
        finally:
            con.close()

        # Material cost (cheapest sell orders)
        mat_cost = 0.0
        costed = True
        for mat_type_id, qty in mat_rows:
            price = storage.market_price(mat_type_id, region_id, buy=False)
            if price is None:
                costed = False
                break
            mat_cost += price * qty

        if not costed:
            continue  # skip items with missing price data

        sell_price = storage.market_price(product_type_id, region_id, buy=False)
        if sell_price is None:
            continue

        sell_value = sell_price * units_per_run
        isk_per_run = sell_value - mat_cost
        build_hours = build_time_s / 3600.0
        isk_per_hour = isk_per_run / build_hours if build_hours > 0 else 0.0
        margin_pct = (isk_per_run / mat_cost * 100.0) if mat_cost > 0 else 0.0

        rows_to_upsert.append((
            product_type_id,
            product_name or f"Type {product_type_id}",
            region_id,
            category_id,
            isk_per_run,
            isk_per_hour,
            margin_pct,
            computed_at,
        ))

    if not rows_to_upsert:
        logger.warning("No rows to upsert — no complete price data found for this category/region.")
        return

    con = storage.connect()
    try:
        con.executemany(
            """
            INSERT OR REPLACE INTO isk_per_hour_results
                (type_id, type_name, region_id, category_id, isk_per_run, isk_per_hour, margin_pct, computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows_to_upsert,
        )
        logger.info("Upserted %d ISK/hr rows for region=%s category=%s", len(rows_to_upsert), region_id, category_id)
    finally:
        con.close()
