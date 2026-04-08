# applications/task_viewer/__init__.py
"""Task Viewer application — task queue, scheduler, ESI rate monitoring, and API explorer."""

from __future__ import annotations

from flask import Blueprint

from applications._api import BaseTool, ToolManifest
from applications.task_viewer import routes


class TaskViewer(BaseTool):
    manifest = ToolManifest(
        id="task_viewer",
        name="Task Manager",
        icon="📋",
        description="Background task queue, scheduler, ESI rate monitoring, and API explorer.",
        url_prefix="/tasks",
        required_scopes=[],
        nav_weight=-50,
        nav_section="tools",
        access_level="user",
        required_role="tasks",
    )

    def create_blueprint(self) -> Blueprint:
        return routes.tasks_bp


Tool = TaskViewer()
