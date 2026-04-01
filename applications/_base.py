"""Re-export plugin framework for applications.

Applications should import from here, not from core.plugin.* directly.
"""
from core.plugin.base import BaseTool, ToolManifest, ToolRegistry, ACCESS_LEVELS
from core.plugin.web import base_ctx, require_login, require_admin, require_role

__all__ = [
    "BaseTool", "ToolManifest", "ToolRegistry", "ACCESS_LEVELS",
    "base_ctx", "require_login", "require_admin", "require_role",
]
