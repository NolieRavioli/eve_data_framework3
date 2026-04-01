"""core/scheduler/db.py — DDL and CRUD for the scheduler_jobs table.

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


def ensure_tables(con) -> None:
    """Create scheduler_jobs if it does not exist. Idempotent."""
    con.execute(_SCHEMA)


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
    """Reset next_run to now so the engine fires the job on its next tick."""
    now = datetime.now(timezone.utc)
    con.execute(
        "UPDATE scheduler_jobs SET next_run = ? WHERE job_id = ?",
        [now, job_id],
    )
