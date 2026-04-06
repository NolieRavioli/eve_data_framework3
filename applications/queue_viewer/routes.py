# applications/queue_viewer/routes.py
"""Queue Viewer blueprint — progress view, list, cancel, and clear."""

from __future__ import annotations

from collections import Counter
import logging

from flask import Blueprint, abort, jsonify, render_template, session

from applications._api import base_ctx, require_role
from applications._api import queue_info, char_data
from core.bus.websocket import register_websock

logger = logging.getLogger(__name__)
tasks_bp = Blueprint("queue_viewer", __name__, template_folder="templates", static_folder="static")


def _owns_task(task) -> bool:
    """True if the current user owns the task or is an admin."""
    return task.owner_id == session.get("owner_id") or bool(session.get("is_admin"))


def _task_ws_access(task_id: str) -> bool:
    """access_check for the per-task WebSocket — enforces task ownership."""
    task = queue_info.get_task(task_id)
    if task is None:
        return False
    return _owns_task(task)


# ── Focused WebSocket endpoints ───────────────────────────────────────────────
# ESI rate + task-list: auto-subscribers receive live pushes from the bus.
register_websock(
    "/queue/ws/rate",
    ["esi/rate", "queue/tasks"],
    access_level="user",
    required_role="queue",
)

# Per-task log stream: dynamic topic, with ownership access check.
register_websock(
    "/queue/<task_id>/ws",
    lambda task_id: [f"task/{task_id}/log"],
    access_level="user",
    required_role="queue",
    access_check=_task_ws_access,
)


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


@tasks_bp.route("/rate_stats")
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


@tasks_bp.route("/")
@require_role("queue")
def esi_queue_list():
    is_admin = bool(session.get("is_admin"))
    owner_id = session["owner_id"]
    tasks    = queue_info.get_all_tasks() if is_admin else queue_info.get_tasks_for_owner(owner_id)
    task_rows = [task.as_dict() for task in tasks]
    summary   = Counter(task["status"] for task in task_rows)

    return render_template(
        "esi_queue_list.html",
        **base_ctx("queue_viewer"),
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


@tasks_bp.route("/<task_id>")
@require_role("queue")
def esi_queue_progress(task_id: str):
    task = queue_info.get_task(task_id)
    if not task:
        abort(404)
    if not _owns_task(task):
        abort(403)

    return render_template(
        "esi_queue_progress.html",
        **base_ctx("queue_viewer"),
        task=task.as_dict(),
    )


@tasks_bp.route("/<task_id>/cancel", methods=["POST"])
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


@tasks_bp.route("/clear", methods=["POST"])
@require_role("queue")
def clear_tasks():
    owner_id = session["owner_id"]
    is_admin = bool(session.get("is_admin"))
    cleared  = queue_info.clear_tasks(None if is_admin else owner_id)
    return jsonify({"cleared": cleared})
