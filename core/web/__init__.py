# core/web/__init__.py
"""Core web framework — Flask application factory.

This module is the *only* place where Flask is wired up.  It registers the
auth blueprint (SSO is infrastructure, not an application) and then delegates
ALL page blueprints to the application tool registry, which auto-discovers
every package that exposes a ``Tool = <BaseTool subclass instance>`` attribute.
"""

import os
from typing import Optional

from flask import Flask, redirect, request, url_for

from config import RuntimeSettings, get_runtime_settings
from core.web.auth import auth_bp
from core.web.home import home_bp
from core.web.setup import setup_bp


def _credentials_exist() -> bool:
    public_data = os.getenv("PUBLIC_DATA_FOLDER", "_publicData")
    return os.path.exists(os.path.join(public_data, "client_cred"))


def create_app(settings: Optional[RuntimeSettings] = None) -> Flask:
    """Create and configure the Flask application."""
    settings = settings or get_runtime_settings()
    app = Flask(__name__, template_folder="templates")
    app.secret_key = settings.session_secret or os.getenv("FLASK_SECRET_KEY", "nolieravioli")
    app.config["RUNTIME_SETTINGS"] = settings

    # Public home page and setup wizard are core infrastructure.
    app.register_blueprint(home_bp)
    app.register_blueprint(setup_bp)

    # Auth is core infrastructure — always registered directly.
    app.register_blueprint(auth_bp)

    # Every application (dashboard, task_queue, admin_panel, market_browser …)
    # registers itself via the shared ToolRegistry.
    from applications import tool_registry
    tool_registry.register_blueprints(app)

    @app.before_request
    def _check_setup():
        """Redirect to the setup wizard when OAuth credentials are missing."""
        path = request.path
        # Allow static files, the setup wizard itself, and the OAuth callback.
        if (
            path.startswith("/static")
            or path.startswith("/setup")
            or path == "/callback"
        ):
            return None
        if not _credentials_exist():
            return redirect(url_for("setup.index"))
        return None

    return app
