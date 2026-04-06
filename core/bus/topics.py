"""Topic constants and logger-name classifier for core.bus.

Every log record emitted anywhere in the application is classified into one
slash-separated topic by matching its logger name against the prefix table
below.  The longest matching prefix wins; unrecognised loggers fall back to
``log/system``.

Live-data topics (``esi/rate``, ``db/stats``) are not derived from logger
names — they are published directly via ``BusHandler.publish()``.
"""
from __future__ import annotations

# ── Log topic constants (slash-separated) ─────────────────────────────────────
# These are the "log/*" family — populated automatically from Python logging.

LOG_DB = "log/db"
LOG_ESI = "log/esi"
LOG_SCHEDULER = "log/scheduler"
LOG_MARKET = "log/market"
LOG_STRUCTURES = "log/structures"
LOG_CHARACTER = "log/character"
LOG_AUTH = "log/auth"
LOG_WEB = "log/web"
LOG_SYSTEM = "log/system"
LOG_APP = "log/app"

LOG_TOPICS: tuple[str, ...] = (
    LOG_DB, LOG_ESI, LOG_SCHEDULER, LOG_MARKET, LOG_STRUCTURES,
    LOG_CHARACTER, LOG_AUTH, LOG_WEB, LOG_SYSTEM, LOG_APP,
)

# ── Live-data topic constants ─────────────────────────────────────────────────
# Published directly via BusHandler.publish(), not via Python logging.

ESI_RATE = "esi/rate"
DB_STATS = "db/stats"
SYSTEM_PROCESS = "system/process"
QUEUE_TASKS = "queue/tasks"

DATA_TOPICS: tuple[str, ...] = (
    ESI_RATE, DB_STATS, SYSTEM_PROCESS, QUEUE_TASKS,
)

# ── Combined ──────────────────────────────────────────────────────────────────

ALL_STATIC_TOPICS: tuple[str, ...] = LOG_TOPICS + DATA_TOPICS

# ── Logger-name prefix → log topic ───────────────────────────────────────────
# Sorted by length at import time so the classifier can do a simple linear
# scan and pick the longest winner.

_PREFIX_MAP: list[tuple[str, str]] = sorted(
    [
        ("core.db",                LOG_DB),
        ("core.queue.esi_req",     LOG_ESI),
        ("core.queue",             LOG_SYSTEM),
        ("core.scheduler",         LOG_SCHEDULER),
        ("core.esi.auth",          LOG_AUTH),
        ("core.esi",               LOG_ESI),
        ("core.web.auth",          LOG_AUTH),
        ("core.web",               LOG_WEB),
        ("core.config",            LOG_SYSTEM),
        ("core.bus",               LOG_SYSTEM),
        ("core",                   LOG_SYSTEM),
        ("analysis.market",        LOG_MARKET),
        ("analysis.structures",    LOG_STRUCTURES),
        ("analysis.character",     LOG_CHARACTER),
        ("analysis.sde_loader",    LOG_DB),
        ("analysis",               LOG_SYSTEM),
        ("applications",           LOG_APP),
        ("__main__",               LOG_SYSTEM),
    ],
    key=lambda t: len(t[0]),
    reverse=True,  # longest first
)


def classify(logger_name: str) -> str:
    """Return the topic for *logger_name* by longest prefix match.

    Always returns a ``log/`` topic.  Falls back to ``log/system`` if no
    prefix matches.
    """
    for prefix, topic in _PREFIX_MAP:
        if logger_name == prefix or logger_name.startswith(prefix + "."):
            return topic
    return LOG_SYSTEM
