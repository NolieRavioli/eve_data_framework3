"""applications/_api.py — single interface for all application development.

Every application (BlueprintTool, routes, workers) imports exclusively from here.
This file is the boundary between core infrastructure and the applications layer.

Usage:
    from applications._api import BaseTool, ToolManifest, base_ctx, require_role
    from applications._api import db, tasks, scheduler, sde, esi, char_data

Plugin framework (BaseTool, ToolManifest, ToolRegistry) lives here rather than
in core/ — it only exists to support applications and has no business in core
infrastructure.

To expose new core functionality:
    1. Import it here from core.* (or analysis.* for collector functions).
    2. Add the name to __all__.
    No wrapper class needed unless connection lifecycle management is required.
"""
from __future__ import annotations

import types
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from flask import Blueprint, Flask

# ── Auth / nav helpers (re-exported from core.web) ────────────────────────────
from core.web.context import base_ctx
from core.auth import require_login, require_admin, require_role

# ── Config ────────────────────────────────────────────────────────────────────
from core.config import get_runtime_settings

# ═══════════════════════════════════════════════════════════════════════════════
# Plugin framework — BaseTool, ToolManifest, ToolRegistry
# (previously in core/plugin/base.py)
# ═══════════════════════════════════════════════════════════════════════════════

#: Valid values for ToolManifest.access_level.
ACCESS_LEVELS = ("public", "user", "admin", "site_owner")


@dataclass
class ToolManifest:
    """Static metadata about a tool, used for nav injection and scope-gating."""

    #: Short, URL-safe identifier (e.g. "market_browser").
    id: str
    #: Human-readable display name shown in the sidebar.
    name: str
    #: Single emoji or symbol used as the nav icon.
    icon: str
    #: One-line description shown in tooltips / future tool catalogue.
    description: str
    #: URL prefix for the tool's blueprint (e.g. "/tools/market").
    url_prefix: str
    #: ESI scopes required to use this tool; empty list = public tool.
    required_scopes: list[str] = field(default_factory=list)
    #: Lower value = higher position in the nav list.
    nav_weight: int = 50
    #: Sidebar section this tool appears in (visual grouping only).
    #: "overview" | "tools" | "apps" | "admin" | "" (hidden)
    nav_section: str = "apps"
    #: Who can access this tool.
    #: "public" = no login | "user" = logged-in | "admin" = site admin
    #: "site_owner" = site owner only
    access_level: str = "user"
    #: Named role required to access this tool (in addition to access_level).
    required_role: str | None = None


class BaseTool(ABC):
    """Abstract base that every tool must implement."""

    manifest: ToolManifest

    @abstractmethod
    def create_blueprint(self) -> Blueprint:
        """Return a configured Flask Blueprint for this tool."""
        ...


class ToolRegistry:
    """Central registry that collects tools and exposes them to Flask and templates."""

    def __init__(self) -> None:
        self._tools: list[BaseTool] = []

    def register(self, tool: BaseTool) -> None:
        self._tools.append(tool)

    def register_blueprints(self, app: Flask) -> None:
        """Register each tool's blueprint with the Flask app."""
        for tool in self._tools:
            bp = tool.create_blueprint()
            prefix = tool.manifest.url_prefix
            if prefix:
                app.register_blueprint(bp, url_prefix=prefix)
            else:
                app.register_blueprint(bp)

    def nav_entries(self) -> list[ToolManifest]:
        """Return manifests sorted by nav_weight (ascending)."""
        return sorted((t.manifest for t in self._tools), key=lambda m: m.nav_weight)

    def check_scopes(self, granted: list[str]) -> dict[str, bool]:
        """Return tool_id → bool: whether all required scopes are in *granted*."""
        granted_set = set(granted)
        return {
            t.manifest.id: all(s in granted_set for s in t.manifest.required_scopes)
            for t in self._tools
        }

    def check_access(
        self,
        *,
        is_logged_in: bool = False,
        is_admin: bool = False,
        is_site_owner: bool = False,
        roles: list[str] | None = None,
    ) -> dict[str, bool]:
        """Return tool_id → bool indicating whether the current session may see this tool."""
        roles_set = set(roles or [])
        result: dict[str, bool] = {}
        for t in self._tools:
            level = t.manifest.access_level
            required_role = t.manifest.required_role
            if level == "public":
                ok = True
            elif level == "user":
                if is_admin or is_site_owner:
                    ok = True
                elif is_logged_in:
                    ok = (not required_role) or (required_role in roles_set)
                else:
                    ok = False
            elif level == "admin":
                ok = is_admin or is_site_owner
            elif level == "site_owner":
                ok = is_site_owner
            else:
                ok = False
            result[t.manifest.id] = ok
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# Infrastructure adapters
# (previously in applications/_adapters.py)
# ═══════════════════════════════════════════════════════════════════════════════

# ── SDE ───────────────────────────────────────────────────────────────────────
import core.db.sde as sde  # the module itself is the public API

# ── DB ────────────────────────────────────────────────────────────────────────
from core.db import public as _pub
from core.db.private import get_private_session as _get_private_session
from core.db.reader import (
    query_rows as _read_public,
    query_one as _read_public_one,
    query_scalar as _read_public_scalar,
)
from core.db.private import read_private as _read_private
from core.db.stats import get_db_gateway_stats
from core.db.reader import get_db_file_stats


class _DB:
    """Connection-lifecycle-aware DuckDB helpers."""

    connect = staticmethod(_pub.connect)

    def query(self, sql: str, params: list | None = None) -> list[dict]:
        return _read_public(sql, params)

    def query_one(self, sql: str, params: list | None = None) -> dict | None:
        return _read_public_one(sql, params)

    def scalar(self, sql: str, params: list | None = None) -> Any:
        return _read_public_scalar(sql, params)

    def private_query(self, owner_id: int, sql: str, params: dict | None = None) -> list[dict]:
        return _read_private(owner_id, sql, params)

    def market_price(self, type_id: int, region_id: int, buy: bool = False) -> float | None:
        from core.db.market_buffer import try_market_price
        hit, price = try_market_price(type_id, region_id, buy)
        if hit:
            return price
        if buy:
            return self.scalar(
                "SELECT MAX(price) FROM market_orders"
                " WHERE type_id = ? AND region_id = ? AND is_buy_order = TRUE",
                [type_id, region_id],
            )
        return self.scalar(
            "SELECT MIN(price) FROM market_orders"
            " WHERE type_id = ? AND region_id = ? AND is_buy_order = FALSE",
            [type_id, region_id],
        )


db = _DB()

# ── Character data ────────────────────────────────────────────────────────────
from core.db.models import Character as _Character


class _CharData:
    """Per-character private SQLite reads with ORM → dict conversion."""

    def get_character(self, owner_id: int, character_id: int) -> dict | None:
        session = _get_private_session(owner_id)
        try:
            char = session.get(_Character, character_id)
            if not char:
                return None
            return {
                "character_id": char.character_id,
                "name": char.name,
                "scopes": char.scopes,
                "token_expires": getattr(char, "token_expires", None),
            }
        finally:
            session.close()

    def get_characters(self, owner_id: int) -> list[dict]:
        """Return all character dicts for an owner."""
        session = _get_private_session(owner_id)
        try:
            chars = session.query(_Character).all()
            return [
                {
                    "character_id": c.character_id,
                    "name": c.name,
                    "scopes": c.scopes,
                    "token_expires": getattr(c, "token_expires", None),
                }
                for c in chars
            ]
        except Exception:
            return []
        finally:
            session.close()

    def get_scopes(self, owner_id: int, character_id: int) -> list[str]:
        info = self.get_character(owner_id, character_id)
        if not info or not info.get("scopes"):
            return []
        return info["scopes"].split()


char_data = _CharData()

# ── Raw ESI ───────────────────────────────────────────────────────────────────
from core.esi import esi_get as _esi_get, esi_post as _esi_post, esi_request as _esi_request

raw_esi = types.SimpleNamespace(get=_esi_get, post=_esi_post, request=_esi_request)

# ── Token helpers ─────────────────────────────────────────────────────────────
from core.auth.tokens import (
    get_token as _get_token,
    fresh_token as _fresh_token,
    pick_token as _pick_token,
    resolve_default_owner_id as _resolve_default_owner_id,
)

tokens = types.SimpleNamespace(get=_get_token)
token_resolution = types.SimpleNamespace(
    resolve_default_owner_id=_resolve_default_owner_id,
    pick_token=_pick_token,
    fresh_token=_fresh_token,
)

# ── ESI typed client ──────────────────────────────────────────────────────────
from core.esi.generated.client import execute_operation as _execute_operation, fetch_all_pages as _fetch_all_pages

esi = types.SimpleNamespace(execute=_execute_operation, fetch_pages=_fetch_all_pages)

# ── Task queue ────────────────────────────────────────────────────────────────
from core.tasks import (
    enqueue as _enqueue,
    get_task,
    get_all_tasks,
    get_tasks_for_owner,
    cancel_task,
    clear_tasks,
)

tasks = types.SimpleNamespace(enqueue=_enqueue)


def _get_esi_rate_stats() -> dict:
    from core.esi.rate import get_esi_rate_limiter
    limiter = get_esi_rate_limiter()
    return limiter.get_stats() if limiter else {}


queue_info = types.SimpleNamespace(
    get_all_tasks=get_all_tasks,
    get_tasks_for_owner=get_tasks_for_owner,
    get_task=get_task,
    cancel_task=cancel_task,
    clear_tasks=clear_tasks,
    get_esi_rate_stats=_get_esi_rate_stats,
)

# ── Scheduler ─────────────────────────────────────────────────────────────────
from core.tasks.engine import get_engine as _get_scheduler


def _scheduler_list_jobs() -> list[dict]:
    return _get_scheduler().list_jobs()


def _scheduler_set_enabled(job_id: str, enabled: bool) -> None:
    _get_scheduler().set_enabled(job_id, enabled)


def _scheduler_run_now(job_id: str) -> str:
    return _get_scheduler().run_now(job_id)


def _scheduler_get_job(job_id: str) -> dict | None:
    return _get_scheduler().get_job(job_id)


def _scheduler_set_interval(job_id: str, interval_s: int) -> None:
    _get_scheduler().set_interval(job_id, interval_s)


def _scheduler_get_run_history(job_id: str, limit: int = 25) -> list[dict]:
    return _get_scheduler().get_run_history(job_id, limit)


scheduler = types.SimpleNamespace(
    list_jobs=_scheduler_list_jobs,
    set_enabled=_scheduler_set_enabled,
    run_now=_scheduler_run_now,
    get_job=_scheduler_get_job,
    set_interval=_scheduler_set_interval,
    get_run_history=_scheduler_get_run_history,
)

# ── ESI registry ──────────────────────────────────────────────────────────────
from core.esi.registry import get_registry_status as _get_registry_status

esi_registry = types.SimpleNamespace(get_status=_get_registry_status)

# ── ESI manifest ──────────────────────────────────────────────────────────────
def _esi_manifest_get_operations() -> list[dict]:
    from core.esi.generated.manifest import OPERATIONS
    return sorted(
        OPERATIONS.values(),
        key=lambda o: ((o.get("tags") or [""])[0], o.get("operation_id", "")),
    )


def _esi_manifest_get_operation(op_id: str) -> dict | None:
    from core.esi.generated.manifest import OPERATIONS
    return OPERATIONS.get(op_id)


def _esi_manifest_get_meta() -> dict:
    from core.esi.generated.manifest import COMPATIBILITY_DATE, OPERATION_COUNT, ALL_SCOPES
    return {
        "compatibility_date": COMPATIBILITY_DATE,
        "operation_count": OPERATION_COUNT,
        "scope_count": len(ALL_SCOPES),
    }


esi_manifest = types.SimpleNamespace(
    get_operations=_esi_manifest_get_operations,
    get_operation=_esi_manifest_get_operation,
    get_meta=_esi_manifest_get_meta,
)

# ── DB admin ──────────────────────────────────────────────────────────────────
from core.auth.identity import (
    get_site_admin as _identity_get_site_admin,
    list_public_users as _identity_list_users,
    upsert_site_admin as _identity_upsert_site_admin,
    delete_site_admin as _identity_delete_site_admin,
    delete_user as _identity_delete_user,
    get_user_roles as _identity_get_user_roles,
    grant_user_roles as _identity_grant_user_roles,
    revoke_user_role as _identity_revoke_user_role,
)
from core.db.stats import get_db_gateway_stats as _get_db_gateway_stats
from core.config import get_db_unit_weights as _get_db_unit_weights

db_admin = types.SimpleNamespace(
    list_tables=_pub.list_browser_tables,
    list_private_tables=_pub.list_private_browser_tables,
    query_sql=_pub.query_browser_sql,
    query_private_sql=_pub.query_private_browser_sql,
    table_counts=_pub.public_table_counts,
    get_warehouse_status=_pub.get_warehouse_status,
    get_site_admin=_identity_get_site_admin,
    list_users=_identity_list_users,
    upsert_site_admin=_identity_upsert_site_admin,
    delete_site_admin=_identity_delete_site_admin,
    delete_user=_identity_delete_user,
    get_user_roles=_identity_get_user_roles,
    grant_user_roles=_identity_grant_user_roles,
    revoke_user_role=_identity_revoke_user_role,
    get_db_gateway_stats=_get_db_gateway_stats,
    get_db_unit_weights=_get_db_unit_weights,
)

# ── Shared UI helpers ─────────────────────────────────────────────────────────

DEFAULT_REGION: int = 10000002  # The Forge (Jita)


def get_regions() -> list[dict]:
    """Return all market regions sorted by name."""
    try:
        rows = db.query("SELECT region_id, name_en FROM sde_mapRegions ORDER BY name_en")
        return [{"id": r["region_id"], "name": r["name_en"] or f"Region {r['region_id']}"} for r in rows]
    except Exception:
        return []


# ── Bus / monitoring ──────────────────────────────────────────────────────────
from core.bus.handler import bus_handler
from core.bus import get_bus_log, get_all_topics, get_recent, publish as bus_publish

# ── System bootstrap ──────────────────────────────────────────────────────────
from core.system.bootstrap import get_subsystem_status as _get_subsystem_status
from core.system.updater import (
    apply_release_update as _apply_release_update,
    get_latest_github_release as _get_latest_github_release,
    restart_process as _restart_process,
)


def _bootstrap_update_sde() -> str:
    from core.system.bootstrap import update_sde_full
    return _enqueue("SDE Update", update_sde_full, queue="public")


def _bootstrap_update_esi() -> str:
    from core.system.bootstrap import update_esi_full
    return _enqueue("ESI Spec + Codegen Update", update_esi_full, queue="public")


def _bootstrap_update_config() -> str:
    from core.system.bootstrap import update_config
    return _enqueue("Regenerate example.config.yaml", update_config, queue="public")


system_bootstrap = types.SimpleNamespace(
    get_status=_get_subsystem_status,
    update_sde=_bootstrap_update_sde,
    update_esi=_bootstrap_update_esi,
    update_config=_bootstrap_update_config,
)

system_update = types.SimpleNamespace(
    apply_release_update=_apply_release_update,
    get_latest_release=_get_latest_github_release,
    restart=_restart_process,
)

__all__ = [
    # Plugin framework
    "ACCESS_LEVELS",
    "ToolManifest",
    "BaseTool",
    "ToolRegistry",
    # Auth / nav / config
    "base_ctx",
    "require_login",
    "require_admin",
    "require_role",
    "get_runtime_settings",
    # Infrastructure adapters
    "sde",
    "db",
    "char_data",
    "raw_esi",
    "tokens",
    "token_resolution",
    "esi",
    "tasks",
    "queue_info",
    "scheduler",
    "esi_registry",
    "esi_manifest",
    "db_admin",
    "get_regions",
    "DEFAULT_REGION",
    "get_db_file_stats",
    "get_db_gateway_stats",
    "bus_handler",
    "get_bus_log",
    "get_all_topics",
    "get_recent",
    "bus_publish",
    "system_bootstrap",
    "system_update",
]
