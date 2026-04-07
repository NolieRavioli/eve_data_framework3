"""Self-update and process restart mechanism.

Provides helpers to check for upstream changes, pull updates, and restart
the running process cleanly.

Usage
-----
    from core.system.updater import check_for_updates, apply_update

    status = check_for_updates()
    if status["updates_available"]:
        apply_update()  # pulls + restarts
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)


def check_for_updates() -> dict:
    """Check the git remote for new commits.

    Returns
    -------
    dict
        ``{"updates_available": bool, "local_ref": str, "remote_ref": str, "error": str | None}``
    """
    try:
        subprocess.check_call(
            ["git", "fetch", "--quiet"],
            timeout=30,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        local = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            timeout=10,
        ).decode().strip()
        remote = subprocess.check_output(
            ["git", "rev-parse", "@{u}"],
            timeout=10,
        ).decode().strip()
        return {
            "updates_available": local != remote,
            "local_ref": local,
            "remote_ref": remote,
            "error": None,
        }
    except Exception as exc:
        return {
            "updates_available": False,
            "local_ref": "",
            "remote_ref": "",
            "error": str(exc),
        }


def apply_update() -> None:
    """Pull latest changes and restart the process.

    Calls ``git pull --ff-only`` and then replaces the current process
    via ``os.execv``.
    """
    logger.info("[updater] Pulling latest changes...")
    subprocess.check_call(["git", "pull", "--ff-only"], timeout=60)
    logger.info("[updater] Update applied. Restarting process...")
    restart_process()


def restart_process() -> None:
    """Replace the current process with a fresh invocation of the same command.

    Uses ``os.execv()`` so the PID stays the same and the calling shell
    sees a seamless restart.
    """
    logger.info("[updater] Restarting: %s %s", sys.executable, " ".join(sys.argv))
    os.execv(sys.executable, [sys.executable, *sys.argv])
