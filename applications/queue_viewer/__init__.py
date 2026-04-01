# applications/queue_viewer/__init__.py
"""Queue Viewer application — background job progress, log streaming, and ESI rate stats."""

from __future__ import annotations

from flask import Blueprint

from applications._base import BaseTool, ToolManifest
from applications.queue_viewer import routes


class QueueViewerTool(BaseTool):
    manifest = ToolManifest(
        id="queue_viewer",
        name="Queue Viewer",
        icon="=",
        description="Monitor background tasks, stream live logs, and inspect ESI rate stats.",
        url_prefix="/tasks",
        required_scopes=[],
        nav_weight=-50,
        nav_section="tools",
    )

    def create_blueprint(self) -> Blueprint:
        return routes.tasks_bp


Tool = QueueViewerTool()
