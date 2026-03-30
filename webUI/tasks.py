# webUI/tasks.py
"""Task management blueprint for progress view, list, cancel, and clear."""

from collections import Counter
import logging

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, session, url_for

from tasks import task_queue
from esi.rate_limiter import get_esi_rate_limiter
from webUI.context import base_ctx

logger = logging.getLogger(__name__)
tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")


def _logged_in() -> bool:
    return "owner_id" in session


def _login_redirect():
    return redirect(url_for("auth.login"))


def _owns_task(task) -> bool:
    """True if the current user owns the task or is an admin."""

    return task.owner_id == session.get("owner_id") or bool(session.get("is_admin"))


@tasks_bp.route("/rate_stats")
def rate_stats():
    """Return current ESI rate-limiter snapshot as JSON."""
    if not _logged_in():
        abort(403)
    stats = get_esi_rate_limiter().get_stats()
    running = [
        {"task_id": t.task_id, "name": t.name, "esi_rate": t.esi_rate}
        for t in task_queue.get_all_tasks()
        if t.status == "running" and t.esi_rate
    ]
    return jsonify({"limiter": stats, "running_tasks": running})


@tasks_bp.route("/rate_stream")
def rate_stream():
    """SSE endpoint that streams ESI rate-limiter stats on every request."""
    if not _logged_in():
        abort(403)
    return Response(
        task_queue.rate_stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@tasks_bp.route("/")
def task_list():
    if not _logged_in():
        return _login_redirect()

    is_admin = bool(session.get("is_admin"))
    owner_id = session["owner_id"]
    tasks = task_queue.get_all_tasks() if is_admin else task_queue.get_tasks_for_owner(owner_id)
    task_rows = [task.as_dict() for task in tasks]
    summary = Counter(task["status"] for task in task_rows)

    return render_template(
        "task_list.html",
        **base_ctx("tasks"),
        tasks=task_rows,
        is_admin=is_admin,
        task_summary={
            "running": summary.get("running", 0),
            "pending": summary.get("pending", 0),
            "complete": summary.get("complete", 0),
            "failed": summary.get("failed", 0),
            "cancelled": summary.get("cancelled", 0),
            "total": len(task_rows),
        },
    )


@tasks_bp.route("/<task_id>")
def task_progress(task_id: str):
    if not _logged_in():
        return _login_redirect()

    task = task_queue.get_task(task_id)
    if not task:
        abort(404)
    if not _owns_task(task):
        abort(403)

    return render_template(
        "task_progress.html",
        **base_ctx("tasks"),
        task=task.as_dict(),
    )


@tasks_bp.route("/<task_id>/stream")
def task_stream(task_id: str):
    """SSE endpoint that streams log lines for a task."""

    if not _logged_in():
        abort(403)

    task = task_queue.get_task(task_id)
    if not task:
        abort(404)
    if not _owns_task(task):
        abort(403)

    return Response(
        task_queue.log_stream(task_id),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@tasks_bp.route("/<task_id>/cancel", methods=["POST"])
def cancel_task(task_id: str):
    if not _logged_in():
        abort(403)

    task = task_queue.get_task(task_id)
    if not task:
        abort(404)
    if not _owns_task(task):
        abort(403)

    ok = task_queue.cancel_task(task_id)
    return jsonify(
        {
            "cancelled": ok,
            "status": task.status,
            "message": None if ok else "Only pending tasks can be cancelled.",
        }
    )


@tasks_bp.route("/clear", methods=["POST"])
def clear_tasks():
    if not _logged_in():
        abort(403)

    owner_id = session["owner_id"]
    is_admin = bool(session.get("is_admin"))
    cleared = task_queue.clear_tasks(None if is_admin else owner_id)
    return jsonify({"cleared": cleared})
