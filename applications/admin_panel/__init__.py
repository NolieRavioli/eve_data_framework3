# applications/admin_panel/__init__.py
"""Admin Panel application — live logs, DB browser, user management, ESI Explorer."""

from __future__ import annotations

from flask import Blueprint

from applications._base import BaseTool, ToolManifest
from applications.admin_panel import routes


class AdminPanelTool(BaseTool):
    manifest = ToolManifest(
        id="admin_panel",
        name="Admin Panel",
        icon="!",
        description="Live log console, DuckDB browser, user management, and ESI Explorer.",
        url_prefix="/admin",
        required_scopes=[],
        nav_weight=0,
        nav_section="admin",
    )

    def create_blueprint(self) -> Blueprint:
        return routes.admin_bp


Tool = AdminPanelTool()
