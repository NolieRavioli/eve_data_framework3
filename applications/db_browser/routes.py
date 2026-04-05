# applications/db_browser/routes.py
"""DuckDB / SQLite browser blueprint — browse tables and run queries."""

from __future__ import annotations

import logging

from flask import (
    Blueprint,
    abort,
    jsonify,
    render_template,
    request,
)

from applications._api import require_admin, base_ctx
from applications._api import db_admin

logger = logging.getLogger(__name__)
db_bp = Blueprint("db_browser", __name__, template_folder="templates", static_folder="static")


@db_bp.route("/")
@require_admin
def index():
    target_owner_id = request.args.get("owner_id", type=int)
    try:
        if target_owner_id is not None:
            tables = db_admin.list_private_tables(target_owner_id)
            db_label = f"owner {target_owner_id} private db"
        else:
            tables = db_admin.list_tables()
            db_label = "public.duckdb"
    except FileNotFoundError:
        abort(404)
    return render_template(
        "db_browser.html",
        **base_ctx("db_browser"),
        tables=tables,
        db_label=db_label,
        browser_owner_id=target_owner_id,
    )


@db_bp.route("/query", methods=["POST"])
@require_admin
def query():
    data = request.get_json(force=True, silent=True) or {}
    raw_sql = (data.get("sql") or "").strip()
    target_owner_id = data.get("owner_id")
    if not raw_sql:
        return jsonify({"error": "No SQL provided"}), 400

    try:
        if target_owner_id is not None:
            return jsonify(
                db_admin.query_private_sql(
                    int(target_owner_id),
                    raw_sql,
                    row_limit=500,
                )
            )
        return jsonify(db_admin.query_sql(raw_sql, row_limit=500))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
