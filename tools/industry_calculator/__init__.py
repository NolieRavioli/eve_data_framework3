# tools/industry_calculator/__init__.py
from __future__ import annotations

from flask import Blueprint

from tools._base import BaseTool, ToolManifest
from tools.industry_calculator import routes


class IndustryCalculatorTool(BaseTool):
    manifest = ToolManifest(
        id="industry_calculator",
        name="Industry Calc",
        icon="⚙",
        description="Calculate manufacturing costs and margins for blueprints.",
        url_prefix="/tools/industry",
        required_scopes=[],
        nav_weight=20,
    )

    def create_blueprint(self) -> Blueprint:
        return routes.industry_bp
