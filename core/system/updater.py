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

from datetime import UTC, datetime
import logging
import os
from pathlib import Path
import subprocess
import sys

logger = logging.getLogger(__name__)
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _git_call(*args: str, timeout: int = 30) -> None:
    """Run a git command from the repository root."""
    subprocess.check_call(["git", *args], cwd=_REPO_ROOT, timeout=timeout)


def _git_output(*args: str, timeout: int = 30) -> str:
    """Return stdout from a git command run at the repository root."""
    return subprocess.check_output(
        ["git", *args],
        cwd=_REPO_ROOT,
        timeout=timeout,
        text=True,
    ).strip()


def _working_tree_dirty() -> bool:
    """Return True when tracked or untracked files are present."""
    status = _git_output("status", "--porcelain", "--untracked-files=all", timeout=10)
    return bool(status)


def _latest_local_tag() -> str | None:
    """Return the newest semver-sorted local tag after fetch."""
    tags = _git_output("tag", "--sort=-version:refname", timeout=10)
    for tag in tags.splitlines():
        tag = tag.strip()
        if tag:
            return tag
    return None


def _current_git_version() -> str | None:
    """Return the current checkout description, if available."""
    try:
        return _git_output("describe", "--tags", "--always", timeout=10)
    except Exception:
        return None


def _stash_local_changes(target_ref: str) -> str | None:
    """Stash tracked and untracked changes before a forced checkout."""
    if not _working_tree_dirty():
        return None

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    message = f"system-update {target_ref} {stamp}"
    logger.warning("[updater] Local changes detected; stashing before update")
    _git_call("stash", "push", "--include-untracked", "-m", message, timeout=120)
    stash_ref = _git_output(
        "stash",
        "list",
        "--max-count=1",
        "--format=%gd: %gs",
        timeout=10,
    )
    if stash_ref:
        logger.warning("[updater] Created stash %s", stash_ref)
        return stash_ref
    logger.warning("[updater] Created stash with message %s", message)
    return message


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
            cwd=_REPO_ROOT,
            timeout=30,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        local = _git_output("rev-parse", "HEAD", timeout=10)
        remote = _git_output("rev-parse", "@{u}", timeout=10)
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
    _git_call("pull", "--ff-only", timeout=60)
    logger.info("[updater] Update applied. Restarting process...")
    restart_process()


def apply_release_update(target_ref: str | None = None) -> dict[str, str | bool | None]:
    """Fetch tags, stash local changes if needed, and force-checkout a release."""
    logger.info("[updater] Fetching origin tags...")
    _git_call("fetch", "--tags", "origin", timeout=60)

    tag = target_ref or _latest_local_tag()
    if tag:
        current_ref = _current_git_version()
        if current_ref == tag:
            logger.info("[updater] Already at release %s", tag)
            return {"target_ref": tag, "stashed": False, "stash_ref": None}
        stash_ref = _stash_local_changes(tag)
        logger.info("[updater] Checking out %s with --force", tag)
        _git_call("checkout", "--force", tag, timeout=30)
        return {"target_ref": tag, "stashed": bool(stash_ref), "stash_ref": stash_ref}

    logger.warning("[updater] No release tags found; falling back to origin/main")
    stash_ref = _stash_local_changes("origin/main")
    _git_call("pull", "--ff-only", "origin", "main", timeout=120)
    return {"target_ref": "origin/main", "stashed": bool(stash_ref), "stash_ref": stash_ref}


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
