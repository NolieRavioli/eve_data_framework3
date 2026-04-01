# applications/scheduler/__init__.py
"""Scheduler admin UI — manage background job intervals and trigger manual runs."""

from __future__ import annotations

from flask import Blueprint

from applications._base import BaseTool, ToolManifest
from applications.scheduler import routes


class SchedulerTool(BaseTool):
    manifest = ToolManifest(
        id="scheduler",
        name="Scheduler",
        icon="⏱",
        description="Manage recurring background jobs: enable/disable, set intervals, run on demand.",
        url_prefix="/admin/scheduler",
        required_scopes=[],
        nav_weight=5,
        nav_section="admin",
        access_level="admin",
    )

    def create_blueprint(self) -> Blueprint:
        return routes.scheduler_bp


Tool = SchedulerTool()
