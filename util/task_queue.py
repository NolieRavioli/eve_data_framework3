# util/task_queue.py
"""
Background task queue with live SSE log streaming.

Both logging calls AND print() statements in worker threads are captured:
  - A custom logging.Handler routes log records to the running Task.
  - sys.stdout/stderr are replaced with thread-aware wrappers that buffer
    each worker thread's output and flush complete lines to the Task log,
    while still passing through to the original real streams.
"""

import io
import json
import logging
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Optional


# ── Per-thread task tracking ─────────────────────────────────────────────────
_thread_task: threading.local = threading.local()

# ── Registry ─────────────────────────────────────────────────────────────────
_registry: dict[str, "Task"] = {}
_registry_lock = threading.Lock()


# ── Thread-aware stdout/stderr interceptor ───────────────────────────────────
class _ThreadRoutedWriter:
    """
    Drop-in replacement for sys.stdout / sys.stderr.

    Writes from worker threads that own a running Task are buffered per-thread
    and flushed as complete lines into that Task's log.  Writes from all other
    threads pass straight through to the original stream unchanged.
    """

    def __init__(self, original):
        self._original = original
        self._local = threading.local()   # per-thread line buffer

    # CPython dict.get is GIL-protected for simple reads — no extra lock needed.
    def _current_task(self):
        task_id = getattr(_thread_task, "task_id", None)
        if not task_id:
            return None
        return _registry.get(task_id)

    def write(self, text: str) -> int:
        if self._original:
            try:
                self._original.write(text)
            except Exception:
                pass

        task = self._current_task()
        if task is None:
            return len(text)

        buf = getattr(self._local, "buf", "")
        buf += text

        # Eat carriage-return overwrite style output (e.g. tqdm progress bars)
        if "\r" in buf and "\n" not in buf:
            buf = buf.rsplit("\r", 1)[-1]

        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            stripped = line.rstrip("\r")
            if stripped.strip():
                task.add_log(stripped)

        self._local.buf = buf
        return len(text)

    def flush(self):
        if self._original:
            try:
                self._original.flush()
            except Exception:
                pass
        task = self._current_task()
        buf = getattr(self._local, "buf", "")
        if buf.strip() and task:
            task.add_log(buf.strip())
        self._local.buf = ""

    def isatty(self) -> bool:
        return False

    def readable(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def fileno(self) -> int:
        if self._original and hasattr(self._original, "fileno"):
            return self._original.fileno()
        raise io.UnsupportedOperation("fileno")

    @property
    def encoding(self) -> str:
        return getattr(self._original, "encoding", "utf-8") or "utf-8"

    @property
    def errors(self) -> str:
        return getattr(self._original, "errors", "replace") or "replace"


# Install interceptors once at module load (idempotent — already-wrapped is a no-op).
if not isinstance(sys.stdout, _ThreadRoutedWriter):
    _orig_stdout = sys.stdout
    sys.stdout = _ThreadRoutedWriter(_orig_stdout)
if not isinstance(sys.stderr, _ThreadRoutedWriter):
    _orig_stderr = sys.stderr
    sys.stderr = _ThreadRoutedWriter(_orig_stderr)


# ── ESI rate-limit hook ───────────────────────────────────────────────────────
_rate_event: threading.Event = threading.Event()


def _esi_rate_hook(stats: dict) -> None:
    """Called by esi_rate_limiter after each real HTTP request."""
    task_id = getattr(_thread_task, "task_id", None)
    if not task_id:
        _rate_event.set()
        return
    task = _registry.get(task_id)
    if task:
        task.update_esi_rate(stats)
    _rate_event.set()


try:
    from util.esi_rate_limiter import set_post_request_hook as _set_esi_hook
    _set_esi_hook(_esi_rate_hook)
except Exception:
    pass


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
# Two single-threaded executors — public tasks run in parallel with private tasks
# but each queue is strictly serial (FIFO).  The ESI alternating gate ensures
# that when both queues are active they interleave one-for-one at the HTTP level.
_public_executor  = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tq-pub")
_private_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tq-prv")


def _run(task: Task, fn: Callable, args: tuple, kwargs: dict) -> None:
    if task.status == "cancelled":
        return
    _thread_task.task_id = task.task_id
    try:
        from util.esi_rate_limiter import set_request_lane
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


def rate_stream():
    """Generator for SSE — yields ESI rate-limiter stats after every request.

    Waits on a shared threading.Event that the _esi_rate_hook sets whenever
    new stats arrive, so the stream only pushes when something actually changed.
    Falls back to a 5 s keepalive tick so the connection stays alive while idle.
    """
    import json
    from util.esi_rate_limiter import get_esi_rate_limiter

    last: Optional[dict] = None
    while True:
        _rate_event.wait(timeout=5.0)
        _rate_event.clear()
        tasks = get_all_tasks()
        stats = get_esi_rate_limiter().get_stats()
        payload = {"limiter": stats, "tasks": [t.brief_dict() for t in tasks]}
        if payload != last:
            last = payload
            yield f"data: {json.dumps(payload)}\n\n"
        else:
            yield ": keepalive\n\n"


def log_stream(task_id: str):
    """Generator for SSE — yields task log lines then a final 'done' event.

    Reconnecting clients (page reload) receive all previous lines immediately,
    then stream new lines until the task finishes.
    """
    task = _registry.get(task_id)
    if not task:
        yield "data: Task not found.\n\n"
        yield "event: done\ndata: notfound\n\n"
        return

    sent = 0
    last_esi_rate = None
    while True:
        lines = task.snapshot()
        for line in lines[sent:]:
            safe = line.replace("\n", " ").replace("\r", "")
            yield f"data: {safe}\n\n"
        sent = len(lines)

        current_esi_rate = task.esi_rate
        if current_esi_rate is not None and current_esi_rate is not last_esi_rate:
            yield f"event: esi_rate\ndata: {json.dumps(current_esi_rate)}\n\n"
            last_esi_rate = current_esi_rate

        if task.status in ("complete", "failed", "cancelled"):
            yield f"event: done\ndata: {task.status}\n\n"
            break

        # Block until new output or 2 s keepalive tick
        task._event.wait(timeout=2.0)
        task._event.clear()
