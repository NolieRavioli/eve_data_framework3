"""Shared thread-local context for identifying the active task.

This module exists solely to break an import cycle: both ``queue.py``
(which sets ``_thread_task.task_id``) and ``core.io.writer`` (which reads it
for write attribution) need access to the same ``threading.local``.
"""
import threading

_thread_task: threading.local = threading.local()
