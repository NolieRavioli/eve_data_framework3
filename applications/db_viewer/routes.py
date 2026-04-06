# applications/db_viewer/routes.py
"""Database Viewer blueprint — personal stats, admin stats, schema browser, SQL queries."""

from __future__ import annotations

import logging

from flask import (
    Blueprint,
    abort,
    jsonify,
    render_template,
    request,
    session,
    url_for,
)

from applications._api import require_admin, require_role, base_ctx
from applications._api import db_admin, queue_info
from core.bus.websocket import register_websock

logger = logging.getLogger(__name__)

db_bp = Blueprint("db_viewer", __name__,
                  template_folder="templates",
                  static_folder="static")

# ── Focused WebSocket endpoints ──────────────────────────────────────────────────

# Personal tier: owner-filtered (client-side) db/stats push
register_websock(
    "/db/ws",
    ["db/stats"],
    access_level="user",
    required_role="db",
)

# Admin tier: global db/stats push (all owners)
register_websock(
    "/db/admin/ws",
    ["db/stats"],
    access_level="admin",
)


# ── Landing ───────────────────────────────────────────────────────────────────────────────────────────────

@db_bp.route("/")
@require_role("db")
def index():
    owner_id = session.get("owner_id")
    is_admin = session.get("is_admin", False)

    # Personal: user’s own private tables
    private_tables = {}
    try:
        private_tables = db_admin.list_private_tables(owner_id) if owner_id else {}
    except FileNotFoundError:
        pass

    # Admin: public table counts
    public_counts = {}
    if is_admin:
        public_counts = db_admin.table_counts()

    # DB write-activity stats for the current owner
    stats_payload = db_admin.get_db_gateway_stats()
    raw_attribution = stats_payload.get("attribution", {})
    owner_totals = stats_payload.get("owner_totals", {})
    weights = stats_payload.get("weights", {})

    # Filter attribution to tasks owned by the current user; enrich with task metadata.
    owner_attribution: list[dict] = []
    for tid, entry in raw_attribution.items():
        if entry.get("owner_id") != owner_id:
            continue
        row = dict(entry)
        row["task_id"] = tid
        task = queue_info.get_task(tid)
        row["task_name"] = task.name if task else "(expired)"
        row["task_status"] = task.status if task else "unknown"
        owner_attribution.append(row)

    owner_attribution.sort(key=lambda r: r.get("rows", 0), reverse=True)
    my_totals = owner_totals.get(str(owner_id), {})

    return render_template(
        "db_index.html",
        **base_ctx("db_viewer"),
        private_tables=private_tables,
        public_counts=public_counts,
        is_admin=is_admin,
        owner_id=owner_id,
        owner_attribution=owner_attribution,
        my_totals=my_totals,
        weights=weights,
    )


# ── Personal tier — private DB ────────────────────────────────────────────────

@db_bp.route("/private/")
@require_role("db")
def private_browser_self():
    owner_id = session.get("owner_id")
    try:
        tables = db_admin.list_private_tables(owner_id)
    except FileNotFoundError:
        tables = {}
    return render_template(
        "db_private_browser.html",
        **base_ctx("db_viewer"),
        tables=tables,
        db_label=f"Your private database (owner {owner_id})",
        browser_owner_id=owner_id,
        query_url=url_for("db_viewer.private_query_self"),
    )


@db_bp.route("/private/query", methods=["POST"])
@require_role("db")
def private_query_self():
    owner_id = session.get("owner_id")
    data = request.get_json(force=True, silent=True) or {}
    raw_sql = (data.get("sql") or "").strip()
    if not raw_sql:
        return jsonify({"error": "No SQL provided"}), 400
    try:
        return jsonify(db_admin.query_private_sql(owner_id, raw_sql, row_limit=500))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


# ── Admin tier — stats ────────────────────────────────────────────────────────

@db_bp.route("/admin/")
@require_admin
def admin_stats():
    table_counts = db_admin.table_counts()
    sorted_counts = dict(sorted(table_counts.items(), key=lambda x: x[1], reverse=True))

    # DB write-activity stats (global)
    stats_payload = db_admin.get_db_gateway_stats()
    owner_totals = stats_payload.get("owner_totals", {})
    weights = stats_payload.get("weights", {})

    # Compute global totals by summing all owner buckets
    global_totals: dict = {
        "inserts": 0, "upserts": 0, "updates": 0, "deletes": 0,
        "truncates": 0, "ddls": 0, "bulk_loads": 0, "reads": 0,
        "rows": 0, "db_units": 0.0,
    }
    for bucket in owner_totals.values():
        for k in ("inserts", "upserts", "updates", "deletes",
                  "truncates", "ddls", "bulk_loads", "reads", "rows"):
            global_totals[k] += bucket.get(k, 0)
        global_totals["db_units"] = round(global_totals["db_units"] + bucket.get("db_units", 0.0), 4)

    return render_template(
        "db_admin.html",
        **base_ctx("db_viewer"),
        table_counts=sorted_counts,
        total_rows=sum(table_counts.values()),
        table_count=len(table_counts),
        owner_totals=owner_totals,
        global_totals=global_totals,
        weights=weights,
    )


# ── Admin tier — public browser ───────────────────────────────────────────────

@db_bp.route("/public/")
@require_admin
def public_browser():
    tables = db_admin.list_tables()
    return render_template(
        "db_public_browser.html",
        **base_ctx("db_viewer"),
        tables=tables,
        db_label="public.duckdb",
        browser_owner_id=None,
    )


@db_bp.route("/public/query", methods=["POST"])
@require_admin
def public_query():
    data = request.get_json(force=True, silent=True) or {}
    raw_sql = (data.get("sql") or "").strip()
    if not raw_sql:
        return jsonify({"error": "No SQL provided"}), 400
    try:
        return jsonify(db_admin.query_sql(raw_sql, row_limit=500))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


# ── Admin tier — specific owner private browser ──────────────────────────────

@db_bp.route("/<int:owner_id>/")
@require_admin
def private_browser(owner_id: int):
    try:
        tables = db_admin.list_private_tables(owner_id)
    except FileNotFoundError:
        abort(404)
    return render_template(
        "db_private_browser.html",
        **base_ctx("db_viewer"),
        tables=tables,
        db_label=f"owner {owner_id} private db",
        browser_owner_id=owner_id,
        query_url=url_for("db_viewer.private_query", owner_id=owner_id),
    )


@db_bp.route("/<int:owner_id>/query", methods=["POST"])
@require_admin
def private_query(owner_id: int):
    data = request.get_json(force=True, silent=True) or {}
    raw_sql = (data.get("sql") or "").strip()
    if not raw_sql:
        return jsonify({"error": "No SQL provided"}), 400
    try:
        return jsonify(db_admin.query_private_sql(owner_id, raw_sql, row_limit=500))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


# ── Admin SQL console ─────────────────────────────────────────────────────────

@db_bp.route("/query", methods=["POST"])
@require_admin
def query():
    data = request.get_json(force=True, silent=True) or {}
    raw_sql = (data.get("sql") or "").strip()
    if not raw_sql:
        return jsonify({"error": "No SQL provided"}), 400
    try:
        return jsonify(db_admin.query_sql(raw_sql, row_limit=500))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


# ── Stats JSON ────────────────────────────────────────────────────────────────

@db_bp.route("/stats")
@require_role("db")
def stats():
    is_admin = session.get("is_admin", False)
    if is_admin:
        counts = db_admin.table_counts()
        return jsonify({"tables": counts, "total_rows": sum(counts.values())})

    owner_id = session.get("owner_id")
    try:
        tables = db_admin.list_private_tables(owner_id)
        return jsonify({"tables": {t: len(cols) for t, cols in tables.items()}, "type": "private"})
    except FileNotFoundError:
        return jsonify({"tables": {}, "type": "private"})


@db_bp.route("/stats/personal")
@require_role("db")
def stats_personal():
    """Return DB-activity stats filtered to the current owner's tasks."""
    owner_id = session.get("owner_id")
    payload = db_admin.get_db_gateway_stats()
    attribution = {
        tid: entry for tid, entry in payload.get("attribution", {}).items()
        if entry.get("owner_id") == owner_id
    }
    owner_totals = payload.get("owner_totals", {})
    return jsonify({
        "attribution": attribution,
        "my_totals": owner_totals.get(str(owner_id), {}),
        "weights": payload.get("weights", {}),
    })


@db_bp.route("/stats/global")
@require_admin
def stats_global():
    """Return full DB-activity stats across all owners (admin only)."""
    payload = db_admin.get_db_gateway_stats()
    return jsonify({
        "attribution": payload.get("attribution", {}),
        "owner_totals": payload.get("owner_totals", {}),
        "weights": payload.get("weights", {}),
    })
