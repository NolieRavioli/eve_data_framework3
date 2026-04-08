# applications/task_viewer/routes.py
"""Task Manager blueprint — personal queue, admin queue, scheduler, and ESI explorer."""

from __future__ import annotations

from collections import Counter
import logging
import secrets

from flask import (
    Blueprint,
    abort,
    jsonify,
    render_template,
    request,
    session,
)

from applications._api import base_ctx, require_role, require_admin
from applications._api import queue_info, char_data, esi, esi_manifest, tokens, scheduler
from core.bus.websocket import register_websock

logger = logging.getLogger(__name__)

tasks_bp = Blueprint("task_viewer", __name__,
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

# Per-task log stream (ownership-checked — must stay as a focused endpoint)
register_websock(
    "/tasks/<task_id>/ws",
    lambda task_id: [f"task/{task_id}/log"],
    access_level="user",
    required_role="tasks",
    access_check=_task_ws_access,
)


# ── Personal tier ─────────────────────────────────────────────────────────────

@tasks_bp.route("/rate_stats")
@require_role("tasks")
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
@require_role("tasks")
def index():
    is_admin = bool(session.get("is_admin"))
    owner_id = session["owner_id"]
    tasks = queue_info.get_tasks_for_owner(owner_id)
    task_rows = [task.as_dict() for task in tasks]
    summary = Counter(task["status"] for task in task_rows)

    return render_template(
        "task_queue.html",
        **base_ctx("task_viewer"),
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
@require_role("tasks")
def task_detail(task_id: str):
    task = queue_info.get_task(task_id)
    if not task:
        abort(404)
    if not _owns_task(task):
        abort(403)

    return render_template(
        "task_detail.html",
        **base_ctx("task_viewer"),
        task=task.as_dict(),
    )


@tasks_bp.route("/<task_id>/cancel", methods=["POST"])
@require_role("tasks")
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
@require_role("tasks")
def clear_tasks():
    owner_id = session["owner_id"]
    is_admin = bool(session.get("is_admin"))
    cleared = queue_info.clear_tasks(None if is_admin else owner_id)
    return jsonify({"cleared": cleared})


# ── Admin tier ────────────────────────────────────────────────────────────────

@tasks_bp.route("/admin/")
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
        "task_admin.html",
        **base_ctx("task_viewer"),
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

@tasks_bp.route("/explore/")
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
        **base_ctx("task_viewer"),
        operations=ops,
        compatibility_date=meta["compatibility_date"],
        operation_count=meta["operation_count"],
        scope_count=meta["scope_count"],
        active_character_id=character_id,
        active_character_name=char_name,
    )


@tasks_bp.route("/explore/<operation_id>")
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
        **base_ctx("task_viewer"),
        op=op,
        op_json=_json.dumps(op),
    )


@tasks_bp.route("/explore/<operation_id>/run", methods=["POST"])
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
    except Exception:
        logger.exception("[ESI Explorer] Error running %s", operation_id)
        return jsonify({"error": "ESI operation failed. Check server logs for details."}), 500


# ── Scheduler ─────────────────────────────────────────────────────────────────

@tasks_bp.route("/scheduler/")
@require_admin
def scheduler_index():
    jobs = scheduler.list_jobs()
    csrf = secrets.token_urlsafe(32)
    session["scheduler_csrf"] = csrf
    return render_template(
        "scheduler.html",
        **base_ctx("task_viewer"),
        jobs=jobs,
        csrf_token=csrf,
    )


@tasks_bp.route("/scheduler/<job_id>")
@require_admin
def scheduler_detail(job_id: str):
    job = scheduler.get_job(job_id)
    if not job:
        abort(404)
    history = scheduler.get_run_history(job_id)
    csrf = secrets.token_urlsafe(32)
    session["scheduler_csrf"] = csrf
    return render_template(
        "scheduler_detail.html",
        **base_ctx("task_viewer"),
        job=job,
        history=history,
        csrf_token=csrf,
    )


def _check_scheduler_csrf():
    """Validate the CSRF token from the X-CSRF-Token header."""
    csrf = request.headers.get("X-CSRF-Token", "")
    expected = session.get("scheduler_csrf")
    if not csrf or not expected or csrf != expected:
        return jsonify({"error": "Invalid or missing CSRF token"}), 403
    return None


@tasks_bp.route("/scheduler/<job_id>/toggle", methods=["POST"])
@require_admin
def scheduler_toggle(job_id: str):
    err = _check_scheduler_csrf()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    enabled = bool(data.get("enabled", True))
    scheduler.set_enabled(job_id, enabled)
    return jsonify({"ok": True, "job_id": job_id, "enabled": enabled})


@tasks_bp.route("/scheduler/<job_id>/run", methods=["POST"])
@require_admin
def scheduler_run_now(job_id: str):
    err = _check_scheduler_csrf()
    if err:
        return err
    task_id = scheduler.run_now(job_id)
    return jsonify({"ok": True, "job_id": job_id, "task_id": task_id})


@tasks_bp.route("/scheduler/<job_id>/interval", methods=["POST"])
@require_admin
def scheduler_change_interval(job_id: str):
    err = _check_scheduler_csrf()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    interval_s = int(data.get("interval_s", 3600))
    scheduler.set_interval(job_id, interval_s)
    return jsonify({"ok": True, "job_id": job_id, "interval_s": interval_s})

