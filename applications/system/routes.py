# applications/system/routes.py
"""System Status blueprint — process health, git version, and live bus log viewer."""

from __future__ import annotations

import logging
import subprocess
import secrets

from flask import Blueprint, redirect, render_template, request, session, url_for

from applications._api import base_ctx, require_admin, tasks
from core.bus.process_pub import collect_process_snapshot
from core.bus.websocket import register_websock

logger = logging.getLogger(__name__)

sys_bp = Blueprint(
    "system",
    __name__,
    template_folder="templates",
    static_folder="static",
)

# Declare a focused push endpoint: publishes system/process metrics every 10 s.
register_websock(
    "/system/ws/process",
    ["system/process"],
    access_level="admin",
)


def _get_git_version() -> str | None:
    """Return the current git describe output, or None if git is unavailable."""
    try:
        out = subprocess.check_output(
            ["git", "describe", "--tags", "--always"],
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return out.decode().strip()
    except Exception:
        return None


@sys_bp.route("/")
@require_admin
def index():
    snapshot = collect_process_snapshot()
    from core.bus import get_all_topics as _topics

    # Generate a one-time token for the update confirmation
    update_token = secrets.token_urlsafe(32)
    session["system_update_token"] = update_token

    return render_template(
        "sys_status.html",
        process=snapshot,
        bus_topics=_topics(),
        git_version=_get_git_version(),
        update_token=update_token,
        **base_ctx("system"),
    )


@sys_bp.route("/update", methods=["POST"])
@require_admin
def update_system():
    """Git pull + pip install. Requires the CSRF-like confirmation token from the page."""
    import sys as _sys

    confirm_token = request.form.get("confirm_token", "")
    expected = session.pop("system_update_token", None)
    if not confirm_token or not expected or confirm_token != expected:
        return redirect(url_for("system.index"))

    def _do_update():
        subprocess.check_call(["git", "pull", "origin", "main"], timeout=120)
        subprocess.check_call(
            [_sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            timeout=300,
        )
        logger.info("System updated — manual restart required.")

    task_id = tasks.enqueue("System Update", _do_update, queue="public")
    return redirect(url_for("esi_viewer.task_detail", task_id=task_id))
