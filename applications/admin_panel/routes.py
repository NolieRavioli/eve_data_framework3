# applications/admin_panel/routes.py
"""Admin panel blueprint — user management, privilege control, system overview."""

from __future__ import annotations

import datetime
import logging

from flask import (
    Blueprint,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from applications._api import require_admin, base_ctx
from applications._api import db_admin, esi_registry, char_data

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__, template_folder="templates", static_folder="static")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_site_owner(owner_id: int) -> bool:
    row = db_admin.get_site_admin(owner_id)
    return bool(row and row.get("is_site_owner"))


def _require_site_owner():
    """Abort 403 unless the current user is the site owner."""
    if not _is_site_owner(session.get("owner_id", 0)):
        abort(403)


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


# ── Dashboard ─────────────────────────────────────────────────────────────────

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
        "total_owners":     len(users),
        "admin_count":      sum(1 for u in users if u["is_admin"]),
        "role_count":       sum(len(db_admin.get_user_roles(u["owner_id"])) for u in users),
        "sde_status":       sde_status,
        "esi_status":       esi_status,
    }
    return render_template(
        "admin_index.html",
        **base_ctx("admin_panel"),
        stats=stats,
    )


# ── User list ─────────────────────────────────────────────────────────────────

@admin_bp.route("/users")
@require_admin
def users():
    user_rows = _user_list()
    for u in user_rows:
        u["roles"] = db_admin.get_user_roles(u["owner_id"])
    return render_template(
        "admin_users.html",
        **base_ctx("admin_panel"),
        users=user_rows,
    )


@admin_bp.route("/users/json")
@require_admin
def users_json():
    return jsonify(_user_list())


# ── User detail ───────────────────────────────────────────────────────────────

@admin_bp.route("/users/<int:owner_id>")
@require_admin
def user_detail(owner_id: int):
    all_users = _user_list()
    user = next((u for u in all_users if u["owner_id"] == owner_id), None)
    if not user:
        abort(404)

    roles = db_admin.get_user_roles(owner_id)
    characters = char_data.get_characters(owner_id)

    return render_template(
        "admin_user_detail.html",
        **base_ctx("admin_panel"),
        user=user,
        roles=roles,
        characters=characters,
    )


# ── Role management ──────────────────────────────────────────────────────────

@admin_bp.route("/users/<int:owner_id>/roles", methods=["POST"])
@require_admin
def manage_roles(owner_id: int):
    data = request.get_json(force=True, silent=True) or {}
    action = data.get("action")
    role = data.get("role", "").strip()

    if not role or action not in ("grant", "revoke"):
        return jsonify({"error": "action (grant|revoke) and role required"}), 400

    if action == "grant":
        db_admin.grant_user_roles(owner_id, [role], granted_by=session.get("owner_id"))
        logger.info("[Admin] Role %r granted to %s by %s.", role, owner_id, session.get("owner_id"))
    else:
        db_admin.revoke_user_role(owner_id, role)
        logger.info("[Admin] Role %r revoked from %s by %s.", role, owner_id, session.get("owner_id"))

    return jsonify({"ok": True, "action": action, "role": role})


# ── Admin toggle ──────────────────────────────────────────────────────────────

@admin_bp.route("/users/<int:owner_id>/admin", methods=["POST"])
@require_admin
def toggle_admin(owner_id: int):
    data = request.get_json(force=True, silent=True) or {}
    action = data.get("action")

    if action not in ("promote", "demote"):
        return jsonify({"error": "action must be 'promote' or 'demote'"}), 400

    current_owner = session.get("owner_id")

    if action == "promote":
        existing = db_admin.get_site_admin(owner_id)
        if existing:
            return jsonify({"ok": True, "note": "already admin"})
        if not _is_site_owner(current_owner):
            return jsonify({"error": "Only site owner can promote."}), 403
        db_admin.upsert_site_admin(
            owner_id=owner_id,
            is_site_owner=False,
            granted_by=current_owner,
            granted_at=datetime.datetime.utcnow(),
        )
        logger.info("[Admin] Owner %s promoted to admin by %s.", owner_id, current_owner)
    else:
        row = db_admin.get_site_admin(owner_id)
        if not row:
            return jsonify({"ok": True, "note": "not an admin"})
        if row.get("is_site_owner"):
            return jsonify({"error": "Cannot demote the site owner."}), 403
        if not _is_site_owner(current_owner):
            return jsonify({"error": "Only site owner can demote."}), 403
        db_admin.delete_site_admin(owner_id)
        logger.info("[Admin] Owner %s demoted by %s.", owner_id, current_owner)

    return jsonify({"ok": True})


# ── User deletion ─────────────────────────────────────────────────────────────

@admin_bp.route("/users/<int:owner_id>/delete", methods=["POST"])
@require_admin
def delete_user(owner_id: int):
    _require_site_owner()

    if owner_id == session.get("owner_id"):
        return jsonify({"error": "Cannot delete yourself."}), 400

    if _is_site_owner(owner_id):
        return jsonify({"error": "Cannot delete the site owner."}), 403

    db_admin.delete_user(owner_id)
    logger.info("[Admin] User %s deleted by %s.", owner_id, session.get("owner_id"))
    return jsonify({"ok": True})


# ── Legacy JSON endpoints (backward compat) ──────────────────────────────────

@admin_bp.route("/promote", methods=["POST"])
@require_admin
def promote():
    data = request.get_json(force=True, silent=True) or {}
    target_id = data.get("owner_id")
    if not target_id:
        return jsonify({"error": "owner_id required"}), 400
    return toggle_admin.__wrapped__(int(target_id)) if hasattr(toggle_admin, '__wrapped__') else _legacy_promote(int(target_id))


@admin_bp.route("/demote", methods=["POST"])
@require_admin
def demote():
    data = request.get_json(force=True, silent=True) or {}
    target_id = data.get("owner_id")
    if not target_id:
        return jsonify({"error": "owner_id required"}), 400
    return _legacy_demote(int(target_id))


def _legacy_promote(target_id: int):
    current_owner = session.get("owner_id")
    existing = db_admin.get_site_admin(target_id)
    if existing:
        return jsonify({"ok": True, "note": "already admin"})
    db_admin.upsert_site_admin(
        owner_id=target_id,
        is_site_owner=False,
        granted_by=current_owner,
        granted_at=datetime.datetime.utcnow(),
    )
    logger.info("[Admin] Owner %s promoted to admin by %s.", target_id, current_owner)
    return jsonify({"ok": True})


def _legacy_demote(target_id: int):
    row = db_admin.get_site_admin(target_id)
    if not row:
        return jsonify({"ok": True, "note": "not an admin"})
    if row.get("is_site_owner"):
        return jsonify({"error": "Cannot demote the site owner."}), 403
    current_owner = session.get("owner_id")
    db_admin.delete_site_admin(target_id)
    logger.info("[Admin] Owner %s demoted by %s.", target_id, current_owner)
    return jsonify({"ok": True})
