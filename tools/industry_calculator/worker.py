# tools/industry_calculator/worker.py
"""Synchronous manufacturing cost calculator (no background task needed)."""

from __future__ import annotations

import logging
from typing import Any

from tools._adapters import storage

logger = logging.getLogger(__name__)

# Default ME/TE (Material/Time Efficiency, %)
_ME_REDUCTION = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # index == ME level
_TE_REDUCTION = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20]  # index == TE level


def calculate(
    type_id: int,
    quantity: int = 1,
    me: int = 0,
    te: int = 0,
    region_id: int = 10000002,  # The Forge (Jita) default
) -> dict[str, Any]:
    """
    Compute manufacturing costs for *type_id*.

    Returns a dict with keys:
      product_name, product_type_id, blueprint_type_id,
      quantity, me, te, region_id,
      manufacturing_time_s (adjusted for TE),
      materials (list of {type_id, name, required_qty, price, subtotal}),
      total_material_cost, sell_price, sell_value, margin_isk, margin_pct,
      error (str | None)
    """
    me = max(0, min(10, me))
    te = max(0, min(20, te))
    me_factor = 1.0 - (_ME_REDUCTION[me] / 100.0)
    te_factor = 1.0 - (_TE_REDUCTION[te] / 100.0)

    con = storage.connect()
    try:
        # Find the blueprint that produces this type_id via manufacturing
        bp_row = con.execute(
            """
            SELECT p.blueprint_type_id, b.manufacturing_time
            FROM fact_blueprint_products AS p
            JOIN fact_blueprints AS b ON b.blueprint_type_id = p.blueprint_type_id
            WHERE p.activity = 'manufacturing' AND p.product_type_id = ?
            LIMIT 1
            """,
            [type_id],
        ).fetchone()

        if not bp_row:
            return _error(type_id, quantity, me, te, region_id, "No manufacturing blueprint found for this type.")

        blueprint_type_id, base_time = bp_row
        adjusted_time = int(base_time * te_factor) if base_time else None

        # Fetch bill of materials
        mat_rows = con.execute(
            """
            SELECT m.material_type_id, m.quantity, t.name_en
            FROM fact_blueprint_materials AS m
            LEFT JOIN dim_types AS t ON t.type_id = m.material_type_id
            WHERE m.blueprint_type_id = ? AND m.activity = 'manufacturing'
            ORDER BY m.quantity DESC
            """,
            [blueprint_type_id],
        ).fetchall()

        # Fetch product quantity per run
        prod_row = con.execute(
            """
            SELECT quantity FROM fact_blueprint_products
            WHERE blueprint_type_id = ? AND activity = 'manufacturing' AND product_type_id = ?
            """,
            [blueprint_type_id, type_id],
        ).fetchone()
        units_per_run = prod_row[0] if prod_row else 1

        product_name_row = con.execute(
            "SELECT name_en FROM dim_types WHERE type_id = ?", [type_id]
        ).fetchone()
        product_name = product_name_row[0] if product_name_row and product_name_row[0] else f"Type {type_id}"

    finally:
        con.close()

    # Compute material requirements with ME reduction
    materials = []
    total_material_cost = 0.0
    for mat_type_id, base_qty, mat_name in mat_rows:
        required_qty = max(1, round(base_qty * quantity * me_factor))
        price = storage.market_price(mat_type_id, region_id, buy=False)
        subtotal = price * required_qty if price is not None else None
        if subtotal is not None:
            total_material_cost += subtotal
        materials.append({
            "type_id": mat_type_id,
            "name": mat_name or f"Type {mat_type_id}",
            "required_qty": required_qty,
            "price": price,
            "subtotal": subtotal,
        })

    # Sell price of the produced item
    total_units = units_per_run * quantity
    sell_price = storage.market_price(type_id, region_id, buy=False)
    sell_value = sell_price * total_units if sell_price is not None else None
    margin_isk = (sell_value - total_material_cost) if sell_value is not None else None
    margin_pct = (margin_isk / total_material_cost * 100.0) if (margin_isk is not None and total_material_cost > 0) else None

    return {
        "product_name": product_name,
        "product_type_id": type_id,
        "blueprint_type_id": blueprint_type_id,
        "quantity": quantity,
        "units_per_run": units_per_run,
        "total_units": total_units,
        "me": me,
        "te": te,
        "region_id": region_id,
        "manufacturing_time_s": adjusted_time,
        "materials": materials,
        "total_material_cost": total_material_cost,
        "sell_price": sell_price,
        "sell_value": sell_value,
        "margin_isk": margin_isk,
        "margin_pct": margin_pct,
        "error": None,
    }


def _error(type_id, quantity, me, te, region_id, msg) -> dict:
    return {
        "product_name": f"Type {type_id}",
        "product_type_id": type_id,
        "blueprint_type_id": None,
        "quantity": quantity,
        "units_per_run": None,
        "total_units": None,
        "me": me,
        "te": te,
        "region_id": region_id,
        "manufacturing_time_s": None,
        "materials": [],
        "total_material_cost": 0.0,
        "sell_price": None,
        "sell_value": None,
        "margin_isk": None,
        "margin_pct": None,
        "error": msg,
    }
