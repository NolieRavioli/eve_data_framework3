"""Periodic publisher for the ``system/process`` bus topic.

Polls process-level metrics (PID, RSS, thread count, CPU%) every
``_INTERVAL_S`` seconds and publishes a snapshot to the bus so any
subscribed WebSocket client receives live updates without polling a REST
endpoint.

Call ``start_process_publisher()`` once at startup (from
``core/web/__init__.py``).  Subsequent calls are idempotent.
"""
from __future__ import annotations

import logging
import os
import threading

logger = logging.getLogger(__name__)

_INTERVAL_S = 10.0
_started = False
_lock = threading.Lock()


def collect_process_snapshot() -> dict:
    """Return a dict with current process metrics including per-thread CPU breakdown."""
    snapshot: dict = {
        "pid": os.getpid(),
        "memory_rss_mb": None,
        "thread_count": threading.active_count(),
        "cpu_percent": None,
        "threads": [],
        "thread_cpu": {},
    }

    # Build a map from native_id → Python thread info.
    native_id_map: dict[int, threading.Thread] = {}
    for t in threading.enumerate():
        nid = getattr(t, "native_id", None)
        if nid is not None:
            native_id_map[nid] = t

    # Populate thread list from Python's threading module.
    for t in threading.enumerate():
        snapshot["threads"].append({
            "name": t.name,
            "native_id": getattr(t, "native_id", None),
            "daemon": t.daemon,
            "alive": t.is_alive(),
        })
    snapshot["threads"].sort(key=lambda x: (x["daemon"], x["name"]))

    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        snapshot["memory_rss_mb"] = round(mem.rss / (1024 * 1024), 1)
        snapshot["cpu_percent"] = proc.cpu_percent(interval=0)
        # Per-thread CPU times — joined to Python thread names via native_id.
        for pt in proc.threads():
            snapshot["thread_cpu"][str(pt.id)] = {
                "user_time":   round(pt.user_time, 3),
                "system_time": round(pt.system_time, 3),
            }
    except ImportError:
        pass
    return snapshot


def _publisher_loop(stop_evt: threading.Event) -> None:
    from core.bus import publish, SYSTEM_PROCESS

    while not stop_evt.wait(timeout=_INTERVAL_S):
        try:
            payload = collect_process_snapshot()
            publish(SYSTEM_PROCESS, payload)
        except Exception:
            logger.exception("[process_pub] error collecting process snapshot")


def start_process_publisher() -> None:
    """Start the background process-metrics publisher (idempotent)."""
    global _started
    with _lock:
        if _started:
            return
        _started = True

    stop_evt = threading.Event()
    thread = threading.Thread(
        target=_publisher_loop,
        args=(stop_evt,),
        daemon=True,
        name="bus-process-pub",
    )
    thread.start()
    logger.debug("[process_pub] started (interval=%ss)", _INTERVAL_S)

    # Register with the central lifecycle coordinator.
    try:
        from core.system import get_lifecycle
        get_lifecycle().register("bus-process-pub", thread)
    except Exception:
        pass
