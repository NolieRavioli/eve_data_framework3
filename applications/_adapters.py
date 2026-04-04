"""Core infrastructure for the applications layer.

To expose new core functionality to an application:
    1. Import it here from core.* (or analysis.* for collector functions).
    2. Add the name to __all__.
    No adapter class or wrapper needed.

Namespace objects (db, raw_esi, tasks, …) preserve the existing call-site API
(e.g. ``db.query(...)``, ``tasks.enqueue(...)``).  Two thin inline classes
(``_DB``, ``_CharData``) exist because they manage connection lifecycles or
ORM sessions — not as an architectural pattern to copy.
"""
from __future__ import annotations

import types
from typing import Any

import sqlalchemy as _sa

# ── SDE ───────────────────────────────────────────────────────────────────────
import core.sde as sde  # the module itself is the public API

# ── DB ────────────────────────────────────────────────────────────────────────
from core.db import publicDB as _pub
from core.db.privateDB import get_private_session as _get_private_session


class _DB:
    """Connection-lifecycle-aware DuckDB helpers."""

    connect = staticmethod(_pub.connect)

    def query(self, sql: str, params: list | None = None) -> list[dict]:
        con = _pub.connect()
        try:
            cur = con.execute(sql, params or [])
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            con.close()

    def query_one(self, sql: str, params: list | None = None) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: list | None = None) -> Any:
        con = _pub.connect()
        try:
            row = con.execute(sql, params or []).fetchone()
            return row[0] if row is not None else None
        finally:
            con.close()

    def private_query(self, owner_id: int, sql: str, params: dict | None = None) -> list[dict]:
        session = _get_private_session(owner_id)
        try:
            with session.bind.connect() as con:
                cur = con.execute(_sa.text(sql), params or {})
                cols = list(cur.keys())
                return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            session.close()

    def market_price(self, type_id: int, region_id: int, buy: bool = False) -> float | None:
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
from core.queue.esi_req import esi_get as _esi_get, esi_post as _esi_post, esi_request as _esi_request

raw_esi = types.SimpleNamespace(get=_esi_get, post=_esi_post, request=_esi_request)

# ── Token helpers ─────────────────────────────────────────────────────────────
from core.esi.auth import (
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
from core.queue import (
    enqueue as _enqueue,
    get_task,
    get_all_tasks,
    get_tasks_for_owner,
    cancel_task,
    clear_tasks,
    rate_stream,
    log_stream,
)

tasks = types.SimpleNamespace(enqueue=_enqueue)


def _get_esi_rate_stats() -> dict:
    from core.queue.esi_req import get_esi_rate_limiter
    limiter = get_esi_rate_limiter()
    return limiter.get_stats() if limiter else {}


queue_info = types.SimpleNamespace(
    get_all_tasks=get_all_tasks,
    get_tasks_for_owner=get_tasks_for_owner,
    get_task=get_task,
    cancel_task=cancel_task,
    clear_tasks=clear_tasks,
    rate_stream=rate_stream,
    log_stream=log_stream,
    get_esi_rate_stats=_get_esi_rate_stats,
)

# ── Scheduler ─────────────────────────────────────────────────────────────────
from core.scheduler import get_engine as _get_scheduler


def _scheduler_list_jobs() -> list[dict]:
    return _get_scheduler().list_jobs()


def _scheduler_set_enabled(job_id: str, enabled: bool) -> None:
    _get_scheduler().set_enabled(job_id, enabled)


def _scheduler_run_now(job_id: str) -> str:
    return _get_scheduler().run_now(job_id)


scheduler = types.SimpleNamespace(
    list_jobs=_scheduler_list_jobs,
    set_enabled=_scheduler_set_enabled,
    run_now=_scheduler_run_now,
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
db_admin = types.SimpleNamespace(
    list_tables=_pub.list_browser_tables,
    list_private_tables=_pub.list_private_browser_tables,
    query_sql=_pub.query_browser_sql,
    query_private_sql=_pub.query_private_browser_sql,
    table_counts=_pub.public_table_counts,
    get_warehouse_status=_pub.get_warehouse_status,
    get_site_admin=_pub.get_site_admin,
    list_users=_pub.list_public_users,
    upsert_site_admin=_pub.upsert_site_admin,
    delete_site_admin=_pub.delete_site_admin,
)

# ── Shared UI helpers ─────────────────────────────────────────────────────────

DEFAULT_REGION: int = 10000002  # The Forge (Jita)


def get_regions() -> list[dict]:
    """Return all market regions sorted by name."""
    try:
        rows = db.query("SELECT region_id, region_name FROM dim_regions ORDER BY region_name")
        return [{"id": r["region_id"], "name": r["region_name"] or f"Region {r['region_id']}"} for r in rows]
    except Exception:
        return []

# ── Market write helpers (for application workers that need to write orders) ──
upsert_market_orders = _pub.upsert_market_orders
mark_region_market_refreshed = _pub.mark_region_market_refreshed
__all__ = [
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
    "upsert_market_orders",
    "mark_region_market_refreshed",
]
