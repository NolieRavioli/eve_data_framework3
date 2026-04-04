# applications/industry_calculator/routes.py
"""Flask blueprint for the Industry Calculator tool."""

from __future__ import annotations

import logging

from flask import Blueprint, render_template, request

from applications._adapters import db, DEFAULT_REGION, get_regions
from applications._base import base_ctx, require_role
from applications.industry_calculator.worker import calculate

logger = logging.getLogger(__name__)

industry_bp = Blueprint("industry_calculator", __name__, template_folder="templates", static_folder="static")


@industry_bp.route("/")
@require_role("industry")
def index():
    ctx = base_ctx("industry_calculator")
    ctx.update({"result": None, "type_id": None, "region_id": DEFAULT_REGION, "regions": get_regions()})
    return render_template("industry_calculator.html", **ctx)


@industry_bp.route("/calc")
@require_role("industry")
def calc():
    ctx = base_ctx("industry_calculator")

    try:
        type_id = int(request.args.get("type_id", 0))
        quantity = max(1, int(request.args.get("quantity", 1)))
        me = max(0, min(10, int(request.args.get("me", 0))))
        te = max(0, min(20, int(request.args.get("te", 0))))
        region_id = int(request.args.get("region_id", DEFAULT_REGION))
    except (ValueError, TypeError):
        type_id = 0
        quantity = 1
        me = 0
        te = 0
        region_id = DEFAULT_REGION

    result = None
    if type_id:
        result = calculate(type_id, quantity=quantity, me=me, te=te, region_id=region_id)

    ctx.update({
        "result": result,
        "type_id": type_id,
        "quantity": quantity,
        "me": me,
        "te": te,
        "region_id": region_id,
        "regions": get_regions(),
    })
    return render_template("industry_calculator.html", **ctx)


