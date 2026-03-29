# tools/__init__.py
"""Tools package — port/adapter framework for EVE Data Framework web tools.

The ``tool_registry`` singleton is imported by ``webUI/__init__.py`` to register
blueprints, and by ``webUI/context.py`` to populate the sidebar nav.
"""

from tools._base import ToolRegistry
from tools.market_browser import MarketBrowserTool
from tools.industry_calculator import IndustryCalculatorTool
from tools.isk_per_hour import IskPerHourTool

tool_registry: ToolRegistry = ToolRegistry()
tool_registry.register(MarketBrowserTool())
tool_registry.register(IndustryCalculatorTool())
tool_registry.register(IskPerHourTool())

__all__ = ["tool_registry"]
