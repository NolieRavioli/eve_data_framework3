# applications/sys_status/__init__.py
"""System Status application — live DB writer metrics, file stats, and scheduler health."""

from __future__ import annotations

from flask import Blueprint

from applications._base import BaseTool, ToolManifest
from applications.sys_status import routes


class SysStatusTool(BaseTool):
    manifest = ToolManifest(
        id="sys_status",
        name="System Status",
        icon="⊞",
        description="Live writer queue depth, database file stats, and process health.",
        url_prefix="/admin/sys_status",
        required_scopes=[],
        nav_weight=90,
        nav_section="admin",
        access_level="admin",
        required_role=None,
    )

    def create_blueprint(self) -> Blueprint:
        return routes.sys_bp


Tool = SysStatusTool()
