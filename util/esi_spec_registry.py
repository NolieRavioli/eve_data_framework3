import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

ESI_BASE_URL = "https://esi.evetech.net"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_specs_root() -> Path:
    return Path(os.getenv("PUBLIC_DATA_FOLDER", "_publicData")) / "esi_specs"


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


def _build_routes(spec: dict) -> list[dict]:
    routes: list[dict] = []
    for path, methods in sorted((spec.get("paths") or {}).items()):
        if not isinstance(methods, dict):
            continue
        for method, operation in sorted(methods.items()):
            if method.lower() not in {"get", "post", "put", "delete", "patch", "head", "options"}:
                continue
            route = {
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
                "security": operation.get("security") or [],
                "parameters": [
                    {
                        "name": (param or {}).get("name"),
                        "in": (param or {}).get("in"),
                        "required": (param or {}).get("required", False),
                    }
                    for param in (operation.get("parameters") or [])
                    if isinstance(param, dict)
                ],
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
