# applications/sys_status/routes.py
"""System Status blueprint — process health and live bus log viewer."""

from __future__ import annotations

import logging
import os
import threading

from flask import Blueprint, jsonify, render_template

from applications._base import base_ctx, require_admin

logger = logging.getLogger(__name__)

sys_bp = Blueprint(
    "sys_status",
    __name__,
    template_folder="templates",
    static_folder="static",
)


def _collect_process_snapshot() -> dict:
    """Gather process-level metrics only."""
    process: dict = {
        "pid": os.getpid(),
        "memory_rss_mb": None,
        "thread_count": threading.active_count(),
    }
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        process["memory_rss_mb"] = round(mem.rss / (1024 * 1024), 1)
        process["cpu_percent"] = proc.cpu_percent(interval=0)
    except ImportError:
        pass
    return process


@sys_bp.route("/")
@require_admin
def index():
    snapshot = _collect_process_snapshot()
    from core.bus import get_all_topics as _topics
    return render_template(
        "sys_status.html",
        process=snapshot,
        bus_topics=_topics(),
        **base_ctx("sys_status"),
    )


@sys_bp.route("/api/process")
@require_admin
def api_process():
    """REST endpoint — returns current process stats."""
    return jsonify(_collect_process_snapshot())

