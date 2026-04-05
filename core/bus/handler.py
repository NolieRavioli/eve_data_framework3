"""Centralized bus handler with per-topic in-memory ring buffers.

``BusHandler`` attaches to the root Python logger and routes every log record
into a per-topic ``deque``.  It also supports direct ``publish()`` for
non-log live data (ESI rate stats, DB queue stats, etc.).

Consumers can:

* Read recent entries from any topic:  ``get_bus_log(topic, limit, after_id)``
* Merge across all topics:             ``get_recent(limit)``
* Stream live updates via callbacks:   ``subscribe(topic, fn)`` / ``unsubscribe()``
* Publish arbitrary data:              ``publish(topic, payload)``

The module-level ``bus_handler`` singleton is installed by calling
``install_bus_handler()``, which is invoked in ``core/web/__init__.py``
(Flask startup) and ``main.py`` (CLI startup).  Installing multiple times is
safe — the handler is only added once.
"""
from __future__ import annotations

import fnmatch
import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Callable

from core.bus.topics import LOG_TOPICS, LOG_SYSTEM, classify

_BUFFER_SIZE = 2000  # entries per topic

logger = logging.getLogger(__name__)


class BusHandler(logging.Handler):
    """Topic-routed logging handler with subscriber-push and direct publish."""

    def __init__(self, level: int = logging.DEBUG) -> None:
        super().__init__(level)
        self.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        self._lock = threading.Lock()
        self._cursor = 0
        # Pre-create buffers for static log topics.
        self._buffers: dict[str, deque] = {t: deque(maxlen=_BUFFER_SIZE) for t in LOG_TOPICS}
        # Subscribers: topic → [callback].  Supports exact match and wildcard.
        self._subscribers: dict[str, list[Callable]] = {}
        # Wildcard subscribers: pattern → [callback].  Resolved on each emit.
        self._wildcard_subscribers: dict[str, list[Callable]] = {}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _ensure_buffer(self, topic: str) -> deque:
        """Return (or create) the ring buffer for *topic*."""
        buf = self._buffers.get(topic)
        if buf is None:
            buf = deque(maxlen=_BUFFER_SIZE)
            self._buffers[topic] = buf
        return buf

    def _matching_subscribers(self, topic: str) -> list[Callable]:
        """Return all subscribers whose pattern matches *topic*."""
        subs = list(self._subscribers.get(topic, []))
        for pattern, fns in self._wildcard_subscribers.items():
            if fnmatch.fnmatch(topic, pattern):
                subs.extend(fns)
        return subs

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
                self._ensure_buffer(topic).append(entry)
                subs = self._matching_subscribers(topic)
            # Notify subscribers outside the lock.
            for fn in subs:
                try:
                    fn(entry)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)

    # ── Publish API (non-log data) ────────────────────────────────────────────

    def publish(self, topic: str, payload: dict) -> None:
        """Publish arbitrary data to *topic*.

        Unlike ``emit()``, this bypasses Python logging.  The payload is stored
        in the topic's ring buffer and pushed to active subscribers.
        """
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        with self._lock:
            self._cursor += 1
            entry: dict = {
                "id": self._cursor,
                "ts": ts,
                "topic": topic,
                "data": payload,
            }
            self._ensure_buffer(topic).append(entry)
            subs = self._matching_subscribers(topic)
        for fn in subs:
            try:
                fn(entry)
            except Exception:
                pass

    # ── Read API ──────────────────────────────────────────────────────────────

    def get_all_topics(self) -> list[str]:
        """Return the list of all topics that have buffers."""
        from core.bus.registry import get_all_topics
        return get_all_topics()

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

    def subscribe(self, pattern: str, fn: Callable) -> None:
        """Register *fn* for entries matching *pattern*.

        *pattern* can be an exact topic name (``log/market``) or a wildcard
        (``log/*``).  Wildcards use ``fnmatch`` semantics.
        """
        is_wildcard = "*" in pattern or "?" in pattern
        with self._lock:
            if is_wildcard:
                self._wildcard_subscribers.setdefault(pattern, [])
                if fn not in self._wildcard_subscribers[pattern]:
                    self._wildcard_subscribers[pattern].append(fn)
            else:
                self._subscribers.setdefault(pattern, [])
                if fn not in self._subscribers[pattern]:
                    self._subscribers[pattern].append(fn)

    def unsubscribe(self, pattern: str, fn: Callable) -> None:
        """Remove *fn* from *pattern*'s subscriber list."""
        with self._lock:
            for store in (self._subscribers, self._wildcard_subscribers):
                subs = store.get(pattern, [])
                try:
                    subs.remove(fn)
                except ValueError:
                    pass

    def unsubscribe_all(self, fn: Callable) -> None:
        """Remove *fn* from every topic/pattern — use on WebSocket disconnect."""
        with self._lock:
            for subs in self._subscribers.values():
                try:
                    subs.remove(fn)
                except ValueError:
                    pass
            for subs in self._wildcard_subscribers.values():
                try:
                    subs.remove(fn)
                except ValueError:
                    pass

    # ── Install helper ────────────────────────────────────────────────────────

    @classmethod
    def install(cls) -> "BusHandler":
        """Attach the module-level singleton to the root logger (idempotent)."""
        root = logging.getLogger()
        for h in root.handlers:
            if isinstance(h, cls):
                return h  # already installed
        root.addHandler(bus_handler)
        return bus_handler


# Module-level singleton.
bus_handler = BusHandler(level=logging.DEBUG)


def install_bus_handler() -> BusHandler:
    """Convenience wrapper — attach ``bus_handler`` to the root logger."""
    return BusHandler.install()


def get_all_topics() -> list[str]:
    return bus_handler.get_all_topics()


def get_bus_log(topic: str, limit: int = 200, after_id: int = 0) -> list[dict]:
    return bus_handler.get_topic_log(topic, limit=limit, after_id=after_id)


def get_recent(limit: int = 100) -> list[dict]:
    return bus_handler.get_recent(limit=limit)


def publish(topic: str, payload: dict) -> None:
    """Publish non-log data to the bus."""
    bus_handler.publish(topic, payload)
