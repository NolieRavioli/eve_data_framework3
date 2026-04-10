# applications/market_browser/routes.py
"""Flask blueprint for the Market Browser tool."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, jsonify, render_template, request

from applications._api import db, raw_esi, sde, get_regions, base_ctx

logger = logging.getLogger(__name__)

market_bp = Blueprint("market_browser", __name__, template_folder="templates", static_folder="static")


def _fmt_expires(issued, duration_days) -> str:
    if not issued or duration_days is None:
        return "—"
    try:
        if isinstance(issued, str):
            issued = datetime.fromisoformat(issued)
        if issued.tzinfo is None:
            issued = issued.replace(tzinfo=timezone.utc)
        expires = issued + timedelta(days=int(duration_days))
        delta = expires - datetime.now(timezone.utc)
        total_s = int(delta.total_seconds())
        if total_s <= 0:
            return "Expired"
        d, rem = divmod(total_s, 86400)
        h = rem // 3600
        return f"{d}d {h}h" if d else f"{h}h {(rem % 3600) // 60}m"
    except Exception:
        return "—"


def _query_orders(type_id: int, region_id: int) -> tuple[list, list]:
    from core.io.market_buffer import query_orders as _buf_query, buffered_region_ids

    buf_hit, buf_rows = _buf_query(type_id, region_id)

    if buf_hit and region_id:
        # Specific region is fully buffered — use buffer data only.
        rows = buf_rows
    else:
        # Query DuckDB, excluding any currently-buffered regions so we don't
        # mix stale DB rows with fresh buffer rows.
        buffered = buffered_region_ids()
        exclude_clause = ""
        params: list = [type_id]
        if region_id:
            exclude_clause = "AND mo.region_id = ?"
            params.append(region_id)
        elif buffered:
            placeholders = ", ".join(["?"] * len(buffered))
            exclude_clause = f"AND mo.region_id NOT IN ({placeholders})"
            params.extend(sorted(buffered))

        sql = f"""
            SELECT mo.order_id, mo.is_buy_order, mo.price, mo.volume_remain, mo.volume_total,
                   mo.order_range AS range, mo.location_id, mo.issued, mo.duration, mo.min_volume,
                   CAST(mo.location_id AS VARCHAR) AS location_name
            FROM market_orders mo
            WHERE mo.type_id = ? {exclude_clause}
        """
        try:
            rows = db.query(sql, params)
        except Exception:
            sql_plain = f"""
                SELECT order_id, is_buy_order, price, volume_remain, volume_total,
                       order_range AS range, location_id, issued, duration, min_volume,
                       CAST(location_id AS VARCHAR) AS location_name
                FROM market_orders
                WHERE type_id = ? {exclude_clause}
            """
            try:
                rows = db.query(sql_plain, params)
            except Exception as exc:
                logger.warning("Orders query failed: %s", exc)
                rows = []

        # Merge buffer rows for the universe case.
        if buf_hit and not region_id:
            rows.extend(buf_rows)

    for o in rows:
        o["expires_in"] = _fmt_expires(o.get("issued"), o.get("duration"))

    sells = sorted([o for o in rows if not o["is_buy_order"]], key=lambda x: x["price"])
    buys = sorted([o for o in rows if o["is_buy_order"]], key=lambda x: -x["price"])
    return sells, buys


@market_bp.route("/")
def index():
    ctx = base_ctx("market_browser")
    ctx.update({
        "regions": get_regions(),
        "sells": None, "buys": None,
        "type_id": None, "type_name": "",
        "region_id": 0,
        "best_sell": None, "best_buy": None,
        "sell_volume": 0, "buy_volume": 0,
    })
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

    sells, buys = [], []
    type_name = ""
    best_sell = best_buy = None
    sell_volume = buy_volume = 0

    if type_id:
        try:
            type_name = db.scalar("SELECT name_en FROM sde_types WHERE type_id = ?", [type_id]) or f"Type {type_id}"
        except Exception:
            type_name = f"Type {type_id}"
        sells, buys = _query_orders(type_id, region_id)
        best_sell = min((o["price"] for o in sells), default=None)
        best_buy = max((o["price"] for o in buys), default=None)
        sell_volume = sum(o["volume_remain"] for o in sells)
        buy_volume = sum(o["volume_remain"] for o in buys)

    ctx.update({
        "regions": get_regions(),
        "sells": sells, "buys": buys,
        "type_id": type_id, "type_name": type_name,
        "region_id": region_id,
        "best_sell": best_sell, "best_buy": best_buy,
        "sell_volume": sell_volume, "buy_volume": buy_volume,
    })
    return render_template("market_browser.html", **ctx)


# ── Tree API ──────────────────────────────────────────────────────────────────

@market_bp.route("/tree")
def tree():
    """Return all market groups as a flat list for client-side tree building."""
    try:
        rows = db.query(
            """
            SELECT market_group_id, parent_group_id, name_en, has_types
            FROM sde_marketGroups
            ORDER BY name_en
            """
        )
        return jsonify([dict(r) for r in rows])
    except Exception:
        logger.exception("[MarketBrowser] Error loading market tree")
        return jsonify({"error": "Failed to load market tree. This may indicate a temporary data access issue."}), 500


@market_bp.route("/group/<int:group_id>/types")
def group_types(group_id: int):
    """Return published types in a market group, ordered by name."""
    try:
        rows = db.query(
            """
            SELECT type_id, name_en
            FROM sde_types
            WHERE market_group_id = ? AND published = true
            ORDER BY name_en
            """,
            [group_id],
        )
        return jsonify([dict(r) for r in rows])
    except Exception:
        logger.exception("[MarketBrowser] Error loading group types for %s", group_id)
        return jsonify({"error": "Failed to load group types"}), 500


@market_bp.route("/search")
def search():
    """Full-text search over type names; returns up to 40 matching published types."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify([])
    try:
        rows = db.query(
            """
            SELECT type_id, name_en, market_group_id
            FROM sde_types
            WHERE name_en ILIKE ? AND published = true AND market_group_id IS NOT NULL
            ORDER BY name_en
            LIMIT 40
            """,
            [f"%{q}%"],
        )
        return jsonify([dict(r) for r in rows])
    except Exception:
        logger.exception("[MarketBrowser] Error searching types")
        return jsonify({"error": "Search failed"}), 500


# ── Type detail ───────────────────────────────────────────────────────────────

@market_bp.route("/type/<int:type_id>")
def type_detail(type_id: int):
    """Dedicated type page: full order book, metadata, and price history chart."""
    type_name = sde.name_from_type_id(type_id)
    if not type_name:
        abort(404)

    # Type metadata from SDE
    try:
        type_info = db.query_one(
            """
            SELECT t.type_id, t.name_en, t.description_en, t.published,
                   t.group_id, t.market_group_id, t.volume, t.mass,
                   g.name_en AS group_name, g.category_id,
                   c.name_en AS category_name,
                   mg.name_en AS market_group_name
            FROM sde_types t
            LEFT JOIN sde_groups g     ON g.group_id = t.group_id
            LEFT JOIN sde_categories c ON c.category_id = g.category_id
            LEFT JOIN sde_marketGroups mg ON mg.market_group_id = t.market_group_id
            WHERE t.type_id = ?
            """,
            [type_id],
        )
    except Exception:
        type_info = None

    # Current orders
    sells, buys = _query_orders(type_id, 0)

    best_sell = min((o["price"] for o in sells), default=None)
    best_buy = max((o["price"] for o in buys), default=None)
    sell_volume = sum(o["volume_remain"] for o in sells)
    buy_volume = sum(o["volume_remain"] for o in buys)

    ctx = base_ctx("market_browser")
    ctx.update({
        "type_id": type_id,
        "type_name": type_name,
        "type_info": type_info,
        "sells": sells,
        "buys": buys,
        "best_sell": best_sell,
        "best_buy": best_buy,
        "sell_volume": sell_volume,
        "buy_volume": buy_volume,
        "regions": get_regions(),
    })
    return render_template("market_type.html", **ctx)


@market_bp.route("/type/<int:type_id>/history")
def type_history(type_id: int):
    """Return price history for a type in a region as JSON."""
    region_id = request.args.get("region_id", 10000002, type=int)

    # Check DuckDB cache first
    try:
        cached = db.query(
            """
            SELECT date, lowest, highest, average, volume, order_count
            FROM market_history
            WHERE type_id = ? AND region_id = ?
            ORDER BY date DESC
            LIMIT 365
            """,
            [type_id, region_id],
        )
        if cached:
            return jsonify([dict(r) for r in cached])
    except Exception:
        pass

    # Fallback: fetch from ESI on demand
    resp = raw_esi.get(
        f"https://esi.evetech.net/latest/markets/{region_id}/history/",
        params={"type_id": type_id},
    )
    if not resp.ok:
        return jsonify([])

    data = resp.json()

    # Cache the results asynchronously
    try:
        from collectors.public_data.market import cache_history_rows
        cache_history_rows(type_id, region_id, data)
    except Exception:
        pass

    return jsonify(data)
