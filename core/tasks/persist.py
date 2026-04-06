"""core/tasks/persist.py — DDL and CRUD for the scheduler_jobs table.

The scheduler_jobs table lives in the public DuckDB database.
Every call to ensure_tables() is idempotent.

Schema:
    job_id          TEXT PRIMARY KEY
    label           TEXT NOT NULL
    fn_path         TEXT NOT NULL        -- importable dotted path to the worker fn
    interval_seconds INTEGER NOT NULL
    enabled         BOOLEAN NOT NULL DEFAULT FALSE
    last_run        TIMESTAMP
    next_run        TIMESTAMP NOT NULL
    last_run_status TEXT                 -- 'success' | 'failed' | 'cancelled'
    last_task_id    TEXT
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scheduler_jobs (
    job_id           TEXT PRIMARY KEY,
    label            TEXT NOT NULL,
    fn_path          TEXT NOT NULL,
    interval_seconds INTEGER NOT NULL,
    enabled          BOOLEAN NOT NULL DEFAULT FALSE,
    last_run         TIMESTAMP,
    next_run         TIMESTAMP NOT NULL
);
"""

_RUN_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS scheduler_run_history (
    run_id      TEXT PRIMARY KEY,
    job_id      TEXT NOT NULL,
    task_id     TEXT,
    started_at  TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    status      TEXT,
    error       TEXT
);
"""


def ensure_tables(con) -> None:
    """Create scheduler_jobs and scheduler_run_history if they do not exist. Idempotent."""
    con.execute(_SCHEMA)
    con.execute(_RUN_HISTORY_SCHEMA)
    # Migration: add columns that may not exist on older installs
    for col, typ in [("last_run_status", "TEXT"), ("last_task_id", "TEXT")]:
        try:
            con.execute(f"ALTER TABLE scheduler_jobs ADD COLUMN {col} {typ}")
        except Exception:
            pass  # column already exists


def get_all_jobs(con) -> list[dict]:
    rows = con.execute(
        "SELECT job_id, label, fn_path, interval_seconds, enabled, last_run, next_run "
        "FROM scheduler_jobs ORDER BY job_id"
    ).fetchall()
    cols = ["job_id", "label", "fn_path", "interval_seconds", "enabled", "last_run", "next_run"]
    return [dict(zip(cols, r)) for r in rows]


def get_due_jobs(con) -> list[dict]:
    """Return enabled jobs whose next_run is at or before now."""
    now = datetime.now(timezone.utc)
    rows = con.execute(
        "SELECT job_id, label, fn_path, interval_seconds, enabled, last_run, next_run "
        "FROM scheduler_jobs WHERE enabled = TRUE AND next_run <= ?",
        [now],
    ).fetchall()
    cols = ["job_id", "label", "fn_path", "interval_seconds", "enabled", "last_run", "next_run"]
    return [dict(zip(cols, r)) for r in rows]


def upsert_job_registration(
    con,
    job_id: str,
    label: str,
    fn_path: str,
    interval_seconds: int,
) -> None:
    """Insert a new job row or update label/fn_path/interval for an existing one.

    Does NOT touch enabled, last_run, or next_run — so user customisations persist
    across restarts.  next_run is only set on INSERT (defaults to now so the job
    runs on the first tick after registration).
    """
    now = datetime.now(timezone.utc)
    con.execute(
        """
        INSERT INTO scheduler_jobs (job_id, label, fn_path, interval_seconds, enabled, next_run)
        VALUES (?, ?, ?, ?, FALSE, ?)
        ON CONFLICT (job_id) DO UPDATE SET
            label            = excluded.label,
            fn_path          = excluded.fn_path,
            interval_seconds = excluded.interval_seconds
        """,
        [job_id, label, fn_path, interval_seconds, now],
    )


def mark_job_ran(con, job_id: str, interval_seconds: int) -> None:
    """Update last_run to now and advance next_run by interval_seconds."""
    now = datetime.now(timezone.utc)
    con.execute(
        """
        UPDATE scheduler_jobs
        SET last_run = ?,
            next_run = ? + INTERVAL (?) SECOND
        WHERE job_id = ?
        """,
        [now, now, interval_seconds, job_id],
    )


def set_enabled(con, job_id: str, enabled: bool) -> None:
    con.execute(
        "UPDATE scheduler_jobs SET enabled = ? WHERE job_id = ?",
        [enabled, job_id],
    )


def run_job_now(con, job_id: str) -> None:
    """Mark job as run now and advance next_run by its interval to prevent double-fire on tick."""
    now = datetime.now(timezone.utc)
    con.execute(
        """
        UPDATE scheduler_jobs
        SET last_run = ?,
            next_run = CAST(? AS TIMESTAMPTZ) + INTERVAL (interval_seconds) SECOND
        WHERE job_id = ?
        """,
        [now, now, job_id],
    )


def get_job(con, job_id: str) -> dict | None:
    """Return a single job by ID or None."""
    row = con.execute(
        "SELECT job_id, label, fn_path, interval_seconds, enabled, last_run, next_run, "
        "last_run_status, last_task_id "
        "FROM scheduler_jobs WHERE job_id = ?",
        [job_id],
    ).fetchone()
    if row is None:
        return None
    cols = ["job_id", "label", "fn_path", "interval_seconds", "enabled",
            "last_run", "next_run", "last_run_status", "last_task_id"]
    return dict(zip(cols, row))


def set_interval(con, job_id: str, interval_seconds: int) -> None:
    """Update a job's interval and recalculate next_run from now."""
    now = datetime.now(timezone.utc)
    con.execute(
        """
        UPDATE scheduler_jobs
        SET interval_seconds = ?,
            next_run = CAST(? AS TIMESTAMPTZ) + INTERVAL (?) SECOND
        WHERE job_id = ?
        """,
        [interval_seconds, now, interval_seconds, job_id],
    )


def update_last_run_status(con, job_id: str, status: str, task_id: str | None) -> None:
    """Write back the outcome of the most recent job run."""
    con.execute(
        "UPDATE scheduler_jobs SET last_run_status = ?, last_task_id = ? WHERE job_id = ?",
        [status, task_id, job_id],
    )


def insert_run_history(con, run_id: str, job_id: str, task_id: str | None) -> None:
    """Record the start of a job run."""
    now = datetime.now(timezone.utc)
    con.execute(
        "INSERT INTO scheduler_run_history (run_id, job_id, task_id, started_at, status) "
        "VALUES (?, ?, ?, ?, 'running')",
        [run_id, job_id, task_id, now],
    )


def complete_run_history(con, run_id: str, status: str, error: str | None = None) -> None:
    """Finalise a run history entry."""
    now = datetime.now(timezone.utc)
    con.execute(
        "UPDATE scheduler_run_history SET finished_at = ?, status = ?, error = ? WHERE run_id = ?",
        [now, status, error, run_id],
    )


def get_run_history(con, job_id: str, limit: int = 25) -> list[dict]:
    """Return recent run history for a job, newest first."""
    rows = con.execute(
        "SELECT run_id, job_id, task_id, started_at, finished_at, status, error "
        "FROM scheduler_run_history WHERE job_id = ? ORDER BY started_at DESC LIMIT ?",
        [job_id, limit],
    ).fetchall()
    cols = ["run_id", "job_id", "task_id", "started_at", "finished_at", "status", "error"]
    return [dict(zip(cols, r)) for r in rows]
