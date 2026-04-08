"""Central thread lifecycle coordinator.

Manages registration, startup, graceful shutdown, and health reporting
for all background threads in the framework (writer, scheduler, stats
publishers, etc.).

Usage
-----
    from core.system import get_lifecycle

    lifecycle = get_lifecycle()
    lifecycle.register("db-writer", thread, stop_fn=stop_writer)
    ...
    lifecycle.shutdown()  # reverse-order graceful stop
"""

from __future__ import annotations

import atexit
import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class _ManagedThread:
    """Internal record for a registered thread."""
    name: str
    thread: threading.Thread
    stop_fn: Optional[Callable[[], None]]
    order: int = 0  # registration order; shutdown is reversed


class SystemLifecycle:
    """Central thread registry + graceful shutdown coordinator."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._threads: dict[str, _ManagedThread] = {}
        self._order_counter = 0
        self._shutdown_registered = False

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        thread: threading.Thread,
        stop_fn: Optional[Callable[[], None]] = None,
    ) -> None:
        """Register a managed thread for lifecycle tracking.

        Parameters
        ----------
        name : str
            Unique name for the thread (used in logs and health check).
        thread : threading.Thread
            The thread object (may already be started).
        stop_fn : callable, optional
            Called during shutdown to signal the thread to stop.
        """
        with self._lock:
            self._order_counter += 1
            self._threads[name] = _ManagedThread(
                name=name,
                thread=thread,
                stop_fn=stop_fn,
                order=self._order_counter,
            )
        logger.debug("Registered thread %r (order=%d)", name, self._order_counter)

        if not self._shutdown_registered:
            atexit.register(self.shutdown)
            self._shutdown_registered = True

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self, timeout: float = 10.0) -> None:
        """Gracefully stop all managed threads in reverse registration order."""
        with self._lock:
            entries = sorted(
                self._threads.values(),
                key=lambda m: m.order,
                reverse=True,
            )

        if not entries:
            return

        logger.info("Shutting down %d managed threads...", len(entries))

        for entry in entries:
            if entry.thread.is_alive():
                logger.info("Stopping %r...", entry.name)
                if entry.stop_fn is not None:
                    try:
                        entry.stop_fn()
                    except Exception:
                        logger.exception("Error stopping %r", entry.name)
                entry.thread.join(timeout=timeout)
                if entry.thread.is_alive():
                    logger.warning("Thread %r did not stop within %.1fs", entry.name, timeout)
                else:
                    logger.info("Thread %r stopped.", entry.name)

        logger.info("Shutdown complete.")

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_check(self) -> dict:
        """Return a status dict for every registered thread.

        Returns
        -------
        dict
            ``{name: {"alive": bool, "daemon": bool, "order": int}}``
        """
        with self._lock:
            entries = list(self._threads.values())

        return {
            entry.name: {
                "alive": entry.thread.is_alive(),
                "daemon": entry.thread.daemon,
                "order": entry.order,
            }
            for entry in entries
        }

    def is_healthy(self) -> bool:
        """Return True if all registered threads are alive."""
        return all(v["alive"] for v in self.health_check().values())


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_lifecycle: Optional[SystemLifecycle] = None
_lifecycle_lock = threading.Lock()


def get_lifecycle() -> SystemLifecycle:
    """Return the global SystemLifecycle singleton."""
    global _lifecycle
    if _lifecycle is None:
        with _lifecycle_lock:
            if _lifecycle is None:
                _lifecycle = SystemLifecycle()
    return _lifecycle
