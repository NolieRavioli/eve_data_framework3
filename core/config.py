# config.py

import importlib
import logging
import os
import secrets
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


def _load_or_create_session_secret() -> str:
    """Load a persistent session secret from disk, or generate one on first boot."""
    public_data = os.getenv("PUBLIC_DATA_FOLDER", "_publicData")
    secret_path = os.path.join(public_data, "secret")
    sealed_path = secret_path + ".sealed"

    # If the file is still sealed, unseal it first (defensive — main.py
    # normally calls unseal_all() before we get here).
    if os.path.exists(sealed_path) and not os.path.exists(secret_path):
        from core.io.encryption import decrypt_file
        from pathlib import Path
        decrypt_file(Path(sealed_path))

    try:
        with open(secret_path, "r") as f:
            secret = f.read().strip()
            if secret:
                return secret
    except FileNotFoundError:
        pass
    secret = secrets.token_hex(32)
    os.makedirs(public_data, exist_ok=True)
    from pathlib import Path
    from core.io.encryption import encrypt_file
    encrypt_file(Path(secret_path))
    logger.info("[Config] Generated new session secret at %s", secret_path)
    return secret


# ──────── Runtime Settings ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class RuntimeSettings:
    """In-memory view of the runtime knobs for the small-team deployment."""

    debug_mode: bool = False
    auto_install: bool = False
    web_host: str = "127.0.0.1"
    web_port: int = 5000
    session_secret: str = ""
    trace_esi: bool = False
    transport: str = "http"
    github_repo: str = ""
    # Python Console logging (console StreamHandler + per-logger overrides)
    global_log_level: str = "INFO"
    werkzeug_log_level: str = "INFO"
    # Bootstrap auto-update toggles
    bootstrap_sde: bool = True
    bootstrap_esi: bool = True


_runtime_settings: Optional[RuntimeSettings] = None
_runtime_lock = Lock()

# ── Cached config dict — loaded once from disk, never again ────────────────────
_cached_config: Optional[dict] = None


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

        global _cached_config
        cfg = load_config(config_path)
        if not isinstance(cfg, dict):
            cfg = {}
        _cached_config = cfg

        runtime_cfg   = cfg.get("Runtime", {}) or {}
        py_console    = cfg.get("Python Console", {}) or {}
        bootstrap_cfg = cfg.get("Bootstrap", {}) or {}

        debug_mode   = _as_bool(runtime_cfg.get("debug") or os.getenv("EVE_DEBUG"))
        auto_install = _as_bool(runtime_cfg.get("auto_install") or os.getenv("EVE_AUTO_INSTALL"))
        trace_esi    = _as_bool(runtime_cfg.get("trace_esi") or os.getenv("EVE_TRACE_ESI"))
        bootstrap_sde = _as_bool(bootstrap_cfg.get("auto_update_sde", True))
        bootstrap_esi = _as_bool(bootstrap_cfg.get("auto_update_esi", True))

        web_host = runtime_cfg.get("host") or os.getenv("EVE_WEB_HOST", "127.0.0.1")
        web_port = int(runtime_cfg.get("port") or os.getenv("EVE_WEB_PORT", "5000"))

        session_secret = (
            os.getenv("FLASK_SECRET_KEY")
            or runtime_cfg.get("secret_key")
            or _load_or_create_session_secret()
        )

        # ── Logging levels ────────────────────────────────────────────────────
        def _level(value, env_var: str, default: str) -> str:
            return (value or os.getenv(env_var) or default).upper()

        global_log_level      = _level(py_console.get("global_log_level"),      "EVE_LOG_LEVEL",         "INFO")
        werkzeug_log_level    = _level(py_console.get("werkzeug_log_level"),    "EVE_WERKZEUG_LOG_LEVEL", "INFO")

        # Extra per-logger overrides from "Python Console" — any key that isn't
        # a known builtin is treated as "<logger_name>: LEVEL".
        _BUILTIN_KEYS = {"global_log_level", "werkzeug_log_level"}
        extra_loggers: dict[str, str] = {
            k: v.upper()
            for k, v in py_console.items()
            if k not in _BUILTIN_KEYS and isinstance(v, str)
        }

        # ── Root logger + console StreamHandler ───────────────────────────────
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # root accepts everything; handler filters

        # Use the real stdout so the StreamHandler bypasses _ThreadRoutedWriter,
        # preventing double-capture in task logs.
        _real_stdout = getattr(sys.stdout, "_original", sys.stdout)
        _console_handler = logging.StreamHandler(_real_stdout)
        _console_handler.setLevel(getattr(logging, global_log_level, logging.INFO))
        _console_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        if not any(
            isinstance(h, logging.StreamHandler)
            and getattr(h, "stream", None) in (sys.stdout, _real_stdout)
            for h in root_logger.handlers
        ):
            root_logger.addHandler(_console_handler)

        # ── Per-logger level overrides ─────────────────────────────────────────
        # werkzeug is chatty; silence it to its own configured level.
        logging.getLogger("werkzeug").setLevel(
            getattr(logging, werkzeug_log_level, logging.INFO)
        )
        # Any extra loggers declared in the "Python Console" section.
        for logger_name, level_str in extra_loggers.items():
            logging.getLogger(logger_name).setLevel(
                getattr(logging, level_str, logging.DEBUG)
            )

        if debug_mode:
            print(f"[Runtime] Debug mode enabled. Console log level={global_log_level}")
        if trace_esi:
            print("[Runtime] ESI tracing is active. HTTP requests will be printed.")

        transport = runtime_cfg.get("transport", "http")
        github_repo = runtime_cfg.get("github_repo", "")

        _runtime_settings = RuntimeSettings(
            debug_mode=debug_mode,
            auto_install=auto_install,
            web_host=web_host,
            web_port=web_port,
            session_secret=session_secret,
            trace_esi=trace_esi,
            transport=transport,
            github_repo=github_repo,
            global_log_level=global_log_level,
            werkzeug_log_level=werkzeug_log_level,
            bootstrap_sde=bootstrap_sde,
            bootstrap_esi=bootstrap_esi,
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
    """Load config.yaml from disk and inject its Environment Variables into os.environ.

    Called once at startup via ``initialize_runtime_environment()``.  Subsequent
    access should use ``get_config()`` which returns the cached dict.
    """
    global _cached_config
    if _cached_config is not None:
        return _cached_config

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

    _cached_config = cfg
    logger.info(f"Loaded {len(env_vars)} environment variables from {config_path}")
    return cfg


def get_config() -> dict:
    """Return the cached config dict.  Initialises from disk if not yet loaded."""
    if _cached_config is not None:
        return _cached_config
    return load_config(CONFIG_PATH)


def get_sde_config() -> dict:
    """Return the ``SDE`` section of the config."""
    return get_config().get("SDE", {})


def get_auth_config() -> dict:
    """Return the ``Auth`` section of the config."""
    return get_config().get("Auth", {})


def get_market_config() -> dict:
    """Return the ``Market`` section of the config."""
    return get_config().get("Market", {})


def get_structures_config() -> dict:
    """Return the ``Structures`` section of the config."""
    return get_config().get("Structures", {})


# ── DB-unit weights ────────────────────────────────────────────────────────────────────

_DB_UNIT_DEFAULTS: dict[str, float] = {
    "read":      0.001,   # SELECT — per statement, nearly free
    "insert":    1.0,     # baseline — batched executemany through writer
    "upsert":    9.0,     # INSERT OR REPLACE / ON CONFLICT DO UPDATE with PK
    "update":    0.0002,  # UPDATE … WHERE — single statement, nearly free
    "delete":    0.003,   # DELETE … WHERE — single statement, nearly free
    "truncate":  4.69,    # scales with reset-iteration count
    "ddl":       1.8,     # CREATE TABLE IF NOT EXISTS / ALTER TABLE ADD COLUMN
    "bulk_load": 0.04,    # vectorised DataFrame import via db_write_dataframe
}


def get_db_unit_weights() -> dict[str, float]:
    """Return DB-unit operation weights merged from config.yaml and hardcoded defaults.

    Reads the ``DB Units`` section of ``config.yaml`` and overlays any configured
    values onto the hardcoded benchmark defaults.  Always returns all 8 keys
    regardless of which ones appear in the config file, so it works out-of-the-box
    with no ``DB Units`` section present.
    """
    weights = dict(_DB_UNIT_DEFAULTS)
    try:
        section = get_config().get("DB Units") or {}
        for key in _DB_UNIT_DEFAULTS:
            if key in section:
                weights[key] = float(section[key])
    except Exception:
        pass
    return weights

