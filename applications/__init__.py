# applications/__init__.py
"""Applications package — port/adapter framework for EVE Data Framework applications.

The ``tool_registry`` singleton is imported by ``webUI/__init__.py`` to register
blueprints, and by ``webUI/context.py`` to populate the sidebar nav.
"""

from applications._base import ToolRegistry
from applications.market_browser import MarketBrowserTool
from applications.industry_calculator import IndustryCalculatorTool
from applications.isk_per_hour import IskPerHourTool

tool_registry: ToolRegistry = ToolRegistry()
tool_registry.register(MarketBrowserTool())
tool_registry.register(IndustryCalculatorTool())
tool_registry.register(IskPerHourTool())

__all__ = ["tool_registry"]
