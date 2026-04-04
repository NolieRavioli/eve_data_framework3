"""core.telemetry — centralized, topic-based log aggregation with WebSocket push.

Usage
-----
    from core.telemetry import install, get_topic_log, get_recent, subscribe

    install()                               # attach handler to root logger
    entries = get_topic_log("market", 100)  # last 100 market-domain log lines
    entries = get_recent(50)                # 50 most recent across all topics

Topic names
-----------
    db, esi, scheduler, market, structures, character, auth, web, system, app

Each log record is classified into a topic by matching its logger name against
a prefix table (longest match wins).  See ``core.telemetry.topics`` for the
full mapping.

WebSocket streaming
-------------------
    The flask-sock handler at /telemetry/ws lets admin browser clients subscribe
    to topics and receive live log entries as JSON.  See ``websocket.py``.
"""
from core.telemetry.topics import (
    ALL_TOPICS,
    DB,
    ESI,
    SCHEDULER,
    MARKET,
    STRUCTURES,
    CHARACTER,
    AUTH,
    WEB,
    SYSTEM,
    APP,
    classify,
)
from core.telemetry.handler import (
    TelemetryHandler,
    telemetry_handler,
    install,
    get_all_topics,
    get_topic_log,
    get_recent,
)

__all__ = [
    # Topics
    "ALL_TOPICS",
    "DB", "ESI", "SCHEDULER", "MARKET", "STRUCTURES",
    "CHARACTER", "AUTH", "WEB", "SYSTEM", "APP",
    "classify",
    # Handler
    "TelemetryHandler",
    "telemetry_handler",
    "install",
    "get_all_topics",
    "get_topic_log",
    "get_recent",
]
