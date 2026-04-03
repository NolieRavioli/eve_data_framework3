"""cache_codegen.py — Generate core/esi/generated/cache_ddl.py from the live ESI routes.json.

This module is called by ``build.py`` (cache schema step) and produces an
auto-generated Python file that contains:

- ``ROUTE_SPECS_DDL``      — DuckDB ``CREATE TABLE esi_route_specs`` statement
- ``RESPONSE_CACHE_DDL``   — DuckDB ``CREATE TABLE esi_cache`` statement
- ``ROUTE_SPECS_SEED_ROWS``— list[dict] with one row per ESI operation for seeding
- ``SPEC_COLUMN_NAMES``    — list[str] of all column names in ``esi_route_specs``

The schema is derived exhaustively from the routes.json field layout so that
adding a new field to the ESI spec only requires re-running ``build.py`` —
no hand-editing of generated files is needed.
"""

from __future__ import annotations

import json
import os
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Columns that are fixed / added by the runtime (not derived from routes.json) ──

# These appear in esi_route_specs but are updated by esi_req.py at runtime.
_LIVE_STATE_COLUMNS: list[tuple[str, str]] = [
    ("rl_remaining",  "INTEGER"),   # X-Ratelimit-Remaining live value
    ("rl_used",       "INTEGER"),   # X-Ratelimit-Used live value
    ("rl_limit_str",  "VARCHAR"),   # raw X-Ratelimit-Limit string e.g. "150/15m"
    ("rl_updated_at", "TIMESTAMP"), # when the live state was last written
    ("generated_at",  "TIMESTAMP"), # build.py run timestamp
]

# Columns that must be excluded from exhaustive field-walking because they are
# either too variable (parameters, response_schema_refs) or are ID-like fields
# handled separately.
_EXCLUDED_TOP_LEVEL: frozenset[str] = frozenset({
    "parameters",           # list of dicts with variable structure
    "request_body_schema_refs",  # list of strings
    "response_schema_refs", # dict[str, list[str]]
    "security",             # raw OAuth2 security list
})


def _safe_col(name: str) -> str:
    """Normalise a dotted/hyphenated field path to a SQL-safe column name."""
    return re.sub(r"[^a-z0-9_]", "_", name.lower())


def _infer_duckdb_type(value: Any) -> str:
    """Return a DuckDB column type for the Python value observed in routes.json."""
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "DOUBLE"
    # Lists and dicts are stored as JSON text.
    if isinstance(value, (list, dict)):
        return "VARCHAR"
    # Everything else (str, None) → VARCHAR
    return "VARCHAR"


def _collect_leaf_columns(
    routes: list[dict],
) -> dict[str, str]:
    """Walk every route dict and collect column_name -> DuckDB_type.

    Nested objects (like ``pagination``, ``rate_limit``) are flattened using
    ``parent_child`` naming.  Lists and dicts that are not simple scalars are
    stored as VARCHAR (JSON text).
    """
    col_types: dict[str, str] = {}

    def _walk(node: Any, prefix: str) -> None:
        if isinstance(node, dict):
            for key, val in node.items():
                child_prefix = f"{prefix}_{_safe_col(key)}" if prefix else _safe_col(key)
                if isinstance(val, dict):
                    # Recurse one level for known simple nested objects
                    _walk(val, child_prefix)
                else:
                    col = child_prefix
                    inferred = _infer_duckdb_type(val)
                    # If we've seen this column before, widen the type if needed.
                    existing = col_types.get(col)
                    if existing is None:
                        col_types[col] = inferred
                    elif existing == "BOOLEAN" and inferred != "BOOLEAN":
                        col_types[col] = inferred
                    elif existing == "INTEGER" and inferred in ("DOUBLE", "VARCHAR"):
                        col_types[col] = inferred
                    elif existing == "DOUBLE" and inferred == "VARCHAR":
                        col_types[col] = inferred
                    # else keep the wider type already recorded

    for route in routes:
        filtered = {k: v for k, v in route.items() if k not in _EXCLUDED_TOP_LEVEL}
        _walk(filtered, "")

    return col_types


def _flatten_route(route: dict, col_names: list[str]) -> dict:
    """Flatten a single route dict into a flat dict matching col_names.

    Nested objects are flattened the same way as _collect_leaf_columns.
    Lists / dicts that are not scalars are JSON-serialised.
    """

    flat: dict[str, Any] = {}

    def _walk(node: Any, prefix: str) -> None:
        if isinstance(node, dict):
            for key, val in node.items():
                child_prefix = f"{prefix}_{_safe_col(key)}" if prefix else _safe_col(key)
                if isinstance(val, dict):
                    _walk(val, child_prefix)
                else:
                    col = child_prefix
                    if isinstance(val, (list, dict)):
                        flat[col] = json.dumps(val, separators=(",", ":"))
                    else:
                        flat[col] = val

    filtered = {k: v for k, v in route.items() if k not in _EXCLUDED_TOP_LEVEL}
    _walk(filtered, "")

    # Store excluded complex fields as JSON text in dedicated columns.
    flat["parameters_json"] = json.dumps(
        route.get("parameters") or [], separators=(",", ":")
    )
    flat["request_body_schema_refs_json"] = json.dumps(
        route.get("request_body_schema_refs") or [], separators=(",", ":")
    )
    flat["response_schema_refs_json"] = json.dumps(
        route.get("response_schema_refs") or {}, separators=(",", ":")
    )
    flat["security_json"] = json.dumps(
        route.get("security") or [], separators=(",", ":")
    )

    # Set live-state columns to NULL in seed rows.
    now_iso = datetime.now(timezone.utc).isoformat()
    for col_name, _ in _LIVE_STATE_COLUMNS:
        if col_name == "generated_at":
            flat[col_name] = now_iso
        else:
            flat.setdefault(col_name, None)

    # Ensure all expected columns are present (fill gaps with None).
    return {col: flat.get(col) for col in col_names}


def _build_route_specs_ddl(col_types: dict[str, str], extra_cols: list[tuple[str, str]]) -> str:
    """Build the CREATE TABLE DDL string for esi_route_specs."""
    lines = [
        "CREATE TABLE IF NOT EXISTS esi_route_specs (",
        "    operation_id VARCHAR PRIMARY KEY,",
    ]
    # All spec-derived columns (but skip operation_id since it's the PK)
    for col, dtype in col_types.items():
        if col == "operation_id":
            continue
        lines.append(f"    {col} {dtype},")
    # Excluded complex fields stored as JSON text
    lines.append("    parameters_json VARCHAR,")
    lines.append("    request_body_schema_refs_json VARCHAR,")
    lines.append("    response_schema_refs_json VARCHAR,")
    lines.append("    security_json VARCHAR,")
    # Runtime live-state columns
    for col_name, dtype in extra_cols:
        lines.append(f"    {col_name} {dtype},")
    # Remove trailing comma from last line
    lines[-1] = lines[-1].rstrip(",")
    lines.append(")")
    return "\n".join(lines)


def _build_cache_ddl() -> str:
    """Build the CREATE TABLE DDL string for esi_cache (fixed schema)."""
    return textwrap.dedent("""\
        CREATE TABLE IF NOT EXISTS esi_cache (
            cache_key                 VARCHAR PRIMARY KEY,
            operation_id              VARCHAR,
            method                    VARCHAR,
            full_url                  VARCHAR,
            params_json               VARCHAR,
            etag                      VARCHAR,
            last_modified             VARCHAR,
            response_body             VARCHAR,
            status_code               INTEGER,
            fetched_at                TIMESTAMP,
            expires_at                TIMESTAMP,
            rl_group                  VARCHAR,
            rl_remaining              INTEGER,
            rl_used                   INTEGER,
            rl_limit_str              VARCHAR,
            retry_after               INTEGER,
            x_pages                   INTEGER,
            x_esi_error_limit_remain  INTEGER,
            x_esi_error_limit_reset   INTEGER
        )""")


def _render_python_file(
    compatibility_date: str,
    route_specs_ddl: str,
    cache_ddl: str,
    seed_rows: list[dict],
    col_names: list[str],
) -> str:
    """Render the full Python source for cache_ddl.py."""
    now_iso = datetime.now(timezone.utc).isoformat()
    # Use repr() — NOT json.dumps() — so the output is valid Python.
    # json.dumps() emits null/true/false which are undefined names in Python.
    seed_repr = repr(seed_rows)
    col_names_repr = repr(col_names)

    return f'''\
# AUTO-GENERATED by utils/build/cache_codegen.py  —  do NOT edit by hand.
# Generated at: {now_iso}
# ESI compatibility date: {compatibility_date}
#
# Re-generate by running:  python build.py  (or  python build.py --cache-only)

"""ESI cache DDL and seed data for core/esi/cache.py."""

ROUTE_SPECS_DDL: str = """
{route_specs_ddl}
"""

RESPONSE_CACHE_DDL: str = """
{cache_ddl}
"""

SPEC_COLUMN_NAMES: list[str] = {col_names_repr}

ROUTE_SPECS_SEED_ROWS: list[dict] = {seed_repr}
'''


def generate_cache_schema(
    compatibility_date: str | None = None,
    force: bool = False,
    output_path: str | Path | None = None,
) -> dict:
    """Generate ``core/esi/generated/cache_ddl.py`` from the live ESI routes.json.

    :param compatibility_date: Pin to a specific ESI compatibility date.
        Defaults to the currently active date in ``_publicData/esi_specs/latest.json``.
    :param force: Regenerate even if the output file already exists.
    :param output_path: Override the output file path (used in tests).
    :returns: Summary dict with ``compatibility_date``, ``route_count``, ``column_count``.
    """
    from core.esi.registry import load_routes, get_registry_status

    if not compatibility_date:
        compatibility_date = get_registry_status().get("compatibility_date") or "unknown"

    if output_path is None:
        output_path = Path("core/esi/generated/cache_ddl.py")
    else:
        output_path = Path(output_path)

    if not force and output_path.exists():
        # Quick check: if the file mentions the same compatibility_date, skip.
        existing = output_path.read_text(encoding="utf-8")
        if f"# ESI compatibility date: {compatibility_date}" in existing:
            routes = load_routes(compatibility_date)
            return {
                "compatibility_date": compatibility_date,
                "route_count": len(routes),
                "column_count": 0,
                "skipped": True,
            }

    routes = load_routes(compatibility_date)

    # Collect all leaf columns from every route object.
    col_types = _collect_leaf_columns(routes)

    # Build the ordered column name list (operation_id first, then sorted remainder).
    col_names: list[str] = ["operation_id"]
    for col in sorted(col_types):
        if col != "operation_id":
            col_names.append(col)
    # Append the excluded JSON columns.
    col_names += [
        "parameters_json",
        "request_body_schema_refs_json",
        "response_schema_refs_json",
        "security_json",
    ]
    # Append live-state columns.
    col_names += [c for c, _ in _LIVE_STATE_COLUMNS]

    # Remove operation_id from col_types since it's hardcoded as PK.
    col_types_for_ddl = {c: t for c, t in col_types.items() if c != "operation_id"}

    # Build DDL.
    route_specs_ddl = _build_route_specs_ddl(col_types_for_ddl, _LIVE_STATE_COLUMNS)
    cache_ddl = _build_cache_ddl()

    # Build seed rows.
    seed_rows = [_flatten_route(r, col_names) for r in routes]

    # Render and write the Python file.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source = _render_python_file(
        compatibility_date=compatibility_date,
        route_specs_ddl=route_specs_ddl,
        cache_ddl=cache_ddl,
        seed_rows=seed_rows,
        col_names=col_names,
    )
    output_path.write_text(source, encoding="utf-8")

    return {
        "compatibility_date": compatibility_date,
        "route_count": len(routes),
        "column_count": len(col_names),
        "skipped": False,
    }
