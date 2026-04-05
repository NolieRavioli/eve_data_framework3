# applications/esi_browser/__init__.py
"""ESI Browser application — browse, search, and execute ESI operations."""

from __future__ import annotations

from flask import Blueprint

from applications._api import BaseTool, ToolManifest
from applications.esi_browser import routes


class ESIBrowserTool(BaseTool):
    manifest = ToolManifest(
        id="esi_browser",
        name="ESI Explorer",
        icon="⚡",
        description="Browse, search, and execute all ESI operations with live results.",
        url_prefix="/admin/esi",
        required_scopes=[],
        nav_weight=6,
        nav_section="admin",
        access_level="admin",
    )

    def create_blueprint(self) -> Blueprint:
        return routes.esi_bp


Tool = ESIBrowserTool()
