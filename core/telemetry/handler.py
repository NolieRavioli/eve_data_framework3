"""Centralized telemetry log handler with per-topic in-memory ring buffers.

``TelemetryHandler`` attaches to the root Python logger and routes every log
record into a per-topic ``deque``.  Consumers can:

* Read recent entries from any topic:  ``get_topic_log(topic, limit, after_id)``
* Merge across all topics:             ``get_recent(limit)``
* Stream live updates via callbacks:   ``subscribe(topic, fn)`` / ``unsubscribe()``

The module-level ``telemetry_handler`` singleton is installed by calling
``install()``, which is invoked in ``core/web/__init__.py`` (Flask startup) and
``main.py`` (CLI startup).  Installing multiple times is safe — the handler is
only added once.
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Callable

from core.telemetry.topics import ALL_TOPICS, SYSTEM, classify

_BUFFER_SIZE = 2000  # entries per topic

logger = logging.getLogger(__name__)


class TelemetryHandler(logging.Handler):
    """Topic-routed logging handler with subscriber-push notifications."""

    def __init__(self, level: int = logging.DEBUG) -> None:
        super().__init__(level)
        self.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        self._lock = threading.Lock()
        self._cursor = 0
        self._buffers: dict[str, deque] = {t: deque(maxlen=_BUFFER_SIZE) for t in ALL_TOPICS}
        self._subscribers: dict[str, list[Callable]] = {t: [] for t in ALL_TOPICS}

    # ── logging.Handler interface ─────────────────────────────────────────────

    def emit(self, record: logging.LogRecord) -> None:
        try:
            topic = classify(record.name)
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            with self._lock:
                self._cursor += 1
                entry: dict = {
                    "id": self._cursor,
                    "ts": ts,
                    "level": record.levelname,
                    "logger": record.name,
                    "topic": topic,
                    "message": self.format(record),
                }
                self._buffers[topic].append(entry)
                subs = list(self._subscribers.get(topic, []))
            # Notify subscribers outside the lock so they can safely call
            # get_topic_log() without deadlocking.
            for fn in subs:
                try:
                    fn(entry)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)

    # ── Read API ──────────────────────────────────────────────────────────────

    def get_all_topics(self) -> list[str]:
        """Return the list of all known topic names."""
        return list(ALL_TOPICS)

    def get_topic_log(
        self,
        topic: str,
        limit: int = 200,
        after_id: int = 0,
    ) -> list[dict]:
        """Return up to *limit* entries for *topic* with ``id > after_id``."""
        with self._lock:
            rows = [e for e in self._buffers.get(topic, []) if e["id"] > after_id]
        return rows[-limit:]

    def get_recent(self, limit: int = 100) -> list[dict]:
        """Return the *limit* most recent entries merged across all topics."""
        with self._lock:
            merged: list[dict] = []
            for buf in self._buffers.values():
                merged.extend(buf)
        merged.sort(key=lambda e: e["id"])
        return merged[-limit:]

    # ── Subscriber API ────────────────────────────────────────────────────────

    def subscribe(self, topic: str, fn: Callable) -> None:
        """Register *fn* to be called with each new entry for *topic*."""
        with self._lock:
            if topic in self._subscribers and fn not in self._subscribers[topic]:
                self._subscribers[topic].append(fn)

    def unsubscribe(self, topic: str, fn: Callable) -> None:
        """Remove *fn* from *topic*'s subscriber list."""
        with self._lock:
            subs = self._subscribers.get(topic, [])
            try:
                subs.remove(fn)
            except ValueError:
                pass

    def unsubscribe_all(self, fn: Callable) -> None:
        """Remove *fn* from every topic — use on WebSocket disconnect."""
        with self._lock:
            for subs in self._subscribers.values():
                try:
                    subs.remove(fn)
                except ValueError:
                    pass

    # ── Install helper ────────────────────────────────────────────────────────

    @classmethod
    def install(cls) -> "TelemetryHandler":
        """Attach the module-level singleton to the root logger (idempotent)."""
        root = logging.getLogger()
        for h in root.handlers:
            if isinstance(h, cls):
                return h  # already installed
        root.addHandler(telemetry_handler)
        return telemetry_handler


# Module-level singleton — consumers import this directly.
telemetry_handler = TelemetryHandler(level=logging.DEBUG)


def install() -> TelemetryHandler:
    """Convenience wrapper — attach ``telemetry_handler`` to the root logger."""
    return TelemetryHandler.install()


def get_all_topics() -> list[str]:
    return telemetry_handler.get_all_topics()


def get_topic_log(topic: str, limit: int = 200, after_id: int = 0) -> list[dict]:
    return telemetry_handler.get_topic_log(topic, limit=limit, after_id=after_id)


def get_recent(limit: int = 100) -> list[dict]:
    return telemetry_handler.get_recent(limit=limit)
