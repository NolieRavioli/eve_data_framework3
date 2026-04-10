"""Centralised DuckDB read helpers.

All helpers open a fresh short-lived connection, run the query, and close the
connection.  DuckDB's MVCC allows concurrent reads alongside the single writer
thread — callers never need to acquire a lock before reading.

Public API
----------
query_rows(sql, params=None, db_path=None)   — list[dict] (all matching rows)
query_one(sql, params=None, db_path=None)    — dict | None (first row or None)
query_scalar(sql, params=None, db_path=None) — Any (first column of first row)
table_count(table_name, db_path=None)        — int (SELECT COUNT(*) from table)
get_db_file_stats(db_path=None)              — dict (file size, WAL info)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Read stats ─────────────────────────────────────────────────────────────────

_stats_lock = threading.Lock()
_read_stats: dict[str, int | float] = {
    "reads_total": 0,
    "rows_total": 0,
    "latency_sum_ms": 0.0,
    "last_latency_ms": 0.0,
}


def get_read_stats() -> dict:
    """Return a snapshot of public DuckDB read metrics."""
    with _stats_lock:
        return dict(_read_stats)


def _resolve_path(db_path: str | Path | None) -> Path:
    if db_path is not None:
        return Path(db_path)
    from core.db.public import get_database_path
    return get_database_path()


def _open(db_path: Path):
    from core.db.public import connect
    return connect(db_path)


def query_rows(
    sql: str,
    params: list[Any] | None = None,
    db_path: str | Path | None = None,
) -> list[dict]:
    """Execute *sql* and return all rows as a list of dicts."""
    con = _open(_resolve_path(db_path))
    t0 = time.monotonic()
    try:
        result = con.execute(sql, params or [])
        columns = [desc[0] for desc in result.description]
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
    finally:
        con.close()
    elapsed_ms = (time.monotonic() - t0) * 1000
    with _stats_lock:
        _read_stats["reads_total"] += 1
        _read_stats["rows_total"] += len(rows)
        _read_stats["latency_sum_ms"] += elapsed_ms
        _read_stats["last_latency_ms"] = elapsed_ms
    return rows


def query_one(
    sql: str,
    params: list[Any] | None = None,
    db_path: str | Path | None = None,
) -> dict | None:
    """Execute *sql* and return the first row as a dict, or None."""
    rows = query_rows(sql, params, db_path)
    return rows[0] if rows else None


def query_scalar(
    sql: str,
    params: list[Any] | None = None,
    db_path: str | Path | None = None,
) -> Any:
    """Execute *sql* and return the first column of the first row, or None."""
    con = _open(_resolve_path(db_path))
    t0 = time.monotonic()
    try:
        row = con.execute(sql, params or []).fetchone()
        result = row[0] if row is not None else None
    finally:
        con.close()
    elapsed_ms = (time.monotonic() - t0) * 1000
    with _stats_lock:
        _read_stats["reads_total"] += 1
        _read_stats["rows_total"] += (1 if row is not None else 0)
        _read_stats["latency_sum_ms"] += elapsed_ms
        _read_stats["last_latency_ms"] = elapsed_ms
    return result


def table_count(table_name: str, db_path: str | Path | None = None) -> int:
    """Return ``SELECT COUNT(*) FROM <table_name>``.

    Returns 0 if the table does not exist or the DB is unavailable.
    The table name is validated to contain only word characters to prevent
    SQL injection.
    """
    import re
    if not re.fullmatch(r"\w+", table_name):
        raise ValueError(f"Invalid table name: {table_name!r}")
    try:
        result = query_scalar(f"SELECT COUNT(*) FROM {table_name}", db_path=db_path)
        return int(result or 0)
    except Exception:
        return 0


def get_db_file_stats(db_path: str | Path | None = None) -> dict:
    """Return filesystem stats for the DuckDB file and its WAL sidecar.

    Keys returned:
        path            — str: absolute path to the DB file
        file_exists     — bool
        file_size_bytes — int: size of the .duckdb file (0 if not found)
        wal_exists      — bool: True if a .wal file is present
        wal_size_bytes  — int: size of the .wal file (0 if not found)
    """
    target = _resolve_path(db_path)
    wal = target.with_suffix(target.suffix + ".wal")

    file_exists = target.exists()
    wal_exists = wal.exists()

    return {
        "path": str(target.resolve()),
        "file_exists": file_exists,
        "file_size_bytes": os.path.getsize(target) if file_exists else 0,
        "wal_exists": wal_exists,
        "wal_size_bytes": os.path.getsize(wal) if wal_exists else 0,
    }
