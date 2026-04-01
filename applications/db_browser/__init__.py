# applications/db_browser/__init__.py
"""DB Browser application — browse DuckDB public warehouse and per-owner SQLite databases."""

from __future__ import annotations

from flask import Blueprint

from applications._base import BaseTool, ToolManifest
from applications.db_browser import routes


class DBBrowserTool(BaseTool):
    manifest = ToolManifest(
        id="db_browser",
        name="DB Browser",
        icon="⛁",
        description="Browse and query DuckDB warehouse and per-owner SQLite databases.",
        url_prefix="/admin/db_browser",
        required_scopes=[],
        nav_weight=5,
        nav_section="admin",
        access_level="admin",
    )

    def create_blueprint(self) -> Blueprint:
        return routes.db_bp


Tool = DBBrowserTool()
