# tools/market_browser/routes.py
"""Flask blueprint for the Market Browser tool."""

from __future__ import annotations

import logging

from flask import Blueprint, redirect, render_template, request, url_for

from applications._adapters import db, tasks
from applications._base import base_ctx

logger = logging.getLogger(__name__)

market_bp = Blueprint("market_browser", __name__, template_folder="templates", static_folder="static")


@market_bp.route("/")
def index():
    ctx = base_ctx("market_browser")

    # Pull region list — fall back gracefully if SDE isn't loaded
    try:
        rows = db.query("SELECT region_id, region_name FROM dim_regions ORDER BY region_name")
        regions = [{"id": r["region_id"], "name": r["region_name"] or f"Region {r['region_id']}"} for r in rows]
    except Exception:
        regions = []

    ctx.update({"regions": regions, "orders": None, "type_id": None, "region_id": None})
    return render_template("market_browser.html", **ctx)


@market_bp.route("/orders")
def orders():
    ctx = base_ctx("market_browser")

    try:
        type_id = int(request.args.get("type_id", 0))
        region_id = int(request.args.get("region_id", 0))
    except (ValueError, TypeError):
        type_id = 0
        region_id = 0

    order_rows = []
    best_buy = None
    best_sell = None
    type_name = ""
    regions = []
    try:
        rows = db.query("SELECT region_id, region_name FROM dim_regions ORDER BY region_name")
        regions = [{"id": r["region_id"], "name": r["region_name"] or f"Region {r['region_id']}"} for r in rows]
    except Exception:
        regions = []

    if type_id and region_id:
        try:
            type_name = db.scalar("SELECT name_en FROM dim_types WHERE type_id = ?", [type_id]) or f"Type {type_id}"
            order_rows = db.query(
                """
                SELECT order_id, is_buy_order AS is_buy, price, volume_remain, volume_total,
                       order_range AS range, location_id, issued
                FROM market_orders
                WHERE type_id = ? AND region_id = ?
                ORDER BY is_buy_order DESC, price ASC
                """,
                [type_id, region_id],
            )
            sells = [o["price"] for o in order_rows if not o["is_buy"]]
            buys = [o["price"] for o in order_rows if o["is_buy"]]
            best_sell = min(sells) if sells else None
            best_buy = max(buys) if buys else None
        except Exception as exc:
            logger.warning("Market orders query failed: %s", exc)

    ctx.update({
        "regions": regions,
        "orders": order_rows,
        "type_id": type_id,
        "type_name": type_name,
        "region_id": region_id,
        "best_buy": best_buy,
        "best_sell": best_sell,
    })
    return render_template("market_browser.html", **ctx)


@market_bp.route("/refresh", methods=["POST"])
def refresh():
    try:
        region_id = int(request.form.get("region_id", 0))
    except (ValueError, TypeError):
        region_id = 0

    if not region_id:
        return redirect(url_for("market_browser.index"))

    from applications.market_browser.worker import refresh_region
    task_id = tasks.enqueue(
        f"Market refresh — region {region_id}",
        refresh_region,
        region_id,
        owner_id=0,
        queue="public",
    )
    return redirect(url_for("queue_viewer.task_progress", task_id=task_id))

