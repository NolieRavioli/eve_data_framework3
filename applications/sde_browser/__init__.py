# applications/sde_browser/__init__.py
"""SDE Browser application — Static Data Edition browser and lookup tool."""

from __future__ import annotations

from flask import Blueprint

from applications._api import BaseTool, ToolManifest
from applications.sde_browser import routes


class SDEBrowser(BaseTool):
    manifest = ToolManifest(
        id="sde_browser",
        name="SDE Browser",
        icon="📚",
        description="Static Data Edition browser and lookup tool.",
        url_prefix="/sde",
        required_scopes=[],
        nav_weight=10,
        nav_section="admin",
        access_level="admin",
        required_role=None,
    )

    def create_blueprint(self) -> Blueprint:
        return routes.sde_bp


Tool = SDEBrowser()
