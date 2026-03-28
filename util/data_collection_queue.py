# util/data_collection_queue.py
"""
Background task queue for ESI data collection.

Uses a floating-window rate limiter (already implemented in esi_rate_limiter.py)
for per-request throttling. This queue serializes high-level collection tasks
so multiple characters don't all blast ESI simultaneously, and handles HTTP 429
by re-queuing the task after the Retry-After delay.
"""
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class CollectionTask:
    """A single unit of work for the background worker."""
    owner_id: int
    label: str               # human-readable name for logging
    fn: Callable             # callable to invoke
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    retries: int = 0
    max_retries: int = 5


class DataCollectionQueue:
    """
    Singleton background worker that drains a task queue.

    - Tasks are `CollectionTask` instances placed via `enqueue()`.
    - On HTTP 429 (rate-limit) the task is re-queued after sleeping Retry-After seconds.
    - On any other exception the error is logged and the task is dropped.
    - `last_run_times` records the finish time of the last successful run per label.
    """

    _instance: Optional["DataCollectionQueue"] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._queue: queue.Queue[CollectionTask] = queue.Queue()
        self.last_run_times: Dict[str, datetime] = {}
        self._thread = threading.Thread(target=self._worker, daemon=True, name="DataCollectionWorker")
        self._initialized = True

    def start(self):
        if not self._thread.is_alive():
            self._thread.start()
            logger.info("[DataCollectionQueue] Background worker started.")

    def enqueue(self, task: CollectionTask):
        self._queue.put(task)
        logger.debug(f"[DataCollectionQueue] Enqueued: {task.label} (owner={task.owner_id})")

    def queue_depth(self) -> int:
        return self._queue.qsize()

    # ── private ──────────────────────────────────────────────────────────────

    def _worker(self):
        while True:
            task = self._queue.get()
            try:
                logger.info(f"[Queue] Running: {task.label} (owner={task.owner_id})")
                task.fn(*task.args, **task.kwargs)
                self.last_run_times[task.label] = datetime.utcnow()
                logger.info(f"[Queue] Done: {task.label}")
            except Exception as exc:
                retry_after = self._extract_retry_after(exc)
                if retry_after is not None and task.retries < task.max_retries:
                    logger.warning(
                        f"[Queue] Rate-limited on {task.label}. "
                        f"Sleeping {retry_after}s then re-queuing (retry {task.retries + 1})."
                    )
                    time.sleep(retry_after)
                    task.retries += 1
                    self._queue.put(task)
                else:
                    logger.error(f"[Queue] Failed {task.label}: {exc}", exc_info=True)
            finally:
                self._queue.task_done()

    @staticmethod
    def _extract_retry_after(exc: Exception) -> Optional[float]:
        """
        Try to pull a Retry-After value from the exception.
        requests.HTTPError attaches the response object; we also check for a
        custom attribute set by esi_rate_limiter on 429.
        """
        # requests.HTTPError
        resp = getattr(exc, "response", None)
        if resp is not None and getattr(resp, "status_code", None) == 429:
            retry_after = resp.headers.get("Retry-After", "60")
            try:
                return float(retry_after)
            except (ValueError, TypeError):
                return 60.0
        # RateLimitError raised by esi_rate_limiter
        if hasattr(exc, "retry_after"):
            return float(exc.retry_after)
        return None


# ── module-level accessor ─────────────────────────────────────────────────────

_queue_singleton: Optional[DataCollectionQueue] = None


def get_collection_queue() -> DataCollectionQueue:
    global _queue_singleton
    if _queue_singleton is None:
        _queue_singleton = DataCollectionQueue()
        _queue_singleton.start()
    return _queue_singleton
