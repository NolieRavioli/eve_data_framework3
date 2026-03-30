# config.py

import importlib
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from threading import Lock
from typing import Iterable, Optional

import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = "config.yaml"
PRIVATE_DATA_FOLDER = os.getenv("EVE_PRIVATE_DATABASE_FOLDER", "_privateData/")


REQUIRED_MODULES = (
    "sqlalchemy",
    "ruamel.yaml",
    "flask",
    "cryptography",
    "requests_oauthlib",
    "jwt",
    "yaml",
    "duckdb",
)

DEFAULT_SECRET = "nolieravioli"


# ──────── Runtime Settings ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class RuntimeSettings:
    """In-memory view of the runtime knobs for the small-team deployment."""

    debug_mode: bool = False
    auto_install: bool = False
    web_host: str = "127.0.0.1"
    web_port: int = 5000
    session_secret: str = DEFAULT_SECRET
    log_level: str = "INFO"
    trace_esi: bool = False


_runtime_settings: Optional[RuntimeSettings] = None
_runtime_lock = Lock()


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def initialize_runtime_environment(config_path: str = CONFIG_PATH) -> RuntimeSettings:
    """Load config, set up logging, and surface runtime toggles once."""

    global _runtime_settings
    with _runtime_lock:
        if _runtime_settings is not None:
            return _runtime_settings

        cfg = load_config(config_path)
        runtime_cfg = cfg.get("Runtime", {}) if isinstance(cfg, dict) else {}

        debug_mode = _as_bool(runtime_cfg.get("debug") or os.getenv("EVE_DEBUG"))
        auto_install = _as_bool(runtime_cfg.get("auto_install") or os.getenv("EVE_AUTO_INSTALL"))
        trace_esi = _as_bool(runtime_cfg.get("trace_esi") or os.getenv("EVE_TRACE_ESI"))

        web_host = runtime_cfg.get("host") or os.getenv("EVE_WEB_HOST", "127.0.0.1")
        web_port = int(runtime_cfg.get("port") or os.getenv("EVE_WEB_PORT", "5000"))

        session_secret = (
            os.getenv("FLASK_SECRET_KEY")
            or runtime_cfg.get("secret_key")
            or DEFAULT_SECRET
        )

        log_level = (runtime_cfg.get("log_level") or os.getenv("EVE_LOG_LEVEL") or "INFO").upper()

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        # Use the real stdout so the StreamHandler bypasses _ThreadRoutedWriter.
        # This prevents log records from being double-captured in the task log
        # (once by _TaskLogHandler and again via StreamHandler->_ThreadRoutedWriter).
        _real_stdout = getattr(sys.stdout, "_original", sys.stdout)
        _console_handler = logging.StreamHandler(_real_stdout)
        _console_handler.setLevel(logging.DEBUG)
        _console_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        if not any(
            isinstance(h, logging.StreamHandler)
            and getattr(h, "stream", None) in (sys.stdout, _real_stdout)
            for h in root_logger.handlers
        ):
            root_logger.addHandler(_console_handler)

        if debug_mode:
            print(f"[Runtime] Debug mode enabled. Log level={log_level}")
        if trace_esi:
            print("[Runtime] ESI tracing is active. HTTP requests will be printed.")

        _runtime_settings = RuntimeSettings(
            debug_mode=debug_mode,
            auto_install=auto_install,
            web_host=web_host,
            web_port=web_port,
            session_secret=session_secret,
            log_level=log_level,
            trace_esi=trace_esi,
        )

        return _runtime_settings


def get_runtime_settings() -> RuntimeSettings:
    """Return cached runtime settings, initialising them if needed."""

    if _runtime_settings is None:
        return initialize_runtime_environment(CONFIG_PATH)
    return _runtime_settings


def ensure_dependencies(settings: Optional[RuntimeSettings] = None,
                        required_modules: Iterable[str] = REQUIRED_MODULES) -> None:
    """Optionally auto-install missing modules to keep small deployments running."""

    settings = settings or get_runtime_settings()
    missing = []
    for module_name in required_modules:
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(module_name)

    if not missing:
        return

    message = f"Missing dependencies detected: {', '.join(missing)}"
    if not settings.auto_install:
        raise ImportError(message)

    print(f"[Runtime] {message}. Installing from requirements.txt...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    print("[Runtime] Dependency installation complete.")


# ──────── Config Loader ─────────────────────────────────────────────────────────


def load_config(config_path: str = CONFIG_PATH) -> dict:
    """
    Loads Environment Variables from a config.yaml into os.environ.
    Returns the full config dict.
    """

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    env_vars = cfg.get("Environment Variables", {})
    if not isinstance(env_vars, dict):
        raise ValueError("Expected 'Environment Variables' to be a dictionary in config.yaml")

    for key, value in env_vars.items():
        if key not in os.environ:
            if isinstance(value, list):
                os.environ[key] = ",".join(str(v) for v in value)
            else:
                os.environ[key] = str(value)

    logger.info(f"Loaded {len(env_vars)} environment variables from {config_path}")
    return cfg

