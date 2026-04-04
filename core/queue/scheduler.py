"""Task lifecycle: Task class, executor pools, enqueue/get/cancel helpers.

Split from the original ``tasks/task_queue.py`` — this half owns the task
registry and the two single-threaded executor pools (public + private).
"""

import logging
import threading
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Optional


# ── Per-thread task tracking ─────────────────────────────────────────────────
_thread_task: threading.local = threading.local()

# ── Registry ─────────────────────────────────────────────────────────────────
_registry: dict[str, "Task"] = {}
_registry_lock = threading.Lock()


class Task:
    """Represents one unit of background work."""

    def __init__(self, task_id: str, owner_id: int, name: str, queue: str = "private"):
        self.task_id = task_id
        self.owner_id = owner_id
        self.name = name
        self.queue = queue               # 'public' | 'private'
        self.status = "pending"          # pending | running | complete | failed | cancelled
        self._log: list[str] = []
        self._lock = threading.Lock()
        self._event = threading.Event()  # fires when new lines arrive or status changes
        self.created_at = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.finished_at: Optional[datetime] = None
        self.esi_rate: Optional[dict] = None
        self._esi_log: deque[dict] = deque(maxlen=500)

    def add_log(self, line: str) -> None:
        with self._lock:
            self._log.append(line)
        self._event.set()

    def update_esi_rate(self, stats: dict) -> None:
        self.esi_rate = stats
        self._event.set()

    def snapshot(self) -> list[str]:
        with self._lock:
            return list(self._log)

    def add_esi_request(self, entry: dict) -> None:
        with self._lock:
            self._esi_log.append(entry)
        self._event.set()

    def esi_requests_snapshot(self) -> list[dict]:
        with self._lock:
            return list(self._esi_log)

    def _set_status(self, s: str) -> None:
        self.status = s
        self._event.set()

    def brief_dict(self) -> dict:
        """Lightweight snapshot — no log lines; used for the rate-stream SSE payload."""
        return {
            "task_id":    self.task_id,
            "name":       self.name,
            "owner_id":   self.owner_id,
            "status":     self.status,
            "queue":      self.queue,
            "esi_rate":   self.esi_rate,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "started_at":  self.started_at.strftime("%Y-%m-%d %H:%M:%S UTC")  if self.started_at  else None,
            "finished_at": self.finished_at.strftime("%Y-%m-%d %H:%M:%S UTC") if self.finished_at else None,
        }

    def as_dict(self) -> dict:
        return {
            "task_id":    self.task_id,
            "name":       self.name,
            "owner_id":   self.owner_id,
            "status":     self.status,
            "queue":      self.queue,
            "log":        self.snapshot(),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "started_at":  self.started_at.strftime("%Y-%m-%d %H:%M:%S UTC")  if self.started_at  else None,
            "finished_at": self.finished_at.strftime("%Y-%m-%d %H:%M:%S UTC") if self.finished_at else None,
            "esi_rate":   self.esi_rate,
        }


# ── Log routing ───────────────────────────────────────────────────────────────
class _TaskLogHandler(logging.Handler):
    """Routes log records to the Task running in the current worker thread."""

    def emit(self, record: logging.LogRecord) -> None:
        task_id = getattr(_thread_task, "task_id", None)
        if not task_id:
            return
        with _registry_lock:
            task = _registry.get(task_id)
        if task:
            try:
                task.add_log(self.format(record))
            except Exception:
                pass


_log_handler = _TaskLogHandler()
_log_handler.setLevel(logging.INFO)
_log_handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
logging.getLogger().addHandler(_log_handler)


# ── Worker pool ───────────────────────────────────────────────────────────────
_public_executor  = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tq-pub")
_private_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tq-prv")


def _run(task: Task, fn: Callable, args: tuple, kwargs: dict) -> None:
    if task.status == "cancelled":
        return
    _thread_task.task_id = task.task_id
    try:
        from core.queue.esi_req import set_request_lane
        set_request_lane(task.queue)
    except Exception:
        pass

    # Ensure the root logger passes INFO so all logger.info() calls are visible.
    root = logging.getLogger()
    if root.level == logging.NOTSET or root.level > logging.INFO:
        root.setLevel(logging.INFO)

    task._set_status("running")
    task.started_at = datetime.now(timezone.utc)
    task.add_log(f"[START] {task.name}  —  {task.started_at.strftime('%H:%M:%S UTC')}")
    try:
        fn(*args, **kwargs)
        task.add_log(f"[OK] {task.name} completed successfully.")
        task._set_status("complete")
    except Exception as exc:
        task.add_log(f"[ERROR] {exc}")
        task._set_status("failed")
    finally:
        task.finished_at = datetime.now(timezone.utc)
        elapsed = (task.finished_at - task.started_at).total_seconds()
        task.add_log(f"[DONE] Finished in {elapsed:.1f}s")
        _thread_task.task_id = None


# ── Public API ────────────────────────────────────────────────────────────────
def enqueue(name: str, fn: Callable, *args, owner_id: int = 0, queue: str = "private", **kwargs) -> str:
    """Submit a task for background execution.  Returns the task_id.

    queue='public'  — public/SDE tasks (market, structures, …)
    queue='private' — personal/corp tasks (default)
    """
    task_id = uuid.uuid4().hex[:10]
    task = Task(task_id, owner_id, name, queue=queue)
    with _registry_lock:
        _registry[task_id] = task
    executor = _public_executor if queue == "public" else _private_executor
    executor.submit(_run, task, fn, args, kwargs)
    return task_id


def get_task(task_id: str) -> Optional[Task]:
    return _registry.get(task_id)


def get_tasks_for_owner(owner_id: int) -> list[Task]:
    with _registry_lock:
        return sorted(
            [t for t in _registry.values() if t.owner_id == owner_id],
            key=lambda t: t.created_at, reverse=True,
        )


def get_all_tasks() -> list[Task]:
    with _registry_lock:
        return sorted(_registry.values(), key=lambda t: t.created_at, reverse=True)


def cancel_task(task_id: str) -> bool:
    """Cancel a pending task. Returns True if successfully cancelled."""
    task = _registry.get(task_id)
    if task and task.status == "pending":
        task._set_status("cancelled")
        task.finished_at = datetime.now(timezone.utc)
        task.add_log("[CANCELLED] Removed from queue before execution.")
        return True
    return False


def clear_tasks(owner_id: Optional[int] = None) -> int:
    """Remove completed/failed/cancelled tasks. Pass owner_id=None to clear all (admin)."""
    terminal = ("complete", "failed", "cancelled")
    with _registry_lock:
        to_del = [
            tid for tid, t in _registry.items()
            if t.status in terminal and (owner_id is None or t.owner_id == owner_id)
        ]
        for tid in to_del:
            del _registry[tid]
    return len(to_del)
