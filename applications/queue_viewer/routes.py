# applications/queue_viewer/routes.py
"""Queue Viewer blueprint — progress view, list, cancel, clear, and ESI rate SSE."""

from __future__ import annotations

from collections import Counter
import logging

from flask import Blueprint, Response, abort, jsonify, render_template, session

from applications._base import base_ctx, require_role
from applications._adapters import queue_info

logger = logging.getLogger(__name__)
tasks_bp = Blueprint("queue_viewer", __name__, template_folder="templates", static_folder="static")


def _owns_task(task) -> bool:
    """True if the current user owns the task or is an admin."""
    return task.owner_id == session.get("owner_id") or bool(session.get("is_admin"))


@tasks_bp.route("/rate_stats")
@require_role("queue")
def rate_stats():
    """Return current ESI rate-limiter snapshot as JSON."""
    stats = queue_info.get_esi_rate_stats()
    running = [
        {"task_id": t.task_id, "name": t.name, "esi_rate": t.esi_rate}
        for t in queue_info.get_all_tasks()
        if t.status == "running" and t.esi_rate
    ]
    return jsonify({"limiter": stats, "running_tasks": running})


@tasks_bp.route("/rate_stream")
@require_role("queue")
def rate_stream():
    """SSE endpoint that streams ESI rate-limiter stats on every request."""
    return Response(
        queue_info.rate_stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@tasks_bp.route("/")
@require_role("queue")
def task_list():
    is_admin = bool(session.get("is_admin"))
    owner_id = session["owner_id"]
    tasks    = queue_info.get_all_tasks() if is_admin else queue_info.get_tasks_for_owner(owner_id)
    task_rows = [task.as_dict() for task in tasks]
    summary   = Counter(task["status"] for task in task_rows)

    return render_template(
        "task_list.html",
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
def task_progress(task_id: str):
    task = queue_info.get_task(task_id)
    if not task:
        abort(404)
    if not _owns_task(task):
        abort(403)

    return render_template(
        "task_progress.html",
        **base_ctx("queue_viewer"),
        task=task.as_dict(),
    )


@tasks_bp.route("/<task_id>/stream")
@require_role("queue")
def task_stream(task_id: str):
    """SSE endpoint that streams log lines for a task."""
    task = queue_info.get_task(task_id)
    if not task:
        abort(404)
    if not _owns_task(task):
        abort(403)

    return Response(
        queue_info.log_stream(task_id),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
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
