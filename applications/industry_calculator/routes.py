# tools/industry_calculator/routes.py
"""Flask blueprint for the Industry Calculator tool."""

from __future__ import annotations

import logging

from flask import Blueprint, render_template, request

from applications._adapters import storage
from applications._base import base_ctx, require_role

logger = logging.getLogger(__name__)

industry_bp = Blueprint("industry_calculator", __name__, template_folder="templates", static_folder="static")

# Jita region id default
_DEFAULT_REGION = 10000002


@industry_bp.route("/")
@require_role("industry")
def index():
    ctx = base_ctx("industry_calculator")
    ctx.update({"result": None, "type_id": None, "region_id": _DEFAULT_REGION, "regions": _get_regions()})
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
        region_id = int(request.args.get("region_id", _DEFAULT_REGION))
    except (ValueError, TypeError):
        type_id = 0
        quantity = 1
        me = 0
        te = 0
        region_id = _DEFAULT_REGION

    result = None
    if type_id:
        from applications.industry_calculator.worker import calculate
        result = calculate(type_id, quantity=quantity, me=me, te=te, region_id=region_id)

    ctx.update({
        "result": result,
        "type_id": type_id,
        "quantity": quantity,
        "me": me,
        "te": te,
        "region_id": region_id,
        "regions": _get_regions(),
    })
    return render_template("industry_calculator.html", **ctx)


def _get_regions() -> list[dict]:
    con = storage.connect()
    try:
        rows = con.execute(
            "SELECT region_id, region_name FROM dim_regions ORDER BY region_name"
        ).fetchall()
        return [{"id": r[0], "name": r[1] or f"Region {r[0]}"} for r in rows]
    except Exception:
        return []
    finally:
        con.close()

