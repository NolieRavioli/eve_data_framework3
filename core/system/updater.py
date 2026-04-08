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
    """Restart the current process with a fresh invocation of the same command.

    On Windows, spawns a child process in the same console (so Ctrl+C works)
    then force-exits.  Lifecycle shutdown is called first so DuckDB and all
    managed threads are released cleanly before the new process starts.
    On Linux/macOS, uses ``os.execv`` to atomically replace the process.
    """
    # Gracefully stop all managed threads (db-writer, scheduler, stats, etc.)
    # *before* spawning the replacement process so DuckDB file locks and the
    # listening port are fully released.
    try:
        from core.system import get_lifecycle
        get_lifecycle().shutdown()
    except Exception:
        logger.warning("[updater] Lifecycle shutdown failed — continuing restart")

    logger.info("[updater] Restarting: %s %s", sys.executable, " ".join(sys.argv))
    if os.name == "nt":
        import subprocess as _sp
        env = os.environ.copy()
        env["_EVE_RESTART_DELAY"] = "1"  # new process waits for port release
        _sp.Popen(
            [sys.executable, *sys.argv],
            env=env,
            creationflags=_sp.CREATE_NEW_PROCESS_GROUP,
        )
        os._exit(0)
    else:
        os.execv(sys.executable, [sys.executable, *sys.argv])


def get_latest_github_release() -> str | None:
    """Fetch the latest release tag from GitHub.

    Returns the ``tag_name`` string (e.g. ``'v0.2.1'``) or ``None`` if the
    request fails for any reason (network error, rate-limited, private repo,
    parse error).
    """
    import requests
    try:
        resp = requests.get(
            "https://api.github.com/repos/NolieRavioli/eve_data_framework3/releases/latest",
            headers={"User-Agent": "eve-data-framework"},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json().get("tag_name")
    except Exception:
        pass
    return None
