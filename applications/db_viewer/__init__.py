# applications/db_viewer/__init__.py
"""Database Viewer application — DB statistics, schema browser, and SQL query tool."""

from __future__ import annotations

from flask import Blueprint

from applications._api import BaseTool, ToolManifest
from applications.db_viewer import routes


class DBViewer(BaseTool):
    manifest = ToolManifest(
        id="db_viewer",
        name="Database",
        icon="🗃️",
        description="Database statistics, schema browser, and SQL query tool.",
        url_prefix="/db",
        required_scopes=[],
        nav_weight=5,
        nav_section="tools",
        access_level="user",
        required_role="db",
    )

    def create_blueprint(self) -> Blueprint:
        return routes.db_bp


Tool = DBViewer()
