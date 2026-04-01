# core/web/app.py
"""Start the web application."""

from typing import Optional

from config import RuntimeSettings, get_runtime_settings
from core.web import create_app


def start_webUI(settings: Optional[RuntimeSettings] = None) -> None:
    """Create and run the Flask application with runtime-aware defaults."""
    settings = settings or get_runtime_settings()
    app = create_app(settings)
    server_url = f"http://{settings.web_host}:{settings.web_port}"

    if settings.debug_mode:
        print("[WebUI] Launching with Flask debug mode ON for rapid iteration.")
    print(f"[WebUI] Starting server at {server_url}")

    app.run(
        debug=settings.debug_mode,
        host=settings.web_host,
        port=settings.web_port,
        threaded=True,
        use_reloader=settings.debug_mode,
    )
