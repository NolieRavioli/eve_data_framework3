# core/web/__init__.py
"""Core web framework — Flask application factory.

This module is the *only* place where Flask is wired up.  It registers the
auth blueprint (SSO is infrastructure, not an application) and then delegates
ALL page blueprints to the application tool registry, which auto-discovers
every package that exposes a ``Tool = <BaseTool subclass instance>`` attribute.
"""

import os
from typing import Optional

from flask import Flask

from config import RuntimeSettings, get_runtime_settings
from core.web.auth import auth_bp


def create_app(settings: Optional[RuntimeSettings] = None) -> Flask:
    """Create and configure the Flask application.

    Parameters
    ----------
    settings:
        Optional pre-built RuntimeSettings.  If omitted the global singleton
        returned by :func:`get_runtime_settings` is used.
    """
    settings = settings or get_runtime_settings()
    app = Flask(__name__, template_folder="templates")
    app.secret_key = settings.session_secret or os.getenv("FLASK_SECRET_KEY", "nolieravioli")
    app.config["RUNTIME_SETTINGS"] = settings

    # Auth is core infrastructure — always registered directly.
    app.register_blueprint(auth_bp)

    # Every application (dashboard, task_queue, admin_panel, market_browser …)
    # registers itself via the shared ToolRegistry.
    from applications import tool_registry
    tool_registry.register_blueprints(app)

    return app
