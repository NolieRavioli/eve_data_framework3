# applications/admin_panel/__init__.py
"""Admin Panel application — live logs, system stats, user management."""

from __future__ import annotations

from flask import Blueprint

from applications._api import BaseTool, ToolManifest
from applications.admin_panel import routes


class AdminPanelTool(BaseTool):
    manifest = ToolManifest(
        id="admin_panel",
        name="Admin Panel",
        icon="🛡️",
        description="Live log console, system stats, and user management.",
        url_prefix="/admin",
        required_scopes=[],
        nav_weight=0,
        nav_section="admin",
        access_level="admin",
    )

    def create_blueprint(self) -> Blueprint:
        return routes.admin_bp


Tool = AdminPanelTool()
