"""core.bus — centralized, topic-based message bus with WebSocket push.

Usage
-----
    from core.bus import install_bus_handler, get_bus_log, get_recent, publish

    install_bus_handler()                        # attach handler to root logger
    entries = get_bus_log("log/market", 100)     # last 100 market log lines
    entries = get_recent(50)                     # 50 most recent across all topics
    publish("db/stats", {"writes": 42})          # push live data to subscribers

Topic names (slash-separated)
-----------------------------
    Log topics:   log/db, log/esi, log/scheduler, log/market, log/structures,
                  log/character, log/auth, log/web, log/system, log/app
    Data topics:  esi/rate, db/stats

Each log record is classified into a ``log/*`` topic by matching its logger
name against a prefix table (longest match wins).  See ``core.bus.topics``.

WebSocket streaming
-------------------
    The flask-sock handler at ``/bus`` lets browser clients subscribe to topics
    and receive live entries as JSON.  See ``websocket.py``.

Dynamic topic registration
--------------------------
    Applications can register custom topics at import time:

        from core.bus.registry import register_topic
        register_topic("myapp/events", description="...", access_level="user", required_role="myapp")
"""
from core.bus.topics import (
    ALL_STATIC_TOPICS,
    LOG_TOPICS,
    DATA_TOPICS,
    LOG_DB,
    LOG_ESI,
    LOG_SCHEDULER,
    LOG_MARKET,
    LOG_STRUCTURES,
    LOG_CHARACTER,
    LOG_AUTH,
    LOG_WEB,
    LOG_SYSTEM,
    LOG_APP,
    ESI_RATE,
    DB_STATS,
    SYSTEM_PROCESS,
    QUEUE_TASKS,
    classify,
)
from core.bus.handler import (
    BusHandler,
    bus_handler,
    install_bus_handler,
    get_all_topics,
    get_bus_log,
    get_recent,
    publish,
)
from core.bus.registry import (
    register_topic,
    get_topic_config,
    get_all_topic_configs,
    TopicConfig,
)
from core.bus.websocket import register_websock, attach_all_websocks

__all__ = [
    # Topics
    "ALL_STATIC_TOPICS", "LOG_TOPICS", "DATA_TOPICS",
    "LOG_DB", "LOG_ESI", "LOG_SCHEDULER", "LOG_MARKET", "LOG_STRUCTURES",
    "LOG_CHARACTER", "LOG_AUTH", "LOG_WEB", "LOG_SYSTEM", "LOG_APP",
    "ESI_RATE", "DB_STATS", "SYSTEM_PROCESS", "QUEUE_TASKS",
    "classify",
    # Handler
    "BusHandler", "bus_handler",
    "install_bus_handler", "get_all_topics", "get_bus_log", "get_recent",
    "publish",
    # Registry
    "register_topic", "get_topic_config", "get_all_topic_configs", "TopicConfig",
    # WebSocket helpers
    "register_websock", "attach_all_websocks",
]
