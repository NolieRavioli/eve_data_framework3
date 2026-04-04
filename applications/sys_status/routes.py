# applications/sys_status/routes.py
"""System Status blueprint — page + SSE stream for DB and writer metrics."""

from __future__ import annotations

import json
import logging
import os
import time

from flask import Blueprint, Response, render_template

from applications._base import base_ctx, require_admin
from applications._adapters import (
    get_writer_stats,
    get_db_file_stats,
    queue_info,
    scheduler,
)

logger = logging.getLogger(__name__)

sys_bp = Blueprint(
    "sys_status",
    __name__,
    template_folder="templates",
    static_folder="static",
)

_STREAM_POLL_INTERVAL = 5.0  # seconds between SSE pushes
_KEEPALIVE_INTERVAL = 10.0   # seconds before sending a keepalive comment


def _collect_snapshot() -> dict:
    """Gather all metrics into a single serialisable dict."""
    writer = get_writer_stats()
    db_file = get_db_file_stats()

    all_tasks = queue_info.get_all_tasks()
    task_counts: dict[str, int] = {}
    queue_counts: dict[str, int] = {}
    for t in all_tasks:
        task_counts[t.status] = task_counts.get(t.status, 0) + 1
        queue_counts[t.queue] = queue_counts.get(t.queue, 0) + 1

    try:
        jobs = scheduler.list_jobs()
    except Exception:
        jobs = []

    process: dict = {
        "pid": os.getpid(),
        "memory_rss_mb": None,
    }
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        process["memory_rss_mb"] = round(proc.memory_info().rss / (1024 * 1024), 1)
    except ImportError:
        pass

    # Convert monotonic timestamp to seconds-ago for the client
    last_cp = writer.get("last_checkpoint_at")
    writer["last_checkpoint_seconds_ago"] = (
        round(time.monotonic() - last_cp, 1) if last_cp is not None else None
    )

    return {
        "writer": writer,
        "db_file": db_file,
        "task_counts": task_counts,
        "queue_counts": queue_counts,
        "jobs": jobs,
        "process": process,
    }


@sys_bp.route("/")
@require_admin
def index():
    snapshot = _collect_snapshot()
    return render_template(
        "sys_status.html",
        snapshot=snapshot,
        **base_ctx("sys_status"),
    )


@sys_bp.route("/stream")
@require_admin
def stream():
    """SSE endpoint — pushes a JSON snapshot every 5 s; keepalive every 10 s."""

    def _generate():
        last_payload: str | None = None
        last_push = time.monotonic()

        while True:
            snap = _collect_snapshot()
            payload = json.dumps(snap, default=str)
            now = time.monotonic()

            if payload != last_payload:
                last_payload = payload
                last_push = now
                yield f"data: {payload}\n\n"
            elif (now - last_push) >= _KEEPALIVE_INTERVAL:
                last_push = now
                yield ": keepalive\n\n"

            time.sleep(_STREAM_POLL_INTERVAL)

    return Response(
        _generate(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
