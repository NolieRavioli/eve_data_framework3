"""config_codegen.py — Generate example.config.yaml from live codebase introspection.

Discovers:
  • SDE keys     — from core.sde.cache._SECTION_DEFAULTS
  • Python loggers — by walking .py files for logging.getLogger(__name__)

Run via:
    python build.py --example-config
    python build.py              (generated at the end of a full build)
"""

import ast
import os
from pathlib import Path

# ── SDE key descriptions (kept in sync with _SECTION_DEFAULTS) ──────────────

_SDE_DESCRIPTIONS: dict[str, str] = {
    "types":          "type ID <-> name maps          (~26 MB, ~4s)",
    "groups":         "item group hierarchy            (~0.3 MB, fast)",
    "categories":     "item categories                 (~0.1 MB, fast)",
    "market_groups":  "market group tree               (~0.3 MB, fast)",
    "universe":       "solar-system -> region map      (8,400+ files, ~15s)",
    "blueprints":     "manufacturing blueprints        (~4 MB, ~8s)",
    "type_materials": "reprocessing materials          (~2 MB, ~3s)",
    "type_dogma":     "item dogma attributes           (~26 MB, ~60s+)",
}

# ── Dirs + files to skip during logger discovery ────────────────────────────

_SKIP_DIRS = {
    "venv", ".venv", "__pycache__", "_sde", ".git",
    "node_modules", ".tox", "dist", "build",
}

_SKIP_FILE_PREFIXES = {"utils/build/"}


def _discover_loggers(root: Path) -> list[str]:
    """Walk .py files and return sorted unique dotted module names that call
    logging.getLogger(__name__).  Converts file paths to module names."""

    found: set[str] = set()

    for py_file in sorted(root.rglob("*.py")):
        # Skip unwanted directories anywhere in the path
        parts = py_file.parts
        if any(part in _SKIP_DIRS for part in parts):
            continue

        rel = py_file.relative_to(root)
        rel_str = str(rel).replace("\\", "/")

        # Skip build utilities themselves — they're not runtime loggers
        if any(rel_str.startswith(p) for p in _SKIP_FILE_PREFIXES):
            continue

        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Fast pre-check before attempting AST parse
        if "getLogger" not in source:
            continue

        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            # Match: logging.getLogger(__name__)
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_get_logger = (
                isinstance(func, ast.Attribute)
                and func.attr == "getLogger"
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "__name__"
            )
            if not is_get_logger:
                continue

            # Convert path to dotted module name
            module_path = rel.with_suffix("")
            dotted = str(module_path).replace("\\", ".").replace("/", ".")
            # Strip trailing .__init__
            if dotted.endswith(".__init__"):
                dotted = dotted[: -len(".__init__")]
            found.add(dotted)
            break  # one match per file is enough

    return sorted(found)


def _get_sde_defaults() -> dict[str, bool]:
    """Read _SECTION_DEFAULTS from core.io.sde without side-effects."""
    from core.io.sde import _SECTION_DEFAULTS  # type: ignore
    return dict(_SECTION_DEFAULTS)


def _sde_section(defaults: dict[str, bool]) -> list[str]:
    lines = [
        "# SDE section toggles — set false to skip loading a dataset at startup.",
        "# Disabled datasets lazy-load on first use (or return defaults if too expensive).",
        "SDE:",
        '  database_file: "_publicData/public.duckdb"',
    ]
    for key, default in defaults.items():
        desc = _SDE_DESCRIPTIONS.get(key, "")
        val = "true" if default else "false"
        pad = max(0, 22 - len(f"load_{key}"))
        lines.append(f"  load_{key}: {val}" + " " * pad + (f"# {desc}" if desc else ""))
    return lines


def _python_console_section(loggers: list[str]) -> list[str]:
    lines = [
        "Python Console:",
        "  global_log_level: INFO          # log level for the terminal / console output",
        "  werkzeug_log_level: INFO        # log level for the Flask/Werkzeug request logger",
        "  # ── Per-logger overrides ─────────────────────────────────────────────────",
        "  # Uncomment and adjust any logger below to tune its verbosity independently.",
        "  # Valid levels: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    ]
    # Add well-known third-party loggers first
    third_party = ["werkzeug", "flask", "sqlalchemy", "duckdb", "urllib3", "requests"]
    for name in third_party:
        lines.append(f"  # {name}: INFO")
    if third_party:
        lines.append("  #")
    for name in loggers:
        lines.append(f"  # {name}: INFO")
    return lines


_TEMPLATE_HEADER = """\
# example.config.yaml — annotated template for EVE Data Framework
# Generated by: python build.py --example-config
# Copy this file to config.yaml and adjust as needed.
# config.yaml is gitignored and must NEVER be committed.

Runtime:
  host: "127.0.0.1"                # bind address for the Flask web server
                                   # use "0.0.0.0" to listen on all network interfaces
  port: 5000                       # TCP port for the Flask web server
  # debug: false                   # enable Flask debug mode (extra logging, auto-reload)
  # trace_esi: false               # print every ESI HTTP request to the console
  # auto_install: false            # pip-install missing requirements automatically
  # secret_key: "change-me"        # Flask session secret (use a long random string in prod)
  # transport: "http"              # "http" or "https" — set to "https" when behind a TLS-terminating proxy
  # github_repo: ""                # GitHub repository URL for system updates (default: NolieRavioli/eve_data_framework3)

"""

_TEMPLATE_BOOTSTRAP = """\
# Bootstrap controls which subsystems auto-update when the server starts.
# Set either flag to false to skip auto-update on boot (useful for production
# deployments that pin generated code to git and update manually).
# Changes take effect on the next server restart.
Bootstrap:
  auto_update_sde: true   # download + rebuild SDE warehouse if stale
  auto_update_esi: true   # fetch latest ESI spec + regenerate codegen if stale

"""

_TEMPLATE_FOOTER = """
Environment Variables:
  LANGUAGE: "en"
  SUPPORTED_LANGUAGES: "en"
  PUBLIC_DATA_FOLDER: "_publicData"
  EVE_PRIVATE_DATABASE_FOLDER: "_privateData/"
  SDE_PATH: "_sde/"

# Role-based access control.
# default_roles are granted to every new user on their first login
# (site owner is exempt — they have full access already).
# Role names must match the required_role field in each application's ToolManifest.
Auth:
  default_roles:
    - dashboard
    - database
    - sde
    - tasks

"""

_TEMPLATE_STRUCTURES = """\
Structures:
  forbidden_cooldown_days: 21       # days to skip transiently-inaccessible structures (404/network)
  unauthorized_cooldown_days: 7     # days to skip 403-inaccessible structures during enrichment
  authorized_cooldown_seconds: 3600 # seconds to skip structures that succeed

Market:
  unauthorized_cooldown_days: 7         # days to skip structures that return 403 on market endpoint
  forbidden_cooldown_days: 21           # days to skip structures that fail for other reasons
  authorized_cooldown_seconds: 3600     # seconds to skip structures that succeed on market endpoint
  max_retries: 3                        # per-page fetch retry limit before skipping a structure
  rate_limit_sleep_seconds: 10          # sleep duration when ESI returns 420 (error rate limit)
"""


def generate_example_config(output_path: str = "example.config.yaml", root: Path | None = None) -> str:
    """Generate and write example.config.yaml. Returns the path written."""

    if root is None:
        root = Path(".")

    sde_defaults = _get_sde_defaults()
    loggers = _discover_loggers(root)

    parts: list[str] = []
    parts.append(_TEMPLATE_HEADER)
    parts.append(_TEMPLATE_BOOTSTRAP)
    parts.append("\n".join(_python_console_section(loggers)))
    parts.append("\n\n")
    parts.append("\n".join(_sde_section(sde_defaults)))
    parts.append("\n")
    parts.append(_TEMPLATE_FOOTER)
    parts.append(_TEMPLATE_STRUCTURES)

    content = "".join(parts)
    Path(output_path).write_text(content, encoding="utf-8")
    return output_path
