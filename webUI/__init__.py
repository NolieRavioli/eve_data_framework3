# webUI/__init__.py

import os
from typing import Optional

from flask import Flask

from util.utils import RuntimeSettings, get_runtime_settings
from webUI.dashboard import dashboard_bp
from webUI.sso import auth_bp
from webUI.admin import admin_bp
from webUI.tasks import tasks_bp


def create_app(settings: Optional[RuntimeSettings] = None):
    """Factory that wires blueprints and exposes runtime settings to Flask."""

    settings = settings or get_runtime_settings()
    app = Flask(__name__)
    secret = settings.session_secret or os.getenv("FLASK_SECRET_KEY")
    app.secret_key = secret or "nolieravioli"

    # Expose toggles for downstream handlers (dashboard, SSO, etc.).
    app.config["RUNTIME_SETTINGS"] = settings

    # Register core blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(tasks_bp)

    # Register tool blueprints (port/adapter framework)
    from tools import tool_registry
    tool_registry.register_blueprints(app)

    return app
