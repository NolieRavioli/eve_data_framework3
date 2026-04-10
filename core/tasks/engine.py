"""core/tasks/scheduler.py — SchedulerEngine daemon.

A background thread that fires registered jobs when their next_run is due.
Jobs and their state (enabled, last_run, next_run) are persisted in the
public DuckDB `scheduler_jobs` table so user customisations survive restarts.

Usage (called once from create_app):

    from core.tasks.engine import get_engine
    engine = get_engine()
    engine.start()          # starts daemon thread; safe to call multiple times

Public interface (also exposed via the scheduler adapter in applications/_api.py):

    engine.list_jobs()      -> list[dict]
    engine.set_enabled(job_id, enabled)
    engine.run_now(job_id)  -> str   (task_id)
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

_TICK_INTERVAL = 30  # seconds between scheduler checks


class SchedulerEngine:
    """Interval-based background job scheduler backed by DuckDB."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # fn_registry maps job_id -> callable for use at runtime
        self._fn_registry: dict[str, Callable] = {}
        # category_registry maps job_id -> category label (UI use only)
        self._category_registry: dict[str, str] = {}
        self._thread: threading.Thread | None = None
        self._stop_evt = threading.Event()
        self._started = False

    # ------------------------------------------------------------------
    # Registration (called at startup before start())
    # ------------------------------------------------------------------

    def register(
        self,
        *,
        job_id: str,
        label: str,
        fn: Callable,
        fn_path: str,
        interval_s: int,
        category: str = "other",
    ) -> None:
        """Declare a job.  Upserts metadata into DuckDB, stores callable locally."""
        with self._lock:
            self._fn_registry[job_id] = fn
            self._category_registry[job_id] = category

        import core.io.public as db
        from core.tasks.persist import ensure_tables, upsert_job_registration

        con = db.connect()
        try:
            ensure_tables(con)
            upsert_job_registration(con, job_id, label, fn_path, interval_s)
        finally:
            con.close()

        logger.debug("[Scheduler] Registered job '%s' every %ds", job_id, interval_s)

    # ------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background tick thread (idempotent)."""
        if self._started:
            return
        self._started = True
        self._thread = threading.Thread(
            target=self._tick_loop,
            name="scheduler-engine",
            daemon=True,
        )
        self._thread.start()
        logger.info("[Scheduler] Engine started (tick every %ds)", _TICK_INTERVAL)

        # Register with the central lifecycle coordinator.
        try:
            from core.system import get_lifecycle
            get_lifecycle().register("scheduler-engine", self._thread, stop_fn=self._stop_evt.set)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public interface (used by scheduler adapter in _api.py)
    # ------------------------------------------------------------------

    def list_jobs(self) -> list[dict]:
        import core.io.public as db
        from core.tasks.persist import ensure_tables, get_all_jobs

        con = db.connect()
        try:
            ensure_tables(con)
            jobs = get_all_jobs(con)
        finally:
            con.close()
        # Augment with in-memory category (not stored in DB)
        with self._lock:
            cat = dict(self._category_registry)
        for job in jobs:
            job["category"] = cat.get(job["job_id"], "other")
        return jobs

    def set_enabled(self, job_id: str, enabled: bool) -> None:
        import core.io.public as db
        from core.tasks.persist import ensure_tables, set_enabled

        con = db.connect()
        try:
            ensure_tables(con)
            set_enabled(con, job_id, enabled)
        finally:
            con.close()
        logger.info("[Scheduler] Job '%s' enabled=%s", job_id, enabled)

    def run_now(self, job_id: str) -> str:
        """Schedule *job_id* to fire on the next tick and return the task_id."""
        import core.io.public as db
        from core.tasks.persist import ensure_tables, run_job_now

        con = db.connect()
        try:
            ensure_tables(con)
            run_job_now(con, job_id)
        finally:
            con.close()

        # Immediately enqueue rather than waiting for the next tick
        return self._fire_job(job_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _tick_loop(self) -> None:
        while not self._stop_evt.is_set():
            try:
                self._tick()
            except Exception:
                logger.exception("[Scheduler] Unhandled error in tick loop")
            self._stop_evt.wait(timeout=_TICK_INTERVAL)

    def _tick(self) -> None:
        import core.io.public as db
        from core.tasks.persist import ensure_tables, get_due_jobs, mark_job_ran

        con = db.connect()
        try:
            ensure_tables(con)
            due = get_due_jobs(con)
            for job in due:
                job_id = job["job_id"]
                interval = job["interval_seconds"]
                mark_job_ran(con, job_id, interval)
                self._fire_job(job_id)
        finally:
            con.close()

    def _fire_job(self, job_id: str) -> str:
        fn = self._fn_registry.get(job_id)
        if fn is None:
            logger.warning("[Scheduler] No callable registered for job '%s'", job_id)
            return ""

        from core.tasks.queue import enqueue
        label = job_id.replace("_", " ").title()
        task_id = enqueue(label, fn, owner_id=0, queue="public")
        logger.info("[Scheduler] Fired job '%s' → task %s", job_id, task_id)
        return task_id


# ---------------------------------------------------------------------------
# Module-level singleton — used by _api.py and create_app()
# ---------------------------------------------------------------------------

_engine: SchedulerEngine | None = None
_engine_lock = threading.Lock()


def get_engine() -> SchedulerEngine:
    """Return the global SchedulerEngine singleton, creating it if necessary."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = SchedulerEngine()
    return _engine
