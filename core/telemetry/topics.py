"""Topic constants and logger-name classifier for core.telemetry.

Every log record emitted anywhere in the application is classified into one
topic by matching its logger name against the prefix table below.  The longest
matching prefix wins; unrecognised loggers fall back to SYSTEM.
"""
from __future__ import annotations

# ── Topic constants ───────────────────────────────────────────────────────────

DB = "db"
ESI = "esi"
SCHEDULER = "scheduler"
MARKET = "market"
STRUCTURES = "structures"
CHARACTER = "character"
AUTH = "auth"
WEB = "web"
SYSTEM = "system"
APP = "app"

ALL_TOPICS: tuple[str, ...] = (
    DB, ESI, SCHEDULER, MARKET, STRUCTURES, CHARACTER, AUTH, WEB, SYSTEM, APP,
)

# Logger-name prefix → topic.  Sorted by length at import time so the
# classifier can do a simple linear scan and pick the longest winner.
_PREFIX_MAP: list[tuple[str, str]] = sorted(
    [
        ("core.db",                DB),
        ("core.queue.esi_req",     ESI),
        ("core.queue",             SYSTEM),
        ("core.scheduler",         SCHEDULER),
        ("core.esi.auth",          AUTH),
        ("core.esi",               ESI),
        ("core.web.auth",          AUTH),
        ("core.web",               WEB),
        ("core.config",            SYSTEM),
        ("core",                   SYSTEM),
        ("analysis.market",        MARKET),
        ("analysis.structures",    STRUCTURES),
        ("analysis.character",     CHARACTER),
        ("analysis.sde_loader",    DB),
        ("analysis",               SYSTEM),
        ("applications",           APP),
        ("__main__",               SYSTEM),
    ],
    key=lambda t: len(t[0]),
    reverse=True,  # longest first
)


def classify(logger_name: str) -> str:
    """Return the topic for *logger_name* by longest prefix match.

    Falls back to ``SYSTEM`` if no prefix matches.
    """
    for prefix, topic in _PREFIX_MAP:
        if logger_name == prefix or logger_name.startswith(prefix + "."):
            return topic
    return SYSTEM
