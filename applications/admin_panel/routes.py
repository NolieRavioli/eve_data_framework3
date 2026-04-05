# applications/admin_panel/routes.py
"""Admin panel blueprint — live logs, DB stats, user management."""

from __future__ import annotations

import datetime
import json
import logging

from flask import (
    Blueprint,
    Response,
    jsonify,
    render_template,
    request,
    session,
)

from applications._api import require_admin, base_ctx, get_runtime_settings
from applications._api import db_admin, esi_registry

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__, template_folder="templates", static_folder="static")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_site_owner(owner_id: int) -> bool:
    row = db_admin.get_site_admin(owner_id)
    return bool(row and row.get("is_site_owner"))


def _db_stats() -> dict[str, int]:
    counts = db_admin.table_counts()
    return dict(sorted(counts.items(), key=lambda item: item[1], reverse=True))


def _normalize_user_row(row: dict) -> dict:
    granted_at = row.get("granted_at")
    if isinstance(granted_at, (datetime.datetime, datetime.date)):
        granted_at = granted_at.isoformat()
    return {
        "owner_id":        row["owner_id"],
        "character_count": int(row.get("character_count") or 0),
        "is_admin":        bool(row.get("is_admin")),
        "is_site_owner":   bool(row.get("is_site_owner")),
        "granted_at":      granted_at,
    }


def _user_list() -> list[dict]:
    return [_normalize_user_row(row) for row in db_admin.list_users()]


# ── Routes ────────────────────────────────────────────────────────────────────

@admin_bp.route("/")
@require_admin
def index():
    users        = _user_list()
    table_counts = _db_stats()
    sde_status   = db_admin.get_warehouse_status()
    esi_status   = esi_registry.get_status()
    stats = {
        "table_counts":     table_counts,
        "table_count":      len(table_counts),
        "table_total_rows": sum(table_counts.values()),
        "users":            users,
        "total_owners":     len(users),
        "admin_count":      sum(1 for row in users if row["is_admin"]),
        "sde_status":       sde_status,
        "esi_status":       esi_status,
    }
    return render_template(
        "admin.html",
        **base_ctx("admin_panel"),
        stats=stats,
        owner_id=session.get("owner_id"),
        is_site_owner=_is_site_owner(session.get("owner_id", 0)),
    )


@admin_bp.route("/users")
@require_admin
def users():
    return jsonify(_user_list())


@admin_bp.route("/promote", methods=["POST"])
@require_admin
def promote():
    data      = request.get_json(force=True, silent=True) or {}
    target_id = data.get("owner_id")
    if not target_id:
        return jsonify({"error": "owner_id required"}), 400

    current_owner = session.get("owner_id")
    existing      = db_admin.get_site_admin(int(target_id))
    if existing:
        return jsonify({"ok": True, "note": "already admin"})

    db_admin.upsert_site_admin(
        owner_id=int(target_id),
        is_site_owner=False,
        granted_by=current_owner,
        granted_at=datetime.datetime.utcnow(),
    )
    logger.info("[Admin] Owner %s promoted to admin by %s.", target_id, current_owner)
    return jsonify({"ok": True})


@admin_bp.route("/demote", methods=["POST"])
@require_admin
def demote():
    data      = request.get_json(force=True, silent=True) or {}
    target_id = data.get("owner_id")
    if not target_id:
        return jsonify({"error": "owner_id required"}), 400

    row = db_admin.get_site_admin(int(target_id))
    if not row:
        return jsonify({"ok": True, "note": "not an admin"})
    if row.get("is_site_owner"):
        return jsonify({"error": "Cannot demote the site owner."}), 403

    current_owner = session.get("owner_id")
    db_admin.delete_site_admin(int(target_id))
    logger.info("[Admin] Owner %s demoted by %s.", target_id, current_owner)
    return jsonify({"ok": True})
