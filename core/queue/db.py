"""Unified DB I/O gateway — all reads and writes outside ``core/db/`` internals.

This module mirrors ``core/queue/esi_req.py`` for ESI HTTP: it is the single
entry point that analysis collectors and applications use for database access.

Public DuckDB writes route through ``core.db.writer`` (serial writer thread).
Public DuckDB reads route through ``core.db.reader`` (fresh connection per call).
Private SQLite writes route through ``core.queue.db_access`` (per-owner queues).
Private SQLite reads use ``core.db.privateDB.get_private_session``.

Stats from all layers are aggregated by ``get_db_gateway_stats()`` and published
to the ``db/stats`` bus topic by a periodic daemon thread.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Sequence

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Public DuckDB — writes
# ═══════════════════════════════════════════════════════════════════════════════


def write_public(sql: str, params: Sequence[Any] | None = None) -> None:
    """Execute a single DuckDB write, blocking until complete."""
    from core.db.writer import db_write
    db_write(sql, params)


def write_public_many(sql: str, rows: list[Sequence[Any]]) -> int:
    """Execute a bulk DuckDB write, blocking until complete."""
    from core.db.writer import db_executemany
    return db_executemany(sql, rows)


def write_public_nowait(sql: str, params: Sequence[Any] | None = None) -> None:
    """Fire-and-forget single DuckDB write."""
    from core.db.writer import db_write_nowait
    db_write_nowait(sql, params)


def write_public_many_nowait(sql: str, rows: list[Sequence[Any]]) -> int:
    """Fire-and-forget bulk DuckDB write."""
    from core.db.writer import db_executemany_nowait
    return db_executemany_nowait(sql, rows)


def write_public_dataframe(sql: str, df: Any) -> int:
    """Bulk-load a pandas DataFrame via the DuckDB writer, blocking until done."""
    from core.db.writer import db_write_dataframe
    return db_write_dataframe(sql, df)


# ═══════════════════════════════════════════════════════════════════════════════
# Public DuckDB — reads
# ═══════════════════════════════════════════════════════════════════════════════


def read_public(sql: str, params: list[Any] | None = None) -> list[dict]:
    """Query DuckDB and return all rows as a list of dicts."""
    from core.db.reader import query_rows
    return query_rows(sql, params)


def read_public_one(sql: str, params: list[Any] | None = None) -> dict | None:
    """Query DuckDB and return the first row as a dict, or None."""
    from core.db.reader import query_one
    return query_one(sql, params)


def read_public_scalar(sql: str, params: list[Any] | None = None) -> Any:
    """Query DuckDB and return the first column of the first row."""
    from core.db.reader import query_scalar
    return query_scalar(sql, params)


# ═══════════════════════════════════════════════════════════════════════════════
# Private SQLite — writes
# ═══════════════════════════════════════════════════════════════════════════════


def write_private(
    owner_id: int, sql: str, params: Sequence[Any] | None = None
) -> None:
    """Enqueue a single write for *owner_id*'s private SQLite."""
    from core.queue.db_access import submit_private_write
    from core.queue._context import _thread_task
    task_id = getattr(_thread_task, "task_id", None)
    submit_private_write(owner_id, sql, params, task_id=task_id)


def write_private_many(
    owner_id: int, sql: str, rows: list[Sequence[Any]]
) -> int:
    """Enqueue a bulk write for *owner_id*'s private SQLite."""
    from core.queue.db_access import submit_private_write_many
    from core.queue._context import _thread_task
    task_id = getattr(_thread_task, "task_id", None)
    submit_private_write_many(owner_id, sql, rows, task_id=task_id)
    return len(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# Private SQLite — reads
# ═══════════════════════════════════════════════════════════════════════════════


def read_private(
    owner_id: int, sql: str, params: list[Any] | None = None
) -> list[dict]:
    """Query *owner_id*'s private SQLite and return all rows as dicts."""
    from core.db.privateDB import get_private_session
    from sqlalchemy import text as sa_text
    session = get_private_session(owner_id)
    try:
        result = session.execute(sa_text(sql), params or {})
        columns = list(result.keys())
        return [dict(zip(columns, row)) for row in result.fetchall()]
    finally:
        session.close()


def read_private_one(
    owner_id: int, sql: str, params: list[Any] | None = None
) -> dict | None:
    """Query *owner_id*'s private SQLite and return the first row or None."""
    rows = read_private(owner_id, sql, params)
    return rows[0] if rows else None


# ═══════════════════════════════════════════════════════════════════════════════
# Stats aggregation
# ═══════════════════════════════════════════════════════════════════════════════


def get_db_gateway_stats() -> dict:
    """Aggregate stats from writer, reader, private queues, and market buffer."""
    from core.db.writer import get_writer_stats, get_attribution_snapshot
    from core.db.reader import get_read_stats
    from core.db.market_buffer import get_cache_stats
    from core.queue.db_access import get_private_queue_stats

    return {
        "writer": get_writer_stats(),
        "attribution": get_attribution_snapshot(),
        "reads": get_read_stats(),
        "market_buffer": get_cache_stats(),
        "private_queues": get_private_queue_stats(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# db/stats bus publisher
# ═══════════════════════════════════════════════════════════════════════════════

_publisher_thread: threading.Thread | None = None


def _publish_loop() -> None:
    """Periodically publish DB stats to the bus."""
    from core.bus import publish, DB_STATS
    while True:
        time.sleep(5.0)
        try:
            publish(DB_STATS, get_db_gateway_stats())
        except Exception:
            pass


def start_db_stats_publisher() -> None:
    """Start the daemon thread that publishes ``db/stats`` every 5 s."""
    global _publisher_thread
    if _publisher_thread is not None and _publisher_thread.is_alive():
        return
    _publisher_thread = threading.Thread(
        target=_publish_loop, daemon=True, name="db-stats-pub"
    )
    _publisher_thread.start()
    logger.info("[db-stats-pub] Started — publishing db/stats every 5s")
