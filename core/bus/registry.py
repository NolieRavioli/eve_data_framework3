"""Dynamic topic registry for core.bus.

Applications and core modules can register new topics at import time via
``register_topic()``.  The bus handler consults this registry when a subscriber
requests a topic that isn't in the static set.

Each topic carries:
    - ``name``            — slash-separated identifier (e.g. ``db/stats``)
    - ``description``     — human-readable one-liner
    - ``access_level``    — minimum access: ``"public"`` | ``"user"`` | ``"admin"``
    - ``required_role``   — named role string, or ``None`` for level-only check
"""
from __future__ import annotations

import threading
from typing import NamedTuple

from core.bus.topics import ALL_STATIC_TOPICS, LOG_TOPICS


class TopicConfig(NamedTuple):
    name: str
    description: str = ""
    access_level: str = "admin"       # "public" | "user" | "admin"
    required_role: str | None = None  # named role, or None


_lock = threading.Lock()
_dynamic_topics: dict[str, TopicConfig] = {}

# Pre-register static topics with sane defaults.
_static_configs: dict[str, TopicConfig] = {}
for _t in LOG_TOPICS:
    _static_configs[_t] = TopicConfig(name=_t, description="Log stream", access_level="admin")
# Live data topics with specific access levels.
_static_configs["esi/rate"] = TopicConfig(
    name="esi/rate",
    description="ESI rate-limiter live stats",
    access_level="user",
    required_role="tasks",
)
_static_configs["db/stats"] = TopicConfig(
    name="db/stats",
    description="Database queue and read statistics",
    access_level="user",
    required_role="database",
)
_static_configs["system/process"] = TopicConfig(
    name="system/process",
    description="Process health metrics (PID, RSS, threads, CPU)",
    access_level="admin",
)
_static_configs["task/events"] = TopicConfig(
    name="task/events",
    description="Live task-list snapshot (all tasks, brief)",
    access_level="user",
    required_role="tasks",
)


def register_topic(
    name: str,
    description: str = "",
    access_level: str = "admin",
    required_role: str | None = None,
) -> None:
    """Register a new topic at runtime.  Safe to call at import time.

    Calling with a name that already exists updates the config.
    """
    with _lock:
        _dynamic_topics[name] = TopicConfig(
            name=name,
            description=description,
            access_level=access_level,
            required_role=required_role,
        )


def get_topic_config(name: str) -> TopicConfig | None:
    """Return the config for a topic, or None if unregistered."""
    with _lock:
        return _dynamic_topics.get(name) or _static_configs.get(name)


def get_all_topics() -> list[str]:
    """Return all known topic names (static + dynamic), sorted."""
    with _lock:
        names = set(ALL_STATIC_TOPICS) | set(_dynamic_topics.keys())
    return sorted(names)


def get_all_topic_configs() -> list[TopicConfig]:
    """Return configs for all registered topics."""
    with _lock:
        merged = dict(_static_configs)
        merged.update(_dynamic_topics)
    return sorted(merged.values(), key=lambda tc: tc.name)
