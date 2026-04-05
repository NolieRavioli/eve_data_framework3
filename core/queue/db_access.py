"""Per-owner private SQLite write queues with ephemeral drain threads.

Each owner gets its own FIFO queue.  When a write is submitted, if no drain
thread is active for that owner, one is spawned.  It runs until the queue is
empty, then exits — no idle threads.

Thread safety
-------------
``_global_lock`` guards creation of new ``_OwnerState`` entries (held briefly).
Each ``_OwnerState.lock`` guards its queue drain lifecycle.
Cross-owner writes never block each other.
"""
from __future__ import annotations

import logging
import queue as _queue_module
import threading
from dataclasses import dataclass, field
from typing import Any, Sequence

from sqlalchemy import text as sa_text

logger = logging.getLogger(__name__)


# ── Internal types ─────────────────────────────────────────────────────────────

@dataclass
class _PrivateOp:
    sql: str
    params: list[Any] | None
    many: bool
    rows: list[Sequence[Any]] | None
    task_id: str | None


@dataclass
class _OwnerState:
    queue: _queue_module.Queue = field(default_factory=_queue_module.Queue)
    lock: threading.Lock = field(default_factory=threading.Lock)
    thread_active: bool = False
    ops: int = 0
    rows_written: int = 0


# ── Module state ───────────────────────────────────────────────────────────────

_global_lock = threading.Lock()
_per_owner: dict[int, _OwnerState] = {}


def _get_owner_state(owner_id: int) -> _OwnerState:
    """Return (or create) the ``_OwnerState`` for *owner_id*."""
    state = _per_owner.get(owner_id)
    if state is not None:
        return state
    with _global_lock:
        state = _per_owner.get(owner_id)
        if state is None:
            state = _OwnerState()
            _per_owner[owner_id] = state
    return state


# ── Drain thread ───────────────────────────────────────────────────────────────

def _drain(owner_id: int) -> None:
    """Process queued writes for *owner_id* until the queue is empty, then exit."""
    from core.db.privateDB import get_private_session

    state = _per_owner[owner_id]
    session = get_private_session(owner_id)
    try:
        while True:
            try:
                op: _PrivateOp = state.queue.get_nowait()
            except _queue_module.Empty:
                # Double-check under lock — prevents race between enqueue and exit.
                with state.lock:
                    if state.queue.empty():
                        state.thread_active = False
                        return
                    else:
                        continue
            try:
                if op.many and op.rows:
                    session.execute(
                        sa_text(op.sql),
                        [dict(enumerate(row)) if not isinstance(row, dict) else row
                         for row in op.rows],
                    )
                    state.rows_written += len(op.rows)
                else:
                    session.execute(
                        sa_text(op.sql),
                        op.params or {},
                    )
                    state.rows_written += 1
                session.commit()
                state.ops += 1
            except Exception as exc:
                logger.warning(
                    "[db_access] private write failed for owner %s: %s", owner_id, exc
                )
                try:
                    session.rollback()
                except Exception:
                    pass
    finally:
        try:
            session.close()
        except Exception:
            pass


# ── Public API ─────────────────────────────────────────────────────────────────

def submit_private_write(
    owner_id: int,
    sql: str,
    params: Sequence[Any] | None = None,
    task_id: str | None = None,
) -> None:
    """Enqueue a single write for *owner_id*'s private SQLite."""
    state = _get_owner_state(owner_id)
    op = _PrivateOp(
        sql=sql,
        params=list(params) if params else None,
        many=False,
        rows=None,
        task_id=task_id,
    )
    state.queue.put(op)
    with state.lock:
        if not state.thread_active:
            state.thread_active = True
            threading.Thread(
                target=_drain, args=(owner_id,), daemon=True,
                name=f"priv-writer-{owner_id}",
            ).start()


def submit_private_write_many(
    owner_id: int,
    sql: str,
    rows: list[Sequence[Any]],
    task_id: str | None = None,
) -> None:
    """Enqueue a bulk write for *owner_id*'s private SQLite."""
    if not rows:
        return
    state = _get_owner_state(owner_id)
    op = _PrivateOp(
        sql=sql,
        params=None,
        many=True,
        rows=rows,
        task_id=task_id,
    )
    state.queue.put(op)
    with state.lock:
        if not state.thread_active:
            state.thread_active = True
            threading.Thread(
                target=_drain, args=(owner_id,), daemon=True,
                name=f"priv-writer-{owner_id}",
            ).start()


def get_private_queue_stats() -> dict[int, dict]:
    """Return ``{owner_id: {ops, rows, queue_depth, thread_active}}``."""
    result = {}
    for oid, state in _per_owner.items():
        result[oid] = {
            "ops": state.ops,
            "rows": state.rows_written,
            "queue_depth": state.queue.qsize(),
            "thread_active": state.thread_active,
        }
    return result
