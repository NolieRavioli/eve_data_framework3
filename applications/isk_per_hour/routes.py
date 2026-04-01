# tools/isk_per_hour/routes.py
"""Flask blueprint for the ISK/hr ranking tool."""

from __future__ import annotations

import logging

from flask import Blueprint, redirect, render_template, request, url_for

from applications._adapters import storage, tasks
from applications._base import base_ctx, require_role

logger = logging.getLogger(__name__)

isk_bp = Blueprint("isk_per_hour", __name__, template_folder="templates", static_folder="static")

_DEFAULT_REGION = 10000002  # The Forge (Jita)


@isk_bp.route("/")
@require_role("isk_per_hour")
def index():
    ctx = base_ctx("isk_per_hour")
    ctx.update({
        "regions": _get_regions(),
        "categories": _get_categories(),
        "results": None,
        "region_id": _DEFAULT_REGION,
        "category_id": None,
    })
    return render_template("isk_per_hour.html", **ctx)


@isk_bp.route("/compute", methods=["POST"])
@require_role("isk_per_hour")
def compute():
    try:
        region_id = int(request.form.get("region_id", _DEFAULT_REGION))
        category_id = int(request.form.get("category_id", 0))
    except (ValueError, TypeError):
        region_id = _DEFAULT_REGION
        category_id = 0

    if not category_id:
        return redirect(url_for("isk_per_hour.index"))

    from tools.isk_per_hour.worker import compute_rankings
    task_id = tasks.enqueue(
        f"ISK/hr — region {region_id}, category {category_id}",
        compute_rankings,
        region_id,
        category_id,
        owner_id=0,
        queue="public",
    )
    return redirect(url_for("queue_viewer.task_progress", task_id=task_id))


@isk_bp.route("/results")
@require_role("isk_per_hour")
def results():
    ctx = base_ctx("isk_per_hour")

    try:
        region_id = int(request.args.get("region_id", _DEFAULT_REGION))
        category_id = int(request.args.get("category_id", 0))
    except (ValueError, TypeError):
        region_id = _DEFAULT_REGION
        category_id = 0

    rows = []
    if region_id and category_id:
        con = storage.connect()
        try:
            raw = con.execute(
                """
                SELECT type_id, type_name, isk_per_run, isk_per_hour, margin_pct, computed_at
                FROM isk_per_hour_results
                WHERE region_id = ? AND category_id = ?
                ORDER BY isk_per_hour DESC
                """,
                [region_id, category_id],
            ).fetchall()
            rows = [
                {
                    "type_id": r[0],
                    "type_name": r[1],
                    "isk_per_run": r[2],
                    "isk_per_hour": r[3],
                    "margin_pct": r[4],
                    "computed_at": r[5],
                }
                for r in raw
            ]
        except Exception as exc:
            logger.warning("ISK/hr results query failed: %s", exc)
        finally:
            con.close()

    ctx.update({
        "regions": _get_regions(),
        "categories": _get_categories(),
        "results": rows,
        "region_id": region_id,
        "category_id": category_id,
    })
    return render_template("isk_per_hour.html", **ctx)


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


def _get_categories() -> list[dict]:
    con = storage.connect()
    try:
        rows = con.execute(
            "SELECT category_id, name_en FROM dim_categories WHERE published = TRUE ORDER BY name_en"
        ).fetchall()
        return [{"id": r[0], "name": r[1] or f"Cat {r[0]}"} for r in rows]
    except Exception:
        return []
    finally:
        con.close()

