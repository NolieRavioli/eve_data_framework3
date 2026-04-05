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
get_writer_stats()           — return live metrics dict (queue depth, latency, etc.)

When the writer is not running (e.g. during SDE pipeline startup or in tests),
both ``db_write`` and ``db_executemany`` fall back to a direct short-lived
DuckDB connection so callers never need to guard against the writer being
absent.
"""

from __future__ import annotations

import logging
import queue as _queue_module
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Sequence

import duckdb

logger = logging.getLogger(__name__)

# ── Internal op ───────────────────────────────────────────────────────────────


class _Op:
    __slots__ = ("sql", "params", "many", "rows", "df", "event", "error", "enqueued_at", "task_id")

    def __init__(
        self,
        sql: str,
        params: list[Any] | None,
        many: bool,
        rows: list[Sequence[Any]] | None,
        df: Any = None,
        task_id: str | None = None,
    ) -> None:
        self.sql = sql
        self.params = params
        self.many = many
        self.rows = rows
        self.df = df
        self.event: threading.Event = threading.Event()
        self.error: BaseException | None = None
        self.enqueued_at: float = time.monotonic()
        self.task_id: str | None = task_id


_STOP = object()  # sentinel

# ── Global writer state ────────────────────────────────────────────────────────

_write_queue: _queue_module.Queue = _queue_module.Queue()
_writer_thread: threading.Thread | None = None
_db_path: Path | None = None

# ── Metrics ────────────────────────────────────────────────────────────────────

_stats_lock = threading.Lock()
_latencies: deque = deque(maxlen=500)  # rolling window of execute_ms values
_attr_stats: dict[str, dict[str, int]] = {}  # task_id → {"ops": int, "rows": int}
_stats: dict[str, Any] = {
    "writes_total": 0,
    "writes_error": 0,
    "last_enqueue_wait_ms": 0.0,        # time op spent waiting in the queue
    "last_execute_ms": 0.0,             # time to execute the statement and commit
    "last_write_latency_ms": 0.0,       # backward-compat alias = last_execute_ms
    "last_checkpoint_at": None,         # float (monotonic) or None
    "last_checkpoint_ms": 0.0,
    "checkpoints_total": 0,
}


def get_writer_stats() -> dict:
    """Return a snapshot of writer thread metrics.

    Keys returned:
        thread_alive          — bool: is the writer thread running
        queue_depth           — int: number of ops currently queued
        writes_total          — int: total completed write ops
        writes_error          — int: total failed write ops
        last_enqueue_wait_ms  — float: time most recent op sat in the queue (ms)
        last_execute_ms       — float: execution + commit time of most recent op (ms)
        last_write_latency_ms — float: backward-compat alias for last_execute_ms
        last_checkpoint_at    — float | None: monotonic timestamp of last checkpoint
        last_checkpoint_ms    — float: duration of last checkpoint (ms)
        checkpoints_total     — int: total checkpoint ops fired
        p50_ms / p95_ms / p99_ms — float | None: execute latency percentiles (last 500 ops)
    """
    with _stats_lock:
        snap = dict(_stats)
        lats = list(_latencies)  # copy under lock
    snap["thread_alive"] = is_running()
    snap["queue_depth"] = _write_queue.qsize()
    if lats:
        lats_s = sorted(lats)
        n = len(lats_s)
        snap["p50_ms"] = lats_s[int(n * 0.50)]
        snap["p95_ms"] = lats_s[min(int(n * 0.95), n - 1)]
        snap["p99_ms"] = lats_s[min(int(n * 0.99), n - 1)]
    else:
        snap["p50_ms"] = snap["p95_ms"] = snap["p99_ms"] = None
    return snap


def get_attribution_snapshot() -> dict[str, dict[str, int]]:
    """Return per-task write attribution: ``{task_id: {"ops": N, "rows": N}}``."""
    with _stats_lock:
        return {tid: dict(vals) for tid, vals in _attr_stats.items()}


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
            # Disable DuckDB's automatic WAL checkpoint during active writes.
            # Our explicit 30 s idle checkpoint keeps the WAL bounded without
            # blocking mid-burst.  The default 16 MB threshold causes a multi-
            # second stall after a large market-order executemany() fires it.
            con.execute("SET checkpoint_threshold='10GB'")
            logger.debug("[writer] Connected to %s", db_path)
        except Exception as exc:
            logger.error("[writer] Failed to open connection: %s", exc)
            con = None

    def _checkpoint() -> None:
        nonlocal _pending
        if _pending and con is not None:
            to_flush = _pending
            t0 = time.monotonic()
            try:
                con.execute("CHECKPOINT")
                elapsed_ms = (time.monotonic() - t0) * 1000
                _pending = 0
                with _stats_lock:
                    _stats["last_checkpoint_at"] = time.monotonic()
                    _stats["last_checkpoint_ms"] = elapsed_ms
                    _stats["checkpoints_total"] += 1
                logger.info("[writer] checkpoint %.0fms — %d ops flushed to disk", elapsed_ms, to_flush)
            except Exception as exc:
                logger.debug("[writer] Checkpoint failed: %s", exc)

    _connect()

    _lookahead: object = None  # non-matching op deferred from last coalesce drain

    while True:
        # Prefer a deferred item from the last coalesce drain over a fresh queue pop.
        if _lookahead is not None:
            item = _lookahead
            _lookahead = None
        else:
            try:
                item = _write_queue.get(timeout=30.0)
            except _queue_module.Empty:
                # Idle timeout — flush any accumulated WAL to the main file.
                _checkpoint()
                continue

        if item is _STOP:
            break

        op: _Op = item

        # ── Coalesce: drain immediately-available many-ops with same SQL ─────
        # Groups queued pages into one executemany() per BEGIN/COMMIT cycle,
        # capped at _MAX_COALESCE_ROWS so no single batch grows unbounded.
        # The writer loops immediately after each batch, picking up the next
        # chunk — queue depth stays low and latency stays bounded.
        _MAX_COALESCE_ROWS = 50_000
        batch: list[_Op] = [op]
        coalesced_rows = len(op.rows) if (op.many and op.rows) else 0
        if op.many and op.rows:
            while coalesced_rows < _MAX_COALESCE_ROWS:
                try:
                    next_item = _write_queue.get_nowait()
                except _queue_module.Empty:
                    break
                if next_item is _STOP:
                    _lookahead = next_item
                    break
                next_op: _Op = next_item
                if next_op.many and next_op.sql == op.sql and next_op.rows:
                    batch.append(next_op)
                    coalesced_rows += len(next_op.rows)
                else:
                    # Different op — stash it for the next iteration (preserves order).
                    _lookahead = next_op
                    break

        enqueue_wait_ms = (time.monotonic() - op.enqueued_at) * 1000
        t0 = time.monotonic()
        depth = _write_queue.qsize()
        if depth > 100:
            logger.warning("[writer] queue depth %d — writes are backing up", depth)
        try:
            if con is None:
                _connect()
            con.execute("BEGIN")
            try:
                if op.df is not None:
                    # Fast path: bulk DataFrame insert via DuckDB's vectorised
                    # columnar import.  ~100× faster than executemany for large
                    # batches because it bypasses per-row Python binding.
                    con.register("_df_staging", op.df)
                    try:
                        con.execute(op.sql)
                    finally:
                        con.unregister("_df_staging")
                elif op.many:
                    combined: list = []
                    for b in batch:
                        combined.extend(b.rows)
                    if combined:
                        con.executemany(op.sql, combined)
                        if len(batch) > 1:
                            logger.debug(
                                "[writer] coalesced %d ops → %d rows",
                                len(batch), len(combined),
                            )
                else:
                    con.execute(op.sql, op.params or [])
                con.execute("COMMIT")
            except Exception:
                try:
                    con.execute("ROLLBACK")
                except Exception:
                    pass
                raise
            _pending += 1
            execute_ms = (time.monotonic() - t0) * 1000
            if execute_ms > 500:
                logger.warning(
                    "[writer] slow write %.0fms (queued %.0fms) | %d ops | %s",
                    execute_ms, enqueue_wait_ms, len(batch), op.sql.strip()[:80],
                )
            with _stats_lock:
                _stats["writes_total"] += len(batch)
                _stats["last_enqueue_wait_ms"] = enqueue_wait_ms
                _stats["last_execute_ms"] = execute_ms
                _stats["last_write_latency_ms"] = execute_ms
                _latencies.append(execute_ms)
                # ── Attribution: accumulate per-task op/row counts ────────
                for b in batch:
                    if b.task_id:
                        entry = _attr_stats.get(b.task_id)
                        if entry is None:
                            entry = {"ops": 0, "rows": 0}
                            _attr_stats[b.task_id] = entry
                        entry["ops"] += 1
                        if b.many and b.rows:
                            entry["rows"] += len(b.rows)
                        elif b.df is not None:
                            entry["rows"] += len(b.df)
                        else:
                            entry["rows"] += 1
        except Exception as exc:
            logger.warning("[writer] Write failed (%s): %s", type(exc).__name__, exc)
            for b in batch:
                b.error = exc
            with _stats_lock:
                _stats["writes_error"] += len(batch)
            _connect()  # reset connection after an error
        finally:
            # Unblock all callers in the coalesced batch immediately.
            for b in batch:
                b.event.set()

        # No inline checkpoint here — checkpoint_threshold is set to 10 GB so
        # DuckDB will not auto-checkpoint during write bursts.  The 30 s idle
        # timeout above handles explicit flushing once the burst completes.

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


def _current_task_id() -> str | None:
    """Read the calling thread's active task_id (if any)."""
    from core.queue._context import _thread_task
    return getattr(_thread_task, "task_id", None)


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
    """Execute a single write statement, blocking until complete."""
    if not is_running():
        _fallback_write(sql, list(params) if params else None)
        return
    op = _Op(sql=sql, params=list(params) if params else [], many=False, rows=None,
             task_id=_current_task_id())
    _submit(op)


def db_write_nowait(sql: str, params: Sequence[Any] | None = None) -> None:
    """Submit a single write statement without waiting for completion (fire-and-forget)."""
    if not is_running():
        _fallback_write(sql, list(params) if params else None)
        return
    op = _Op(sql=sql, params=list(params) if params else [], many=False, rows=None,
             task_id=_current_task_id())
    _write_queue.put(op)


def db_executemany(sql: str, rows: list[Sequence[Any]]) -> int:
    """Execute a bulk write statement, blocking until complete."""
    if not rows:
        return 0
    if not is_running():
        _fallback_executemany(sql, rows)
        return len(rows)
    op = _Op(sql=sql, params=None, many=True, rows=rows,
             task_id=_current_task_id())
    _submit(op)
    return len(rows)


def db_executemany_nowait(sql: str, rows: list[Sequence[Any]]) -> int:
    """Submit a bulk write without waiting for completion (fire-and-forget)."""
    if not rows:
        return 0
    if not is_running():
        _fallback_executemany(sql, rows)
        return len(rows)
    op = _Op(sql=sql, params=None, many=True, rows=rows,
             task_id=_current_task_id())
    _write_queue.put(op)
    return len(rows)


def db_write_dataframe(sql: str, df: Any) -> int:
    """Bulk-load a pandas DataFrame via the writer thread, blocking until done.

    The DataFrame is registered as ``_df_staging`` on the writer's persistent
    connection and the caller-supplied *sql* executes against it — typically::

        INSERT INTO my_table SELECT * FROM _df_staging

    This uses DuckDB's vectorised columnar import path, which is ~100× faster
    than ``executemany`` for large row counts.

    :param sql: INSERT (or other DML) referencing ``_df_staging``.
    :param df: A ``pandas.DataFrame`` whose columns match the target table.
    :returns: Number of rows in the DataFrame.
    """
    if df is None or len(df) == 0:
        return 0
    if not is_running():
        # Fallback: direct connection
        from core.db.publicDB import connect, get_database_path
        con = connect(get_database_path())
        try:
            con.register("_df_staging", df)
            try:
                con.execute(sql)
                con.execute("CHECKPOINT")
            finally:
                con.unregister("_df_staging")
        finally:
            con.close()
        return len(df)
    op = _Op(sql=sql, params=None, many=False, rows=None, df=df,
             task_id=_current_task_id())
    _submit(op)
    return len(df)
