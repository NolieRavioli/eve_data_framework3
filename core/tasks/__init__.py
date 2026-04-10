"""Task execution and scheduling.

Task queue:   enqueue() → Task runs in ThreadPoolExecutor → logs stream via bus
Scheduler:    SchedulerEngine ticks every 30s, fires due jobs via enqueue()
Output:       stdout/stderr capture + SSE generators for live task logs
"""

from core.tasks.queue import (
    Task,
    enqueue,
    get_task,
    get_tasks_for_owner,
    get_all_tasks,
    cancel_task,
    clear_tasks,
)
from core.tasks.output import rate_stream, log_stream
from core.tasks.engine import get_engine, SchedulerEngine
from core.tasks.jobs import register_all_jobs

# Writer thread start/stop stays in core.io.writer — it's a DB concern
from core.io.writer import start_writer, stop_writer

__all__ = [
    "Task", "enqueue", "get_task", "get_tasks_for_owner", "get_all_tasks",
    "cancel_task", "clear_tasks",
    "rate_stream", "log_stream",
    "get_engine", "SchedulerEngine", "register_all_jobs",
    "start_writer", "stop_writer",
]
