"""
util/esi_codegen.py
────────────────────
Code generator that reads the active ESI spec snapshot and emits the
``esi/generated/`` package.

Generated files
───────────────
  esi/generated/__init__.py          — package marker + version check
  esi/generated/manifest.py          — authoritative operation catalog dict
  esi/generated/schemas.py           — TypedDict stubs + aliases from schemas.json
  esi/generated/client.py            — dynamic execute_operation() + batch helpers

Entry points
────────────
  generate(compatibility_date=None, output_dir=None, force=False)
      Main entry point.  Reads routes.json + schemas.json for the given (or
      latest) compatibility date and writes the generated package.

  check_generated_is_current()
      Called at app startup.  Raises RuntimeError if the generated package's
      embedded compatibility date / operation count does not match latest.json.
      Fail-closed behaviour.

CLI
───
  python -m util.esi_codegen [--date YYYY-MM-DD] [--output DIR] [--force]
"""

from __future__ import annotations

import argparse
import json
import keyword
import re
import sys
import textwrap
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_ident(name: str) -> str:
    """Convert a string into a valid Python identifier."""
    ident = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if ident and ident[0].isdigit():
        ident = "_" + ident
    if keyword.iskeyword(ident):
        ident = ident + "_"
    return ident


def _repr(value: Any) -> str:
    """repr() with consistent True/False/None capitalisation."""
    return repr(value)


def _wrap_docstring(text: str, indent: int = 4) -> str:
    """Return a triple-quoted docstring block."""
    if not text:
        return ""
    prefix = " " * indent
    body = textwrap.indent(textwrap.fill(text.strip(), width=96), prefix)
    return f'{prefix}"""\n{body}\n{prefix}"""\n'


# ─────────────────────────────────────────────────────────────────────────────
# Spec loader
# ─────────────────────────────────────────────────────────────────────────────

def _spec_root() -> Path:
    return Path("_publicData") / "esi_specs"


def _latest_info() -> dict:
    latest_path = _spec_root() / "latest.json"
    if not latest_path.exists():
        raise FileNotFoundError(
            "No ESI spec snapshot found at _publicData/esi_specs/latest.json. "
            "Run util.esi_spec_registry.refresh_esi_spec_registry() first."
        )
    return json.loads(latest_path.read_text(encoding="utf-8"))


def _load_routes(compatibility_date: str) -> list[dict]:
    path = _spec_root() / compatibility_date / "routes.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_schemas(compatibility_date: str) -> dict[str, dict]:
    path = _spec_root() / compatibility_date / "schemas.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
# manifest.py generator
# ─────────────────────────────────────────────────────────────────────────────

def _gen_manifest(routes: list[dict], compatibility_date: str) -> str:
    lines: list[str] = [
        '"""',
        "esi/generated/manifest.py",
        "─────────────────────────",
        "AUTO-GENERATED — do not edit by hand.",
        f"Source: ESI compatibility date {compatibility_date}",
        f"Operations: {len(routes)}",
        '"""',
        "# ruff: noqa",
        "from __future__ import annotations",
        "",
        "COMPATIBILITY_DATE: str = " + repr(compatibility_date),
        f"OPERATION_COUNT: int = {len(routes)}",
        "",
        "# All unique scopes required by any operation in this spec.",
        "ALL_SCOPES: list[str] = " + repr(sorted({s for r in routes for s in r.get("scopes", [])})),
        "",
        "# ── Operation manifest ────────────────────────────────────────────────────────",
        "# Each entry is a dict with the full normalised route metadata.",
        "# Keys mirror routes.json exactly so callers can use either source.",
        "OPERATIONS: dict[str, dict] = {",
    ]

    for route in routes:
        op_id = route.get("operation_id") or ""
        lines.append(f"    {repr(op_id)}: {{")
        for key in (
            "route_key", "method", "path", "operation_id", "summary",
            "description", "tags", "compatibility_date", "cache_age",
            "cache_mode", "pagination", "required_roles", "rate_limit",
            "scopes", "requires_auth", "queue_channel",
            "request_body_schema_refs", "response_schema_refs",
        ):
            if key in route:
                lines.append(f"        {repr(key)}: {_repr(route[key])},")
        # Include path parameters condensed
        params = [
            {"name": p.get("name"), "in": p.get("in"), "required": p.get("required", False)}
            for p in route.get("parameters", [])
            if p.get("name")
        ]
        lines.append(f"        {repr('parameters')}: {_repr(params)},")
        lines.append("    },")

    lines += [
        "}",
        "",
        "# ── Convenience lookups ──────────────────────────────────────────────────────",
        "OPERATIONS_BY_TAG: dict[str, list[str]] = {}",
        "for _op_id, _op in OPERATIONS.items():",
        "    for _tag in (_op.get('tags') or []):",
        "        OPERATIONS_BY_TAG.setdefault(_tag, []).append(_op_id)",
        "",
        "OPERATIONS_BY_METHOD: dict[str, list[str]] = {}",
        "for _op_id, _op in OPERATIONS.items():",
        "    _m = _op.get('method', '')",
        "    OPERATIONS_BY_METHOD.setdefault(_m, []).append(_op_id)",
        "",
        "AUTH_OPERATIONS: list[str] = [op_id for op_id, op in OPERATIONS.items() if op.get('requires_auth')]",
        "PUBLIC_OPERATIONS: list[str] = [op_id for op_id, op in OPERATIONS.items() if not op.get('requires_auth')]",
        "",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# schemas.py generator
# ─────────────────────────────────────────────────────────────────────────────

_JSON_TO_PYTHON = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "list",
    "object": "dict",
}


def _schema_to_python_type(schema: dict | None) -> str:
    if not schema:
        return "Any"
    t = schema.get("type")
    fmt = schema.get("format", "")
    if t == "array":
        items = schema.get("items", {})
        item_type = _schema_to_python_type(items)
        return f"list[{item_type}]"
    if t == "integer" and "int64" in fmt:
        return "int"
    return _JSON_TO_PYTHON.get(t or "", "Any")


def _gen_schemas(schemas: dict[str, dict], compatibility_date: str) -> str:
    lines: list[str] = [
        '"""',
        "esi/generated/schemas.py",
        "─────────────────────────",
        "AUTO-GENERATED — do not edit by hand.",
        f"Source: ESI compatibility date {compatibility_date}",
        f"Schemas: {len(schemas)}",
        "",
        "TypedDict stubs and type aliases for ESI response schemas.",
        "These are informational; the runtime uses plain dicts.",
        '"""',
        "# ruff: noqa",
        "from __future__ import annotations",
        "from typing import Any, TypedDict",
        "",
        f"SCHEMA_COUNT: int = {len(schemas)}",
        "",
    ]

    for name, schema in sorted(schemas.items()):
        safe_name = _safe_ident(name)
        schema_type = schema.get("type")
        description = schema.get("description", "")

        if schema_type == "object" and schema.get("properties"):
            # Emit as TypedDict
            props = schema["properties"]
            required_set = set(schema.get("required") or [])
            lines.append(f"class {safe_name}(TypedDict, total=False):")
            if description:
                lines.append(f'    """{description[:120]}"""')
            for prop_name, prop_schema in props.items():
                py_type = _schema_to_python_type(prop_schema)
                safe_prop = _safe_ident(prop_name)
                lines.append(f"    {safe_prop}: {py_type}  # required={prop_name in required_set}")
            lines.append("")
        elif schema_type == "array":
            item_type = _schema_to_python_type(schema.get("items", {}))
            lines.append(f"# {name}: array of {item_type}")
            lines.append(f"{safe_name} = list[{item_type}]")
            lines.append("")
        else:
            py_type = _schema_to_python_type(schema)
            lines.append(f"# {name}: {schema_type or 'any'}")
            lines.append(f"{safe_name} = {py_type}")
            lines.append("")

    lines.append("# ── Schema name constant map ─────────────────────────────────────────────────")
    lines.append("SCHEMA_NAMES: list[str] = " + repr(sorted(schemas.keys())))
    lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# client.py generator
# ─────────────────────────────────────────────────────────────────────────────

_CLIENT_TEMPLATE = '''"""
esi/generated/client.py
────────────────────────
AUTO-GENERATED — do not edit by hand.
Source: ESI compatibility date {compatibility_date}

Provides:
  execute_operation(operation_id, *, path_params, query_params, token,
                    json_body, headers, pages) -> dict | list[dict]
    Generic executor for any operation in the manifest.  Routes all HTTP
    through util.esi_rate_limiter.esi_request — never calls requests directly.

  execute_tag(tag, owner_id, ...) -> list[dict]
    Convenience batch runner for all GET operations in a tag.

  validate_write(operation_id, path_params, json_body) -> list[str]
    Lightweight pre-dispatch validation for write routes.
    Returns a list of error strings; empty means valid.
"""
# ruff: noqa
from __future__ import annotations

import re
from typing import Any

from esi.generated.manifest import OPERATIONS, COMPATIBILITY_DATE, ALL_SCOPES


RESPONSE_CONTRACT_KEYS = ("route", "url", "status_code", "headers", "body", "queue_channel")

ESI_BASE_URL = "https://esi.evetech.net"


class OperationNotFound(KeyError):
    """Raised when an operation_id is not in the manifest."""


class MissingPathParam(ValueError):
    """Raised when a required path parameter is absent."""


class AuthRequired(PermissionError):
    """Raised when a token is required but not supplied."""


class ValidationError(ValueError):
    """Raised by validate_write when the request body is structurally invalid."""


# ── Path building ─────────────────────────────────────────────────────────────

def build_path(operation_id: str, path_params: dict[str, Any] | None = None) -> str:
    op = OPERATIONS.get(operation_id)
    if op is None:
        raise OperationNotFound(operation_id)
    template: str = op["path"]
    values = path_params or {{}}
    missing: list[str] = []

    def _replace(m: re.Match[str]) -> str:
        k = m.group(1)
        if k not in values:
            missing.append(k)
            return m.group(0)
        return str(values[k])

    resolved = re.sub(r"\\{{([^}}]+)\\}}", _replace, template)
    if missing:
        raise MissingPathParam(
            f"Operation {{operation_id!r}} is missing path params: {{missing}}"
        )
    return resolved


# ── Validation ────────────────────────────────────────────────────────────────

def validate_write(
    operation_id: str,
    path_params: dict[str, Any] | None = None,
    json_body: Any = None,
) -> list[str]:
    """
    Validate a write (POST/PUT/DELETE/PATCH) operation before dispatch.
    Returns a list of error strings; empty list means the request looks valid.
    """
    op = OPERATIONS.get(operation_id)
    if op is None:
        return [f"Unknown operation: {{operation_id!r}}"]

    errors: list[str] = []
    method = op.get("method", "GET")
    if method == "GET":
        errors.append(f"{{operation_id!r}} is a GET operation — use execute_operation instead.")

    # Check all required path params are present
    for p in op.get("parameters", []):
        if p.get("in") == "path" and p.get("required") and p.get("name"):
            name = p["name"]
            if not path_params or name not in path_params:
                errors.append(f"Missing required path param: {{name!r}}")

    # Check request body schema refs
    body_refs = op.get("request_body_schema_refs") or []
    if body_refs and json_body is None:
        errors.append(f"Operation {{operation_id!r}} requires a request body.")

    return errors


# ── Core executor ─────────────────────────────────────────────────────────────

def execute_operation(
    operation_id: str,
    *,
    path_params: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    json_body: Any = None,
    token: str | None = None,
    headers: dict[str, str] | None = None,
    page: int | None = None,
) -> dict:
    """
    Execute a single ESI operation and return the standardised response dict.

    Response dict keys: route, url, status_code, headers, body, queue_channel.
    All HTTP goes through util.esi_rate_limiter.esi_request.
    """
    from util.esi_rate_limiter import esi_request

    op = OPERATIONS.get(operation_id)
    if op is None:
        raise OperationNotFound(operation_id)

    if op.get("requires_auth") and not token:
        raise AuthRequired(
            f"{{operation_id!r}} requires authentication but no token was provided."
        )

    resolved_path = build_path(operation_id, path_params)

    req_headers: dict[str, str] = {{"Accept": "application/json", **(headers or {{}})}}
    req_headers.setdefault("X-Compatibility-Date", COMPATIBILITY_DATE)
    req_headers.setdefault("X-Tenant", "tranquility")
    if token:
        req_headers["Authorization"] = f"Bearer {{token}}"

    params = dict(query_params or {{}})
    if page is not None and op.get("pagination", {{}}).get("has_page_param"):
        params["page"] = page

    response = esi_request(
        op["method"],
        f"{{ESI_BASE_URL}}{{resolved_path}}",
        params=params or None,
        json=json_body,
        headers=req_headers,
    )

    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            body = response.json() if response.content else None
        except ValueError:
            body = response.text
    else:
        body = response.text

    return {{
        "route": op,
        "url": response.url,
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body": body,
        "queue_channel": op.get("queue_channel", "public"),
    }}


def fetch_all_pages(
    operation_id: str,
    *,
    path_params: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    token: str | None = None,
    headers: dict[str, str] | None = None,
) -> list:
    """
    Fetch all pages for a paginated operation and return the concatenated list.
    Returns [] on 403/404.  Raises on 401.
    """
    op = OPERATIONS.get(operation_id)
    if op is None:
        raise OperationNotFound(operation_id)

    has_pages = op.get("pagination", {{}}).get("has_page_param", False)

    r1 = execute_operation(
        operation_id,
        path_params=path_params,
        query_params=query_params,
        token=token,
        headers=headers,
        page=1 if has_pages else None,
    )
    status = r1["status_code"]
    if status == 401:
        raise AuthRequired(f"401 for {{operation_id!r}}")
    if status in (403, 404):
        return []
    if not (200 <= status < 300):
        return []

    body = r1["body"]
    if not isinstance(body, list):
        return [body] if body is not None else []

    if not has_pages:
        return body

    total_pages = int(r1["headers"].get("X-Pages", 1))
    results: list = list(body)
    for page in range(2, total_pages + 1):
        rn = execute_operation(
            operation_id,
            path_params=path_params,
            query_params=query_params,
            token=token,
            headers=headers,
            page=page,
        )
        if not (200 <= rn["status_code"] < 300):
            break
        if isinstance(rn["body"], list):
            results.extend(rn["body"])

    return results


def execute_tag_batch(
    tag: str,
    *,
    token: str | None = None,
    path_params: dict[str, Any] | None = None,
    method_filter: str = "GET",
) -> list[dict]:
    """
    Execute all operations with the given tag and optional method filter.
    Each result is a standardised response dict with an added 'operation_id' key.
    Skips operations that require auth when no token is supplied.
    """
    from esi.generated.manifest import OPERATIONS_BY_TAG
    results: list[dict] = []
    for op_id in OPERATIONS_BY_TAG.get(tag, []):
        op = OPERATIONS[op_id]
        if method_filter and op.get("method") != method_filter:
            continue
        if op.get("requires_auth") and not token:
            continue
        try:
            r = fetch_all_pages(op_id, token=token, path_params=path_params)
            results.append({{"operation_id": op_id, "data": r, "error": None}})
        except Exception as exc:
            results.append({{"operation_id": op_id, "data": None, "error": str(exc)}})
    return results
'''


def _gen_client(compatibility_date: str) -> str:
    return _CLIENT_TEMPLATE.format(compatibility_date=compatibility_date)


# ─────────────────────────────────────────────────────────────────────────────
# operations.py generator (one callable per operation_id)
# ─────────────────────────────────────────────────────────────────────────────

def _gen_operations(routes: list[dict], compatibility_date: str) -> str:
    lines: list[str] = [
        '"""',
        "esi/generated/operations.py",
        "────────────────────────────",
        "AUTO-GENERATED — do not edit by hand.",
        f"Source: ESI compatibility date {compatibility_date}",
        f"Operations: {len(routes)}",
        "",
        "One callable per operation_id.  Each function delegates to",
        "client.execute_operation() and returns the standardised response dict.",
        '"""',
        "# ruff: noqa",
        "from __future__ import annotations",
        "from typing import Any",
        "from esi.generated.client import execute_operation, fetch_all_pages",
        "",
    ]

    for route in routes:
        op_id = route.get("operation_id") or ""
        fn_name = _safe_ident(op_id)
        summary = route.get("summary") or op_id
        method = route.get("method", "GET")
        scopes = route.get("scopes") or []
        path = route.get("path", "")
        is_auth = route.get("requires_auth", False)
        has_pages = route.get("pagination", {}).get("has_page_param", False)
        path_params = [
            p["name"] for p in route.get("parameters", [])
            if p.get("in") == "path" and p.get("name")
        ]

        # Build function signature
        sig_parts = ["*"]
        for pp in path_params:
            sig_parts.append(f"{_safe_ident(pp)}: Any")
        if is_auth:
            sig_parts.append("token: str")
        else:
            sig_parts.append("token: str | None = None")
        sig_parts.append("query_params: dict | None = None")
        if method != "GET":
            sig_parts.append("json_body: Any = None")
        if has_pages:
            sig_parts.append("all_pages: bool = False")
        sig = ", ".join(sig_parts)

        lines.append(f"def {fn_name}({sig}) -> dict | list:")
        lines.append(f'    """{summary[:120]}')
        lines.append(f"    Method: {method}  Path: {path}")
        if scopes:
            lines.append(f"    Scopes: {', '.join(scopes)}")
        lines.append('    """')

        # Build path_params dict
        if path_params:
            pp_dict = "{" + ", ".join(f'"{pp}": {_safe_ident(pp)}' for pp in path_params) + "}"
        else:
            pp_dict = "None"

        if has_pages:
            lines.append(f"    if all_pages:")
            lines.append(f"        return fetch_all_pages({repr(op_id)}, path_params={pp_dict}, query_params=query_params, token=token)")
        lines.append(f"    return execute_operation({repr(op_id)}, path_params={pp_dict}, query_params=query_params, token=token" + (f", json_body=json_body" if method != "GET" else "") + ")")
        lines.append("")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# __init__.py generator
# ─────────────────────────────────────────────────────────────────────────────

def _gen_init(compatibility_date: str, route_count: int, schema_count: int, scope_count: int) -> str:
    return f'''"""
esi/generated/__init__.py
──────────────────────────
AUTO-GENERATED — do not edit by hand.
Compatibility date: {compatibility_date}
Operations: {route_count} | Schemas: {schema_count} | Scopes: {scope_count}
"""
# ruff: noqa
COMPATIBILITY_DATE = {repr(compatibility_date)}
OPERATION_COUNT = {route_count}
SCHEMA_COUNT = {schema_count}
SCOPE_COUNT = {scope_count}
'''


# ─────────────────────────────────────────────────────────────────────────────
# Main generate() entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate(
    compatibility_date: str | None = None,
    output_dir: str | None = None,
    force: bool = False,
) -> dict:
    """
    Read the active ESI spec snapshot and write the ``esi/generated/`` package.

    Parameters
    ----------
    compatibility_date:
        The spec version to use.  Defaults to the active date in latest.json.
    output_dir:
        Where to write the package.  Defaults to ``esi/generated/``.
    force:
        If False (default), skip generation when the package already matches
        the active compatibility date.

    Returns
    -------
    dict with keys: compatibility_date, operation_count, schema_count, scope_count.
    """
    info = _latest_info()
    date = compatibility_date or info["compatibility_date"]
    out = Path(output_dir or "esi/generated")

    # Check if already current
    init_path = out / "__init__.py"
    if not force and init_path.exists():
        content = init_path.read_text(encoding="utf-8")
        if f"COMPATIBILITY_DATE = {repr(date)}" in content:
            print(f"[codegen] esi/generated/ already at {date} — nothing to do.  Use force=True to regenerate.")
            routes = _load_routes(date)
            schemas = _load_schemas(date)
            all_scopes = sorted({s for r in routes for s in r.get("scopes", [])})
            return {
                "compatibility_date": date,
                "operation_count": len(routes),
                "schema_count": len(schemas),
                "scope_count": len(all_scopes),
            }

    routes = _load_routes(date)
    schemas = _load_schemas(date)
    all_scopes = sorted({s for r in routes for s in r.get("scopes", [])})

    out.mkdir(parents=True, exist_ok=True)

    (out / "__init__.py").write_text(_gen_init(date, len(routes), len(schemas), len(all_scopes)), encoding="utf-8")
    (out / "manifest.py").write_text(_gen_manifest(routes, date), encoding="utf-8")
    (out / "schemas.py").write_text(_gen_schemas(schemas, date), encoding="utf-8")
    (out / "client.py").write_text(_gen_client(date), encoding="utf-8")
    (out / "operations.py").write_text(_gen_operations(routes, date), encoding="utf-8")

    result = {
        "compatibility_date": date,
        "operation_count": len(routes),
        "schema_count": len(schemas),
        "scope_count": len(all_scopes),
    }
    print(
        f"[codegen] Generated esi/generated/ for {date} — "
        f"{len(routes)} operations, {len(schemas)} schemas, {len(all_scopes)} scopes."
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Fail-closed startup check
# ─────────────────────────────────────────────────────────────────────────────

def check_generated_is_current() -> None:
    """
    Verify the generated package matches the active ESI spec snapshot.
    Raises RuntimeError if the generated package is missing or stale.
    Called at app startup from main.py.
    """
    init_path = Path("esi/generated/__init__.py")
    if not init_path.exists():
        raise RuntimeError(
            "esi/generated/ package is missing.  Run util.esi_codegen.generate() "
            "or: python -m util.esi_codegen"
        )

    info = _latest_info()
    expected_date = info["compatibility_date"]
    expected_ops = info.get("route_count", 0)

    content = init_path.read_text(encoding="utf-8")
    if f"COMPATIBILITY_DATE = {repr(expected_date)}" not in content:
        raise RuntimeError(
            f"esi/generated/ is stale (expected {expected_date}).  "
            "Run: python -m util.esi_codegen"
        )

    if expected_ops:
        from esi.generated import OPERATION_COUNT
        if OPERATION_COUNT != expected_ops:
            raise RuntimeError(
                f"esi/generated/ operation count mismatch: "
                f"generated={OPERATION_COUNT}, spec={expected_ops}.  "
                "Run: python -m util.esi_codegen"
            )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _cli() -> None:
    parser = argparse.ArgumentParser(description="Generate esi/generated/ from the active ESI spec.")
    parser.add_argument("--date", metavar="YYYY-MM-DD", help="Spec compatibility date (defaults to latest)")
    parser.add_argument("--output", metavar="DIR", default="esi/generated", help="Output directory (default: esi/generated)")
    parser.add_argument("--force", action="store_true", help="Regenerate even if already current")
    args = parser.parse_args()
    result = generate(compatibility_date=args.date, output_dir=args.output, force=args.force)
    print(f"Done: {result}")


if __name__ == "__main__":
    _cli()
