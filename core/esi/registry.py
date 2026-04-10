import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

ESI_BASE_URL = "https://esi.evetech.net"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_specs_root() -> Path:
    return Path(os.getenv("ESI_SPECS_FOLDER", "_esi_specs"))


def fetch_compatibility_dates(timeout: int = 30) -> list[str]:
    response = requests.get(f"{ESI_BASE_URL}/meta/compatibility-dates", timeout=timeout)
    response.raise_for_status()
    payload = response.json() or []
    if isinstance(payload, dict):
        dates = payload.get("compatibility_dates") or []
    else:
        dates = payload
    if not isinstance(dates, list):
        raise RuntimeError("Unexpected compatibility date payload from ESI")
    return sorted(str(item) for item in dates)


def fetch_latest_compatibility_date(timeout: int = 30) -> str:
    dates = fetch_compatibility_dates(timeout=timeout)
    if not dates:
        raise RuntimeError("No compatibility dates returned by ESI")
    return dates[-1]


def fetch_openapi_spec(compatibility_date: str, timeout: int = 60) -> dict:
    response = requests.get(
        f"{ESI_BASE_URL}/meta/openapi.json",
        params={"compatibility_date": compatibility_date},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json() or {}
    if not isinstance(data, dict):
        raise RuntimeError("Unexpected OpenAPI payload from ESI")
    return data


def _extract_scopes(security: list[dict] | None) -> list[str]:
    scopes: set[str] = set()
    for entry in security or []:
        for values in entry.values():
            if isinstance(values, list):
                scopes.update(str(item) for item in values)
    return sorted(scopes)


def _route_requires_auth(security: list[dict] | None) -> bool:
    return bool(security)


def _queue_channel_for_security(security: list[dict] | None) -> str:
    return "private" if _route_requires_auth(security) else "public"


def _collect_schema_refs(node: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            refs.add(ref.rsplit("/", 1)[-1])
        for value in node.values():
            refs.update(_collect_schema_refs(value))
    elif isinstance(node, list):
        for item in node:
            refs.update(_collect_schema_refs(item))
    return refs


def _resolve_parameter(spec: dict, parameter: dict | None) -> dict:
    if not isinstance(parameter, dict):
        return {}
    ref = parameter.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/components/parameters/"):
        return parameter
    name = ref.rsplit("/", 1)[-1]
    resolved = (((spec.get("components") or {}).get("parameters") or {}).get(name) or {}).copy()
    overlay = {key: value for key, value in parameter.items() if key != "$ref"}
    resolved.update(overlay)
    return resolved


def _build_routes(spec: dict) -> list[dict]:
    routes: list[dict] = []
    for path, methods in sorted((spec.get("paths") or {}).items()):
        if not isinstance(methods, dict):
            continue
        for method, operation in sorted(methods.items()):
            if method.lower() not in {"get", "post", "put", "delete", "patch", "head", "options"}:
                continue
            security = operation.get("security") or []
            request_body_schema_refs = sorted(
                _collect_schema_refs(((operation.get("requestBody") or {}).get("content") or {}))
            )
            response_schema_refs: dict[str, list[str]] = {}
            for status_code, response in sorted((operation.get("responses") or {}).items()):
                refs = sorted(_collect_schema_refs(((response or {}).get("content") or {})))
                if refs:
                    response_schema_refs[str(status_code)] = refs
            route = {
                "route_key": f"{method.upper()} {path}",
                "method": method.upper(),
                "path": path,
                "operation_id": operation.get("operationId"),
                "summary": operation.get("summary"),
                "description": operation.get("description"),
                "tags": operation.get("tags") or [],
                "compatibility_date": operation.get("x-compatibility-date"),
                "cache_age": operation.get("x-cache-age"),
                "cache_mode": operation.get("x-cache-mode"),
                "pagination": {
                    "mode": operation.get("x-pagination"),
                    "has_page_param": any((param or {}).get("name") == "page" for param in (operation.get("parameters") or [])),
                },
                "required_roles": operation.get("x-required-roles") or [],
                "rate_limit": operation.get("x-rate-limit"),
                "scopes": _extract_scopes(operation.get("security")),
                "security": security,
                "requires_auth": _route_requires_auth(security),
                "queue_channel": _queue_channel_for_security(security),
                "parameters": [
                    {
                        "name": resolved.get("name"),
                        "in": resolved.get("in"),
                        "required": resolved.get("required", False),
                        "schema": resolved.get("schema"),
                    }
                    for param in (operation.get("parameters") or [])
                    for resolved in [_resolve_parameter(spec, param)]
                    if resolved
                ],
                "request_body_schema_refs": request_body_schema_refs,
                "response_schema_refs": response_schema_refs,
            }
            routes.append(route)
    return routes


def _build_scopes(routes: list[dict]) -> dict[str, list[dict]]:
    scopes: dict[str, list[dict]] = {}
    for route in routes:
        for scope in route.get("scopes") or []:
            scopes.setdefault(scope, []).append(
                {
                    "method": route["method"],
                    "path": route["path"],
                    "operation_id": route.get("operation_id"),
                    "summary": route.get("summary"),
                }
            )
    return {scope: sorted(entries, key=lambda row: (row["path"], row["method"])) for scope, entries in sorted(scopes.items())}


def _render_agents_md(compatibility_date: str, routes: list[dict], scopes: dict[str, list[dict]], spec: dict) -> str:
    tag_counts: dict[str, int] = {}
    for route in routes:
        for tag in route.get("tags") or []:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    lines = [
        "# ESI API Notes",
        "",
        f"- Generated at: {_utc_now_iso()}",
        f"- Active compatibility date: `{compatibility_date}`",
        f"- Route count: `{len(routes)}`",
        f"- Scope count: `{len(scopes)}`",
        "",
        "## Request Rules",
        "",
        "- Send `X-Compatibility-Date` on requests that need explicit version pinning.",
        "- Respect `ETag`, `If-None-Match`, `Last-Modified`, and `If-Modified-Since` for cache-aware polling.",
        "- Use `X-Pages` when present for page-based pagination.",
        "- Some routes use cursor pagination via `x-pagination` metadata instead of numbered pages.",
        "",
        "## Common Headers",
        "",
        "- `Accept-Language`: `en`, `de`, `fr`, `ja`, `ru`, `zh`, `ko`, `es`",
        "- `X-Tenant`: defaults to `tranquility`",
        "- `X-Compatibility-Date`: required by the spec parameter model",
        "",
        "## Scope Groups",
        "",
    ]

    if scopes:
        for scope, entries in scopes.items():
            lines.append(f"### `{scope}`")
            lines.append("")
            for entry in entries[:12]:
                lines.append(f"- `{entry['method']}` `{entry['path']}`: {entry.get('summary') or entry.get('operation_id') or 'No summary'}")
            if len(entries) > 12:
                lines.append(f"- ... `{len(entries) - 12}` more route(s)")
            lines.append("")
    else:
        lines.append("- No OAuth scopes were declared in the current spec.")
        lines.append("")

    lines.extend(
        [
            "## Route Tags",
            "",
        ]
    )
    for tag, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{tag}`: `{count}` route(s)")

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Public market, universe, and status routes often have `x-cache-age` values and should be cached aggressively.",
            "- Corporation and fleet routes frequently include both OAuth scope requirements and `x-required-roles` metadata.",
            "- The raw `openapi.json` remains the source of truth; this document is a quick operating summary.",
            "",
            f"Spec title: `{((spec.get('info') or {}).get('title') or 'ESI')}`",
        ]
    )
    return "\n".join(lines) + "\n"


def get_registry_paths(compatibility_date: str | None = None) -> dict[str, Path]:
    status = get_registry_status()
    if not compatibility_date:
        compatibility_date = status.get("compatibility_date")
    if not compatibility_date:
        raise FileNotFoundError("No active ESI registry is available.")

    root = get_specs_root()
    target_dir = root / compatibility_date
    return {
        "root": root,
        "target_dir": target_dir,
        "openapi_json": target_dir / "openapi.json",
        "routes_json": target_dir / "routes.json",
        "scopes_json": target_dir / "scopes.json",
        "schemas_json": target_dir / "schemas.json",
        "agents_md": target_dir / "AGENTS.md",
        "latest_json": root / "latest.json",
    }


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_routes(compatibility_date: str | None = None) -> list[dict]:
    return _load_json(get_registry_paths(compatibility_date)["routes_json"])


def load_scopes(compatibility_date: str | None = None) -> dict[str, list[dict]]:
    return _load_json(get_registry_paths(compatibility_date)["scopes_json"])


def load_schemas(compatibility_date: str | None = None) -> dict[str, dict]:
    return _load_json(get_registry_paths(compatibility_date)["schemas_json"])


def iter_routes(
    *,
    compatibility_date: str | None = None,
    queue_channel: str | None = None,
    tag: str | None = None,
) -> list[dict]:
    routes = load_routes(compatibility_date)
    results: list[dict] = []
    for route in routes:
        if queue_channel and route.get("queue_channel") != queue_channel:
            continue
        if tag and tag not in (route.get("tags") or []):
            continue
        results.append(route)
    return results


def find_route(
    *,
    method: str | None = None,
    path: str | None = None,
    operation_id: str | None = None,
    compatibility_date: str | None = None,
) -> dict | None:
    normalized_method = method.upper() if method else None
    for route in load_routes(compatibility_date):
        if operation_id and route.get("operation_id") == operation_id:
            return route
        if normalized_method and path and route.get("method") == normalized_method and route.get("path") == path:
            return route
    return None


def route_requires_auth(route: dict) -> bool:
    return bool(route.get("requires_auth"))


def route_queue_channel(route: dict) -> str:
    return route.get("queue_channel") or _queue_channel_for_security(route.get("security"))


def get_schema(schema_name: str, compatibility_date: str | None = None) -> dict | None:
    return load_schemas(compatibility_date).get(schema_name)


def build_route_path(route: dict, path_params: dict[str, Any] | None = None) -> str:
    values = path_params or {}
    missing: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            missing.append(key)
            return match.group(0)
        return str(values[key])

    path = re.sub(r"\{([^{}]+)\}", _replace, route["path"])
    if missing:
        raise ValueError(f"Missing path parameters for route {route['route_key']}: {', '.join(sorted(missing))}")
    return path


def execute_route(
    *,
    method: str | None = None,
    path: str | None = None,
    operation_id: str | None = None,
    route: dict | None = None,
    path_params: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    json_body: Any | None = None,
    token: str | None = None,
    headers: dict[str, str] | None = None,
    accept_language: str | None = None,
    tenant: str = "tranquility",
    compatibility_date: str | None = None,
    timeout: int = 30,
) -> dict:
    from core.esi.request import esi_request

    selected_route = route or find_route(
        method=method,
        path=path,
        operation_id=operation_id,
        compatibility_date=compatibility_date,
    )
    if not selected_route:
        raise LookupError("Unable to resolve the requested ESI route from the registry.")

    request_headers = {"Accept": "application/json", **(headers or {})}
    active_date = compatibility_date or get_registry_status().get("compatibility_date")
    if active_date:
        request_headers.setdefault("X-Compatibility-Date", active_date)
    if accept_language:
        request_headers.setdefault("Accept-Language", accept_language)
    request_headers.setdefault("X-Tenant", tenant)

    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    elif route_requires_auth(selected_route):
        raise PermissionError(f"{selected_route['route_key']} requires authentication and no token was provided.")

    resolved_path = build_route_path(selected_route, path_params)
    response = esi_request(
        selected_route["method"],
        f"{ESI_BASE_URL}{resolved_path}",
        params=query_params,
        json=json_body,
        headers=request_headers,
        timeout=timeout,
    )
    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            body = response.json() if response.content else None
        except ValueError:
            body = response.text
    else:
        body = response.text

    return {
        "route": selected_route,
        "queue_channel": route_queue_channel(selected_route),
        "url": response.url,
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body": body,
    }


def refresh_esi_spec_registry(compatibility_date: str | None = None) -> dict:
    active_date = compatibility_date or fetch_latest_compatibility_date()
    spec = fetch_openapi_spec(active_date)
    routes = _build_routes(spec)
    scopes = _build_scopes(routes)
    schemas = (spec.get("components") or {}).get("schemas") or {}

    root = get_specs_root()
    target_dir = root / active_date
    target_dir.mkdir(parents=True, exist_ok=True)

    openapi_path = target_dir / "openapi.json"
    routes_path = target_dir / "routes.json"
    scopes_path = target_dir / "scopes.json"
    schemas_path = target_dir / "schemas.json"
    agents_path = target_dir / "AGENTS.md"
    latest_path = root / "latest.json"

    openapi_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    routes_path.write_text(json.dumps(routes, indent=2, ensure_ascii=False), encoding="utf-8")
    scopes_path.write_text(json.dumps(scopes, indent=2, ensure_ascii=False), encoding="utf-8")
    schemas_path.write_text(json.dumps(schemas, indent=2, ensure_ascii=False), encoding="utf-8")
    agents_path.write_text(_render_agents_md(active_date, routes, scopes, spec), encoding="utf-8")

    latest_payload = {
        "compatibility_date": active_date,
        "generated_at": _utc_now_iso(),
        "openapi_json": str(openapi_path),
        "routes_json": str(routes_path),
        "scopes_json": str(scopes_path),
        "schemas_json": str(schemas_path),
        "agents_md": str(agents_path),
        "route_count": len(routes),
        "scope_count": len(scopes),
        "schema_count": len(schemas),
    }
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(json.dumps(latest_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    try:
        from core.io import public

        public.sync_esi_registry_to_warehouse(
            compatibility_date=active_date,
            registry_root=root,
        )
    except Exception as exc:
        logger.warning("Failed to sync ESI registry into DuckDB warehouse: %s", exc)

    logger.info("ESI spec registry refreshed for compatibility date %s", active_date)
    return get_registry_status()


def get_registry_status() -> dict:
    root = get_specs_root()
    latest_path = root / "latest.json"
    status = {
        "available": latest_path.exists(),
        "root": str(root),
        "latest_pointer": str(latest_path),
    }
    if not latest_path.exists():
        return status

    try:
        payload = json.loads(latest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        status["available"] = False
        status["error"] = str(exc)
        return status

    status.update(payload)
    return status
