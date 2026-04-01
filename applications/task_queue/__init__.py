# applications/task_queue/__init__.py
"""Task Queue application — background job progress, log streaming, and ESI rate stats."""

from __future__ import annotations

from flask import Blueprint

from applications._base import BaseTool, ToolManifest
from applications.task_queue import routes


class TaskQueueTool(BaseTool):
    manifest = ToolManifest(
        id="task_queue",
        name="Task Queue",
        icon="=",
        description="Monitor background tasks, stream live logs, and inspect ESI rate stats.",
        url_prefix="/tasks",
        required_scopes=[],
        nav_weight=-50,
        nav_section="tools",
    )

    def create_blueprint(self) -> Blueprint:
        return routes.tasks_bp


Tool = TaskQueueTool()
