# applications/__init__.py
"""Applications package — port/adapter framework for EVE Data Framework applications.

The ``tool_registry`` singleton is imported by ``webUI/__init__.py`` to register
blueprints, and by ``webUI/context.py`` to populate the sidebar nav.

Applications are auto-discovered via pkgutil: every sub-package that exposes a
``Tool`` attribute (an instance of :class:`_base.ToolBase`) is registered
automatically.
"""

import importlib
import logging
import pkgutil

from applications._base import ToolRegistry

logger = logging.getLogger(__name__)
tool_registry: ToolRegistry = ToolRegistry()


def _auto_discover() -> None:
    """Walk sub-packages and register any that expose a ``Tool`` attribute."""
    import applications as _pkg

    for finder, name, is_pkg in pkgutil.iter_modules(_pkg.__path__, _pkg.__name__ + "."):
        if name.startswith("applications._"):
            continue  # skip private helpers (_base, _adapters, _ports)
        if not is_pkg:
            continue
        try:
            mod = importlib.import_module(name)
        except Exception:
            logger.debug("Skipping application %s (import failed)", name, exc_info=True)
            continue
        tool = getattr(mod, "Tool", None)
        if tool is not None:
            tool_registry.register(tool)
            logger.debug("Auto-registered application: %s", name)


_auto_discover()

__all__ = ["tool_registry"]
