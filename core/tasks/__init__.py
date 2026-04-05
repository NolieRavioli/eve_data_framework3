"""core/tasks — background task management and data pipeline tasks.

This package is the home for long-running or scheduled operations that are
driven by the framework itself rather than a user request.  It contains:

- scheduler.py        SchedulerEngine — interval-based background job runner
- scheduler_db.py     DuckDB DDL/CRUD for the scheduler_jobs table
- scheduler_jobs.py   Job catalog — add new scheduled analysis jobs here
- sde_loader.py       SDE pipeline — download, extract, build the DuckDB warehouse

Domain rule: core/tasks/ may import from core.* but never from applications/*.
Analysis collectors (analysis.*) may also import from here (e.g. sde_loader).
"""

from core.tasks.scheduler import get_engine, SchedulerEngine
from core.tasks.scheduler_jobs import register_all_jobs

__all__ = [
    "get_engine",
    "SchedulerEngine",
    "register_all_jobs",
]
