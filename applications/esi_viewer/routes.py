# applications/esi_viewer/routes.py
"""ESI Viewer blueprint — personal queue, admin queue, and ESI operation explorer."""

from __future__ import annotations

from collections import Counter
import logging

from flask import (
    Blueprint,
    abort,
    jsonify,
    render_template,
    request,
    session,
)

from applications._api import base_ctx, require_role, require_admin
from applications._api import queue_info, char_data, esi, esi_manifest, tokens
from core.bus.websocket import register_websock

logger = logging.getLogger(__name__)

esi_bp = Blueprint("esi_viewer", __name__,
                   template_folder="templates",
                   static_folder="static")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _owns_task(task) -> bool:
    """True if the current user owns the task or is an admin."""
    return task.owner_id == session.get("owner_id") or bool(session.get("is_admin"))


def _task_ws_access(task_id: str) -> bool:
    """access_check for the per-task WebSocket — enforces task ownership."""
    task = queue_info.get_task(task_id)
    if task is None:
        return False
    return _owns_task(task)


def _make_char_name_lookup():
    """Return a closure that maps owner_id → character name (cached for connection lifetime)."""
    _cache: dict[int, str] = {}

    def _lookup(owner_id: int) -> str:
        if owner_id in _cache:
            return _cache[owner_id]
        if not owner_id:
            _cache[owner_id] = ""
            return ""
        try:
            chars = char_data.get_characters(owner_id)
            name = chars[0]["name"] if chars else str(owner_id)
        except Exception:
            name = str(owner_id)
        _cache[owner_id] = name
        return name

    return _lookup


# ── Focused WebSocket endpoints ───────────────────────────────────────────────

# Personal tier: owner-filtered rate + task events
register_websock(
    "/esi/ws/rate",
    ["esi/rate", "queue/tasks"],
    access_level="user",
    required_role="queue",
)

# Per-task log stream
register_websock(
    "/esi/<task_id>/ws",
    lambda task_id: [f"task/{task_id}/log"],
    access_level="user",
    required_role="queue",
    access_check=_task_ws_access,
)

# Admin tier: unfiltered rate + task events
register_websock(
    "/esi/admin/ws",
    ["esi/rate", "queue/tasks"],
    access_level="admin",
)


# ── Personal tier ─────────────────────────────────────────────────────────────

@esi_bp.route("/rate_stats")
@require_role("queue")
def rate_stats():
    """Return current ESI rate-limiter snapshot as JSON (kept for scripting)."""
    stats = queue_info.get_esi_rate_stats()
    running = [
        {"task_id": t.task_id, "name": t.name, "esi_rate": t.esi_rate}
        for t in queue_info.get_all_tasks()
        if t.status == "running" and t.esi_rate
    ]
    return jsonify({"limiter": stats, "running_tasks": running})


@esi_bp.route("/")
@require_role("queue")
def index():
    is_admin = bool(session.get("is_admin"))
    owner_id = session["owner_id"]
    tasks = queue_info.get_all_tasks() if is_admin else queue_info.get_tasks_for_owner(owner_id)
    task_rows = [task.as_dict() for task in tasks]
    summary = Counter(task["status"] for task in task_rows)

    return render_template(
        "esi_index.html",
        **base_ctx("esi_viewer"),
        tasks=task_rows,
        is_admin=is_admin,
        task_summary={
            "running":   summary.get("running", 0),
            "pending":   summary.get("pending", 0),
            "complete":  summary.get("complete", 0),
            "failed":    summary.get("failed", 0),
            "cancelled": summary.get("cancelled", 0),
            "total":     len(task_rows),
        },
    )


@esi_bp.route("/<task_id>")
@require_role("queue")
def task_detail(task_id: str):
    task = queue_info.get_task(task_id)
    if not task:
        abort(404)
    if not _owns_task(task):
        abort(403)

    return render_template(
        "esi_task.html",
        **base_ctx("esi_viewer"),
        task=task.as_dict(),
    )


@esi_bp.route("/<task_id>/cancel", methods=["POST"])
@require_role("queue")
def cancel_task(task_id: str):
    task = queue_info.get_task(task_id)
    if not task:
        abort(404)
    if not _owns_task(task):
        abort(403)

    ok = queue_info.cancel_task(task_id)
    return jsonify({
        "cancelled": ok,
        "status":    task.status,
        "message":   None if ok else "Only pending tasks can be cancelled.",
    })


@esi_bp.route("/clear", methods=["POST"])
@require_role("queue")
def clear_tasks():
    owner_id = session["owner_id"]
    is_admin = bool(session.get("is_admin"))
    cleared = queue_info.clear_tasks(None if is_admin else owner_id)
    return jsonify({"cleared": cleared})


# ── Admin tier ────────────────────────────────────────────────────────────────

@esi_bp.route("/admin/")
@require_admin
def admin_index():
    all_tasks = queue_info.get_all_tasks()
    task_rows = [task.as_dict() for task in all_tasks]
    summary = Counter(t["status"] for t in task_rows)

    # Group tasks by owner_id for the per-owner breakdown
    owner_groups: dict[int, list[dict]] = {}
    for t in task_rows:
        owner_groups.setdefault(t.get("owner_id", 0), []).append(t)

    char_name = _make_char_name_lookup()
    owners = [
        {
            "owner_id": oid,
            "name": char_name(oid),
            "tasks": tasks_list,
            "running": sum(1 for t in tasks_list if t["status"] == "running"),
            "pending": sum(1 for t in tasks_list if t["status"] == "pending"),
        }
        for oid, tasks_list in sorted(owner_groups.items())
    ]

    return render_template(
        "esi_admin.html",
        **base_ctx("esi_viewer"),
        tasks=task_rows,
        owners=owners,
        task_summary={
            "running":   summary.get("running", 0),
            "pending":   summary.get("pending", 0),
            "complete":  summary.get("complete", 0),
            "failed":    summary.get("failed", 0),
            "cancelled": summary.get("cancelled", 0),
            "total":     len(task_rows),
        },
    )


# ── Explorer ──────────────────────────────────────────────────────────────────

@esi_bp.route("/explore/")
@require_admin
def explore_index():
    ops = esi_manifest.get_operations()
    meta = esi_manifest.get_meta()

    char_name: str | None = None
    character_id = session.get("character_id")
    owner_id = session.get("owner_id")
    if character_id and owner_id:
        info = char_data.get_character(owner_id, character_id)
        if info:
            char_name = info.get("name")

    return render_template(
        "esi_explore.html",
        **base_ctx("esi_viewer"),
        operations=ops,
        compatibility_date=meta["compatibility_date"],
        operation_count=meta["operation_count"],
        scope_count=meta["scope_count"],
        active_character_id=character_id,
        active_character_name=char_name,
    )


@esi_bp.route("/explore/<operation_id>")
@require_admin
def explore_detail(operation_id: str):
    """Operation detail — JSON if Accept requests it, HTML page otherwise."""
    op = esi_manifest.get_operation(operation_id)
    if not op:
        abort(404)

    # AJAX calls from the explorer sidebar still get JSON
    if request.accept_mimetypes.best == "application/json" or request.args.get("format") == "json":
        return jsonify(op)

    import json as _json
    return render_template(
        "esi_operation.html",
        **base_ctx("esi_viewer"),
        op=op,
        op_json=_json.dumps(op),
    )


@esi_bp.route("/explore/<operation_id>/run", methods=["POST"])
@require_admin
def explore_run(operation_id: str):
    """Execute an ESI operation and return the response as JSON."""
    op = esi_manifest.get_operation(operation_id)
    if not op:
        return jsonify({"error": f"Unknown operation: {operation_id!r}"}), 404

    data = request.get_json(force=True, silent=True) or {}
    path_params = data.get("path_params") or {}
    query_params = data.get("query_params") or {}
    all_pages = bool(data.get("all_pages", False))

    token = None
    if op.get("requires_auth"):
        owner_id = session.get("owner_id")
        character_id = session.get("character_id")
        if owner_id and character_id:
            try:
                token_map = tokens.get(owner_id, character_ids=[character_id])
                row = token_map.get(character_id)
                if row:
                    token = row["access_token"]
            except Exception:
                pass
        if not token:
            return jsonify({"error": "Authentication required but no valid token is available for your session."}), 401

    try:
        if all_pages and op.get("pagination", {}).get("has_page_param"):
            result = esi.fetch_pages(
                operation_id,
                path_params=path_params or None,
                query_params=query_params or None,
                token=token,
            )
            return jsonify({
                "ok": True,
                "operation_id": operation_id,
                "all_pages": True,
                "count": len(result) if isinstance(result, list) else None,
                "data": result,
            })
        else:
            r = esi.execute(
                operation_id,
                path_params=path_params or None,
                query_params=query_params or None,
                token=token,
            )
            return jsonify({
                "ok": True,
                "operation_id": operation_id,
                "status_code": r["status_code"],
                "headers": {k: v for k, v in r["headers"].items()
                            if k.lower().startswith(("x-", "content-", "expires", "etag"))},
                "data": r["body"],
            })
    except Exception as exc:
        logger.exception("[ESI Explorer] Error running %s", operation_id)
        return jsonify({"error": str(exc)}), 500
