# tools/industry_calculator/__init__.py
from __future__ import annotations

from flask import Blueprint

from applications._base import BaseTool, ToolManifest
from applications.industry_calculator import routes


class IndustryCalculatorTool(BaseTool):
    manifest = ToolManifest(
        id="industry_calculator",
        name="Industry Calc",
        icon="⚙",
        description="Calculate manufacturing costs and margins for blueprints.",
        url_prefix="/industry",
        required_scopes=[],
        nav_weight=20,
        access_level="user",
        required_role="industry",
    )

    def create_blueprint(self) -> Blueprint:
        return routes.industry_bp


Tool = IndustryCalculatorTool()
