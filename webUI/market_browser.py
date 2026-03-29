# webUI/market_browser.py

from flask import Blueprint, jsonify, render_template, request

from util import sde, sde_store
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

    total, results = sde_store.search_market_orders(
        type_ids=type_ids,
        has_type_filter=has_type_filter,
        region_id=region_id,
        location_id=location_id,
        is_buy=is_buy,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )

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
