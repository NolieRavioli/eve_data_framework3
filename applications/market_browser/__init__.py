# tools/market_browser/__init__.py
from __future__ import annotations

from flask import Blueprint

from applications._base import BaseTool, ToolManifest
from applications.market_browser import routes


class MarketBrowserTool(BaseTool):
    manifest = ToolManifest(
        id="market_browser",
        name="Market Browser",
        icon="📊",
        description="Browse live market orders by region and item type.",
        url_prefix="/tools/market",
        required_scopes=[],
        nav_weight=10,
    )

    def create_blueprint(self) -> Blueprint:
        return routes.market_bp


Tool = MarketBrowserTool()
