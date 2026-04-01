# tools/isk_per_hour/__init__.py
from __future__ import annotations

from flask import Blueprint

from applications._base import BaseTool, ToolManifest
from applications.isk_per_hour import routes


class IskPerHourTool(BaseTool):
    manifest = ToolManifest(
        id="isk_per_hour",
        name="ISK / hr",
        icon="💰",
        description="Rank manufacturing blueprints by ISK earned per hour.",
        url_prefix="/tools/isk_per_hour",
        required_scopes=[],
        nav_weight=30,
    )

    def create_blueprint(self) -> Blueprint:
        return routes.isk_bp


Tool = IskPerHourTool()
