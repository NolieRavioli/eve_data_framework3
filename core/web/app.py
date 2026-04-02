# core/web/app.py
"""Start the web application."""

import socket
import sys
from typing import Optional

from core.config import RuntimeSettings, get_runtime_settings
from core.web import create_app


def start_webUI(settings: Optional[RuntimeSettings] = None) -> None:
    """Create and run the Flask application with runtime-aware defaults."""
    settings = settings or get_runtime_settings()

    # Validate the bind address before handing it to Flask.  A bad value (e.g.
    # "*.*.*.*" instead of "0.0.0.0") causes a cryptic getaddrinfo failure inside
    # a C extension thread which can core-dump rather than print a useful message.
    try:
        socket.getaddrinfo(settings.web_host, settings.web_port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        print(
            f"\n[WebUI] ERROR: Cannot resolve bind address '{settings.web_host}' — {exc}\n"
            f"  Fix the 'host' key in config.yaml:\n"
            f"    host: '0.0.0.0'     # all network interfaces\n"
            f"    host: '127.0.0.1'   # localhost only\n",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

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
