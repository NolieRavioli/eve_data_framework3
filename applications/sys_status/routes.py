# applications/sys_status/routes.py
"""System Status blueprint — process health and live bus log viewer."""

from __future__ import annotations

import logging

from flask import Blueprint, render_template

from applications._api import base_ctx, require_admin
from core.bus.process_pub import collect_process_snapshot
from core.bus.websocket import register_websock

logger = logging.getLogger(__name__)

sys_bp = Blueprint(
    "sys_status",
    __name__,
    template_folder="templates",
    static_folder="static",
)

# Declare a focused push endpoint: publishes system/process metrics every 10 s.
register_websock(
    "/admin/sys_status/ws/process",
    ["system/process"],
    access_level="admin",
)


@sys_bp.route("/")
@require_admin
def index():
    snapshot = collect_process_snapshot()
    from core.bus import get_all_topics as _topics
    return render_template(
        "sys_status.html",
        process=snapshot,
        bus_topics=_topics(),
        **base_ctx("sys_status"),
    )

