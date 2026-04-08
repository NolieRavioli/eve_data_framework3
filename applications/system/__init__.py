# applications/system/__init__.py
"""System Status application — process health metrics and live bus log viewer."""

from __future__ import annotations

from flask import Blueprint

from applications._api import BaseTool, ToolManifest
from applications.system import routes


class SystemStatus(BaseTool):
    manifest = ToolManifest(
        id="system",
        name="System",
        icon="⚙️",
        description="Python runtime overview, process metrics, and system updates.",
        url_prefix="/system",
        required_scopes=[],
        nav_weight=90,
        nav_section="admin",
        access_level="admin",
        required_role=None,
    )

    def create_blueprint(self) -> Blueprint:
        return routes.sys_bp


Tool = SystemStatus()
