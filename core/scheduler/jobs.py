"""core/scheduler/jobs.py — hardcoded job catalog.

Call register_all_jobs(engine) once at startup.  The scheduler engine calls
this after its own table is ready so that job rows exist before the first tick.

To add a new scheduled job:
  1. Import the worker function (or reference it by dotted path).
  2. Append an entry to _JOBS.

Fields:
    job_id          — stable identifier; changing this creates a new row
    label           — display name shown in the scheduler UI
    fn              — callable (used at runtime); fn_path is derived automatically
    interval_s      — default interval in seconds
"""

from __future__ import annotations

import importlib
import logging

logger = logging.getLogger(__name__)


def _path(fn) -> str:
    return f"{fn.__module__}.{fn.__qualname__}"


# ---------------------------------------------------------------------------
# Job catalog — add new jobs here
# ---------------------------------------------------------------------------

def _build_catalog() -> list[dict]:
    jobs = []

    try:
        from analysis.market.publicRegions import fetch_all_market_data
        jobs.append({
            "job_id": "market_refresh",
            "label": "Market Data Refresh",
            "fn": fetch_all_market_data,
            "fn_path": _path(fetch_all_market_data),
            "interval_s": 3600,
        })
    except Exception:
        logger.warning("[SchedulerJobs] Could not import market collector — skipping job")

    try:
        from analysis.structures.publicDiscovery import discover_structures
        jobs.append({
            "job_id": "structure_discovery",
            "label": "Structure Discovery",
            "fn": discover_structures,
            "fn_path": _path(discover_structures),
            "interval_s": 86400,
        })
    except Exception:
        logger.warning("[SchedulerJobs] Could not import structure collector — skipping job")

    try:
        from analysis.character.populate import populate_all  # noqa: F401  verify importable
        jobs.append({
            "job_id": "character_refresh",
            "label": "Character Data Refresh (all owners)",
            "fn": _refresh_all_characters,
            "fn_path": f"{__name__}._refresh_all_characters",
            "interval_s": 86400,
        })
    except Exception:
        logger.warning("[SchedulerJobs] Could not import character collector — skipping job")

    return jobs


def _refresh_all_characters() -> None:
    """Refresh character data for every known owner."""
    import core.db.publicDB as db

    con = db.connect()
    try:
        rows = con.execute("SELECT DISTINCT owner_id FROM users").fetchall()
        owner_ids = [r[0] for r in rows]
    finally:
        con.close()

    from analysis.character.populate import populate_all
    for owner_id in owner_ids:
        try:
            populate_all(owner_id)
        except Exception:
            logger.exception("[SchedulerJobs] character_refresh failed for owner %s", owner_id)


# Module-level catalog — built once on import
CATALOG: list[dict] = _build_catalog()


def register_all_jobs(engine) -> None:
    """Upsert all catalog entries into the scheduler_jobs table via *engine*."""
    from core.scheduler.db import upsert_job_registration
    for job in CATALOG:
        engine.register(
            job_id=job["job_id"],
            label=job["label"],
            fn=job["fn"],
            fn_path=job["fn_path"],
            interval_s=job["interval_s"],
        )
