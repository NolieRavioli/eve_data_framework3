# core/web/__init__.py
"""Core web framework — Flask application factory.

This module is the *only* place where Flask is wired up.  It registers the
auth blueprint (SSO is infrastructure, not an application) and then delegates
ALL page blueprints to the application tool registry, which auto-discovers
every package that exposes a ``Tool = <BaseTool subclass instance>`` attribute.
"""

import logging
import os
from typing import Optional

from flask import Flask, Response, redirect, request, url_for

from core.config import RuntimeSettings, get_runtime_settings

from core.auth.sso import auth_bp
from core.web.home import home_bp
from core.web.setup import setup_bp

logger = logging.getLogger(__name__)


def _credentials_exist() -> bool:
    public_data = os.getenv("PUBLIC_DATA_FOLDER", "_publicData")
    return os.path.exists(os.path.join(public_data, "client_cred"))


def create_app(settings: Optional[RuntimeSettings] = None) -> Flask:
    """Create and configure the Flask application."""
    settings = settings or get_runtime_settings()
    app = Flask(__name__, template_folder="templates")
    app.secret_key = settings.session_secret or os.getenv("FLASK_SECRET_KEY", "nolieravioli")
    app.config["RUNTIME_SETTINGS"] = settings

    # Install the centralized bus handler before any blueprint imports
    # so that blueprint-level log calls are captured from the start.
    from core.bus import install_bus_handler as _install_bus_handler
    _install_bus_handler()

    # Start the periodic db/stats publisher (publishes to the bus every 5s).
    from core.db.stats import start_db_stats_publisher
    start_db_stats_publisher()

    # Start the periodic process-metrics publisher (publishes system/process every 10s).
    from core.bus.process_pub import start_process_publisher
    start_process_publisher()

    # Attach the flask-sock WebSocket extension and register the bus endpoint.
    # flask-sock is an optional dependency — the app starts normally without it,
    # but the /bus endpoint will be unavailable until it is installed.
    try:
        from flask_sock import Sock
        from core.bus.websocket import bus_ws
        sock = Sock(app)
        sock.route("/bus")(bus_ws)
    except ImportError:
        logger.warning(
            "[web] flask-sock not installed — /bus WebSocket disabled. "
            "Run: pip install flask-sock"
        )
        sock = None

    # Public home page and setup wizard are core infrastructure.
    app.register_blueprint(home_bp)
    app.register_blueprint(setup_bp)

    # Auth is core infrastructure — always registered directly.
    app.register_blueprint(auth_bp)

    # Every application (dashboard, task_queue, admin_panel, market_browser …)
    # registers itself via the shared ToolRegistry.
    from applications import tool_registry
    tool_registry.register_blueprints(app)

    # Bind all register_websock() declarations made by applications during
    # blueprint registration above.  Must run AFTER register_blueprints().
    if sock is not None:
        from core.bus.websocket import attach_all_websocks
        attach_all_websocks(sock)

    # Start the background scheduler engine and register all catalog jobs.
    # Import is deferred so collectors are importable at this point.
    from core.tasks.engine import get_engine
    from core.tasks.jobs import register_all_jobs
    _scheduler = get_engine()
    register_all_jobs(_scheduler)
    _scheduler.start()

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

    @app.errorhandler(404)
    def _not_found(e):
        notfound_msg = """Hello,

This resource is in a restricted administrative area and is not available for public access.

Unauthorized access attempts are logged and monitored.
Most offenses are reported.

If you believe you should have access,
please contact the administrator.

.--.--.--.--.--.--.--.  .--.--.--.--.--.--.--.
|                    |        |     |     |  |
:  :--:  :--:--:--:--:  :--:  :  :  :  :  :  :
|     |     |              |     |     |  |  |
:--:  :--:  :  :--:--:--:  :--:--:--:  :  :  :
|     |     |     |     |           |  |  |  |
:--:--:  :--:  :--:  :  :--:--:  :  :  :  :  :
|        |     |     |           |  |  |     |
:  :--:--:  :--:  :  :--:  :--:--:  :  :--:--:
|           |     |     |  |     |  |  |     |
:--:--:--:--:  :--:--:  :--:  :--:  :  :  :  :
|           |  |     |     |     |  |     |  |
:  :  :  :--:  :  :  :--:  :--:  :  :--:--:  :
|  |  |     |  |  |     |        |     |  |  |
:  :  :--:  :  :  :--:  :--:--:--:--:  :  :  :
|  |     |           |  |           |  |     |
:--:--:  :--:--:--:  :--:  :--:--:  :  :--:--:
|     |  |     |           |     |  |  |     |
:  :  :--:  :  :  :--:--:--:  :  :  :  :  :  :
|  |  |     |  |           |  |  |  |     |  |
:  :  :  :--:--:  :--:--:  :  :  :--:--:--:  :
|  |  |  |     |     |     |  |        |     |
:  :  :  :  :  :--:  :  :--:--:  :--:  :  :--:
|  |     |  |  |     |        |     |  |     |
:  :--:--:  :  :--:--:--:--:  :  :  :--:--:  :
|        |  |     |     |     |  |  |     |  |
:  :--:  :  :--:  :  :  :  :--:--:  :  :  :  :
|  |     |  |     |  |     |     |  |  |  |  |
:  :  :--:  :  :--:  :--:--:  :  :  :  :--:  :
|  |     |  |  |              |     |     |  |
:  :  :--:  :--:  :--:--:--:--:  :--:  :  :  :
|  |     |        |           |     |  |     |
:  :--:  :--:--:--:  :--:--:  :--:  :--:--:--:
|  |     |           |        |  |           |
:  :  :--:--:--:--:  :  :--:--:  :  :--:--:  :
|  |     |     |     |  |     |     |     |  |
:  :--:  :  :  :  :--:  :  :--:  :--:  :  :--:
|  |     |  |  |     |     |     |     |     |
:  :--:--:  :  :  :  :--:--:  :--:  :--:--:  :
|  |        |  |  |  |     |  |        |     |
:  :  :  :--:  :  :  :  :  :  :--:--:  :  :--:
|     |     |  |  |  |  |  |           |  |  |
:  :--:--:  :  :  :  :  :--:  :--:--:--:  :  :
|     |     |     |  |  |     |        |  |  |
:--:--:  :--:--:  :--:  :  :  :  :--:  :  :  :
|        |     |  |     |  |  |     |  |  |  |
:  :--:--:  :--:  :  :--:  :  :  :  :--:  :  :
|        |     |  |        |  |  |     |  |  |
:--:--:  :  :  :  :--:--:--:--:  :  :  :  :  :
|     |  |  |  |     |     |     |  |  |     |
:  :  :  :--:  :  :--:  :  :  :  :--:  :  :--:
|  |           |        |     |  |           |
:--:--:--:--:--:--:--:--:--:--:--:  :--:--:--:"""
        return Response(notfound_msg, status=404, mimetype="text/plain")

    return app
