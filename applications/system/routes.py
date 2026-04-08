# applications/system/routes.py
"""System Status blueprint — process health, git version, and live bus log viewer."""

from __future__ import annotations

import logging
import subprocess
import secrets

from flask import Blueprint, redirect, render_template, request, session, url_for

from flask import jsonify

from applications._api import base_ctx, require_admin, tasks, system_bootstrap
from core.bus.process_pub import collect_process_snapshot
from core.system.updater import get_latest_github_release

logger = logging.getLogger(__name__)

sys_bp = Blueprint(
    "system",
    __name__,
    template_folder="templates",
    static_folder="static",
)

# WebSocket for this blueprint is handled by the shared /bus endpoint.
# Clients subscribe to "system/process" via the /bus protocol.


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

    # Generate one-time CSRF tokens for each destructive action
    update_token = secrets.token_urlsafe(32)
    sde_token = secrets.token_urlsafe(32)
    esi_token = secrets.token_urlsafe(32)
    config_token = secrets.token_urlsafe(32)
    session["system_update_token"] = update_token
    session["system_sde_token"] = sde_token
    session["system_esi_token"] = esi_token
    session["system_config_token"] = config_token

    git_version = _get_git_version()
    latest_release = get_latest_github_release()
    update_available = bool(latest_release and latest_release != git_version)

    return render_template(
        "sys_status.html",
        process=snapshot,
        bus_topics=_topics(),
        git_version=git_version,
        latest_release=latest_release,
        update_available=update_available,
        update_token=update_token,
        sde_token=sde_token,
        esi_token=esi_token,
        config_token=config_token,
        subsystems=system_bootstrap.get_status(),
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
        from core.system.updater import restart_process
        subprocess.check_call(["git", "fetch", "--tags", "origin"], timeout=60)
        try:
            tag = subprocess.check_output(
                ["git", "tag", "--sort=-version:refname"],
                timeout=10,
            ).decode().strip().split("\n")[0]
        except Exception:
            tag = ""
        if tag:
            subprocess.check_call(["git", "checkout", tag], timeout=30)
            logger.info("System updated to tag %s — restarting...", tag)
        else:
            logger.warning("[Update] No release tags found — falling back to origin/main")
            subprocess.check_call(["git", "pull", "origin", "main"], timeout=120)
            logger.info("System updated to latest main — restarting...")
        subprocess.check_call(
            [_sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            timeout=300,
        )
        restart_process()

    task_id = tasks.enqueue("System Update", _do_update, queue="public")
    return redirect(url_for("task_viewer.task_detail", task_id=task_id))


@sys_bp.route("/status/subsystems")
@require_admin
def subsystem_status():
    """JSON endpoint returning current subsystem status."""
    return jsonify(system_bootstrap.get_status())


@sys_bp.route("/update/sde", methods=["POST"])
@require_admin
def update_sde():
    """Enqueue a full SDE update. Requires CSRF token."""
    confirm_token = request.form.get("confirm_token", "")
    expected = session.pop("system_sde_token", None)
    if not confirm_token or not expected or confirm_token != expected:
        return redirect(url_for("system.index"))
    task_id = system_bootstrap.update_sde()
    return redirect(url_for("task_viewer.task_detail", task_id=task_id))


@sys_bp.route("/update/esi", methods=["POST"])
@require_admin
def update_esi():
    """Enqueue an ESI spec + codegen update. Requires CSRF token."""
    confirm_token = request.form.get("confirm_token", "")
    expected = session.pop("system_esi_token", None)
    if not confirm_token or not expected or confirm_token != expected:
        return redirect(url_for("system.index"))
    task_id = system_bootstrap.update_esi()
    return redirect(url_for("task_viewer.task_detail", task_id=task_id))


@sys_bp.route("/update/config", methods=["POST"])
@require_admin
def update_config():
    """Enqueue regeneration of example.config.yaml. Requires CSRF token."""
    confirm_token = request.form.get("confirm_token", "")
    expected = session.pop("system_config_token", None)
    if not confirm_token or not expected or confirm_token != expected:
        return redirect(url_for("system.index"))
    task_id = system_bootstrap.update_config()
    return redirect(url_for("task_viewer.task_detail", task_id=task_id))
