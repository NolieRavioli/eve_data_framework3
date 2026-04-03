"""SSE generators and IO routing for the task queue.

Split from the original ``tasks/task_queue.py`` — this half owns the
thread-aware stdout/stderr interceptor, the ESI rate hook, and the SSE
stream generators (rate_stream, log_stream).
"""

import io
import json
import logging
import sys
import threading
from datetime import datetime, timezone

from core.queue.scheduler import _thread_task, _registry, _registry_lock, get_all_tasks


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
    from core.queue.esi_req import set_post_request_hook as _set_esi_hook
    _set_esi_hook(_esi_rate_hook)
except Exception:
    pass


def _esi_detail_hook(method: str, url: str, status_code: int, elapsed_ms: int) -> None:
    """Called by esi_req after every real HTTP response — records on the running task."""
    task_id = getattr(_thread_task, "task_id", None)
    if not task_id:
        return
    task = _registry.get(task_id)
    if task:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        task.add_esi_request({"ts": ts, "method": method, "url": url, "status": status_code, "ms": elapsed_ms})


try:
    from core.queue.esi_req import set_post_request_detail_hook as _set_esi_detail_hook
    _set_esi_detail_hook(_esi_detail_hook)
except Exception:
    pass


# ── SSE generators ────────────────────────────────────────────────────────────
def rate_stream():
    """Generator for SSE — yields ESI rate-limiter stats after every request.

    Waits on a shared threading.Event that the _esi_rate_hook sets whenever
    new stats arrive, so the stream only pushes when something actually changed.
    Falls back to a 5 s keepalive tick so the connection stays alive while idle.
    """
    from core.queue.esi_req import get_esi_rate_limiter

    last = None
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
    esi_sent = 0
    last_esi_rate = None
    while True:
        lines = task.snapshot()
        for line in lines[sent:]:
            safe = line.replace("\n", " ").replace("\r", "")
            yield f"data: {safe}\n\n"
        sent = len(lines)

        esi_entries = task.esi_requests_snapshot()
        if len(esi_entries) > esi_sent:
            yield f"event: esi_requests\ndata: {json.dumps(esi_entries[esi_sent:])}\n\n"
            esi_sent = len(esi_entries)

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
