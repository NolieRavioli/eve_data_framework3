"""Serialized DuckDB write channel.

A single background writer thread holds one persistent DuckDB connection and
processes all write operations from a queue.  This eliminates the
concurrent-write lock conflicts that arise when multiple Flask request threads
or task workers open separate writeable DuckDB connections simultaneously.

Public API
----------
start_writer(db_path=None)   — start the writer thread (call once at startup)
stop_writer(timeout=10.0)    — graceful shutdown (call at app teardown)
db_write(sql, params=None)   — execute a single write statement (blocking)
db_executemany(sql, rows)    — execute a bulk insert/upsert (blocking)

When the writer is not running (e.g. during SDE pipeline startup or in tests),
both ``db_write`` and ``db_executemany`` fall back to a direct short-lived
DuckDB connection so callers never need to guard against the writer being
absent.
"""

from __future__ import annotations

import logging
import queue as _queue_module
import threading
from pathlib import Path
from typing import Any, Sequence

import duckdb

logger = logging.getLogger(__name__)

# ── Internal op ───────────────────────────────────────────────────────────────


class _Op:
    __slots__ = ("sql", "params", "many", "rows", "event", "error")

    def __init__(
        self,
        sql: str,
        params: list[Any] | None,
        many: bool,
        rows: list[Sequence[Any]] | None,
    ) -> None:
        self.sql = sql
        self.params = params
        self.many = many
        self.rows = rows
        self.event: threading.Event = threading.Event()
        self.error: BaseException | None = None


_STOP = object()  # sentinel

# ── Global writer state ────────────────────────────────────────────────────────

_write_queue: _queue_module.Queue = _queue_module.Queue()
_writer_thread: threading.Thread | None = None
_db_path: Path | None = None

# ── Writer loop ────────────────────────────────────────────────────────────────


def _writer_loop(db_path: Path) -> None:
    con: duckdb.DuckDBPyConnection | None = None
    _pending = 0

    def _connect() -> None:
        nonlocal con
        try:
            if con is not None:
                try:
                    con.close()
                except Exception:
                    pass
            con = duckdb.connect(str(db_path), read_only=False)
            con.execute("PRAGMA threads=4")
            logger.debug("[writer] Connected to %s", db_path)
        except Exception as exc:
            logger.error("[writer] Failed to open connection: %s", exc)
            con = None

    def _checkpoint() -> None:
        nonlocal _pending
        if _pending and con is not None:
            try:
                con.execute("CHECKPOINT")
                _pending = 0
            except Exception as exc:
                logger.debug("[writer] Checkpoint failed: %s", exc)

    _connect()

    while True:
        try:
            item = _write_queue.get(timeout=30.0)
        except _queue_module.Empty:
            # Idle timeout — flush any accumulated WAL to the main file.
            _checkpoint()
            continue

        if item is _STOP:
            break

        op: _Op = item
        try:
            if con is None:
                _connect()
            if op.many:
                if op.rows:
                    con.executemany(op.sql, op.rows)
            else:
                con.execute(op.sql, op.params or [])
            _pending += 1
        except Exception as exc:
            logger.warning("[writer] Write failed (%s): %s", type(exc).__name__, exc)
            op.error = exc
            _connect()  # reset connection after an error
        finally:
            # Unblock the caller immediately — never make callers wait for CHECKPOINT.
            op.event.set()

        # No inline checkpoint here — DuckDB auto-checkpoints at the WAL size
        # threshold, and the 30 s idle timeout above handles explicit flushing
        # after a burst completes.  Firing checkpoint between writes would block
        # the next caller for the full flush duration (~14 s on large tables).

    _checkpoint()
    if con is not None:
        try:
            con.close()
        except Exception:
            pass
    logger.debug("[writer] Thread stopped.")


# ── Public API ─────────────────────────────────────────────────────────────────


def start_writer(db_path: str | Path | None = None) -> None:
    """Start the background writer thread.

    Safe to call multiple times — does nothing if already running.
    """
    global _writer_thread, _db_path

    if _writer_thread is not None and _writer_thread.is_alive():
        return  # already running

    if db_path is None:
        from core.db.publicDB import get_database_path
        db_path = get_database_path()

    _db_path = Path(db_path)
    _writer_thread = threading.Thread(
        target=_writer_loop,
        args=(_db_path,),
        name="duckdb-writer",
        daemon=True,
    )
    _writer_thread.start()
    logger.info("[writer] Started — serializing writes to %s", _db_path)


def stop_writer(timeout: float = 10.0) -> None:
    """Stop the writer thread gracefully.

    Sends a stop sentinel, then waits up to *timeout* seconds for the thread
    to finish processing any queued operations before joining.
    """
    global _writer_thread

    if _writer_thread is None or not _writer_thread.is_alive():
        return

    _write_queue.put(_STOP)
    _writer_thread.join(timeout=timeout)
    _writer_thread = None
    logger.info("[writer] Stopped.")


def is_running() -> bool:
    """Return True if the writer thread is alive."""
    return _writer_thread is not None and _writer_thread.is_alive()


def _submit(op: _Op) -> None:
    """Push an op onto the queue and block until the writer completes it."""
    _write_queue.put(op)
    op.event.wait()
    if op.error is not None:
        raise op.error


def _fallback_write(sql: str, params: list[Any] | None) -> None:
    """Direct-connection fallback used when the writer is not running."""
    from core.db.publicDB import connect, get_database_path
    con = connect(get_database_path())
    try:
        con.execute(sql, params or [])
        con.execute("CHECKPOINT")
    finally:
        con.close()


def _fallback_executemany(sql: str, rows: list[Sequence[Any]]) -> None:
    """Direct-connection fallback used when the writer is not running."""
    from core.db.publicDB import connect, get_database_path
    con = connect(get_database_path())
    try:
        if rows:
            con.executemany(sql, rows)
            con.execute("CHECKPOINT")
    finally:
        con.close()


def db_write(sql: str, params: Sequence[Any] | None = None) -> None:
    """Execute a single write statement.

    Routes through the serialized writer thread when running, or falls back
    to a direct connection otherwise.
    """
    if not is_running():
        _fallback_write(sql, list(params) if params else None)
        return
    op = _Op(sql=sql, params=list(params) if params else [], many=False, rows=None)
    _submit(op)


def db_executemany(sql: str, rows: list[Sequence[Any]]) -> int:
    """Execute a bulk write statement.

    Routes through the serialized writer thread when running, or falls back
    to a direct connection otherwise.  Returns the number of rows submitted.
    """
    if not rows:
        return 0
    if not is_running():
        _fallback_executemany(sql, rows)
        return len(rows)
    op = _Op(sql=sql, params=None, many=True, rows=rows)
    _submit(op)
    return len(rows)
