# applications/esi_viewer/__init__.py
"""ESI Viewer application — unified ESI queue, rate monitoring, and API explorer."""

from __future__ import annotations

from flask import Blueprint

from applications._api import BaseTool, ToolManifest
from applications.esi_viewer import routes


class ESIViewer(BaseTool):
    manifest = ToolManifest(
        id="esi_viewer",
        name="ESI Queue",
        icon="⚡",
        description="ESI request queue, rate monitoring, and API explorer.",
        url_prefix="/esi",
        required_scopes=[],
        nav_weight=-50,
        nav_section="tools",
        access_level="user",
        required_role="queue",
    )

    def create_blueprint(self) -> Blueprint:
        return routes.esi_bp


Tool = ESIViewer()
