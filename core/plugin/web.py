"""Flask-layer re-exports for the plugin framework.

Applications import web helpers from here (via applications._base)
instead of reaching into core.web.* directly.
"""

from core.web.context import base_ctx
from core.web.auth import require_login, require_admin

__all__ = ["base_ctx", "require_login", "require_admin"]
