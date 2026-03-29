# webUI/market_browser.py

from flask import Blueprint, jsonify, render_template, request

from db.database import get_public_session
from db.models import MarketOrder
from util import sde
from webUI.context import base_ctx

market_bp = Blueprint("market_browser", __name__, url_prefix="/market")


@market_bp.route("/")
def browser():
    sde.load_types_data()
    sde.load_market_tree()

    raw_query = request.args.get("type_id", "").strip()
    group_id = request.args.get("group_id", type=int)
    region_id = request.args.get("region_id", type=int)
    location_id = request.args.get("location_id", type=int)
    is_buy = request.args.get("is_buy", type=int)
    sort_by = request.args.get("sort_by", "price")
    page = request.args.get("page", 1, type=int)
    page_size = 50

    if group_id:
        type_ids = set(sde.get_types_in_group(group_id))
    else:
        type_ids = sde.resolve_type_ids(raw_query)
    has_type_filter = bool(group_id or raw_query)

    db = get_public_session()
    try:
        query = db.query(MarketOrder)
        if type_ids:
            query = query.filter(MarketOrder.type_id.in_(type_ids))
        elif has_type_filter:
            query = query.filter(MarketOrder.type_id == -1)

        if region_id:
            query = query.filter(MarketOrder.region_id == region_id)
        if location_id:
            query = query.filter(MarketOrder.location_id == location_id)
        if is_buy in (0, 1):
            query = query.filter(MarketOrder.is_buy_order == bool(is_buy))

        if sort_by == "volume":
            query = query.order_by(MarketOrder.volume_remain.desc())
        else:
            query = query.order_by(MarketOrder.price.asc())

        total = query.count()
        results = query.offset((page - 1) * page_size).limit(page_size).all()
    finally:
        db.close()

    return render_template(
        "market_browser.html",
        **base_ctx("market"),
        results=results,
        page=page,
        total=total,
        page_size=page_size,
        query=raw_query,
        selected_group=group_id,
        region_id=region_id,
        location_id=location_id,
        is_buy=is_buy,
        sort_by=sort_by,
        market_tree=sde.load_market_tree(),
        name_from_type_id=sde.name_from_type_id,
    )


@market_bp.route("/autocomplete")
def autocomplete():
    """Return up to 10 item-name suggestions matching the q prefix."""

    prefix = request.args.get("q", "").strip()
    return jsonify(sde.suggest_type_names(prefix, limit=10))
