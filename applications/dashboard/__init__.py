# applications/dashboard/__init__.py
"""Dashboard application — character overview and session info."""

from __future__ import annotations

from flask import Blueprint

from applications._base import BaseTool, ToolManifest
from applications.dashboard import routes


class DashboardTool(BaseTool):
    manifest = ToolManifest(
        id="dashboard",
        name="Dashboard",
        icon="🏠︎",
        description="Character overview, active ESI spec status, and granted scopes.",
        url_prefix="/dashboard",
        required_scopes=[],
        nav_weight=-100,
        nav_section="overview",
        access_level="user",
        required_role="dashboard",
    )

    def create_blueprint(self) -> Blueprint:
        return routes.dashboard_bp


Tool = DashboardTool()
