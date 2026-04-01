"""Concrete adapters that wire the live project infrastructure to the plugin layer.

Module-level singletons imported by application and analysis modules:
    db              — parameterised DuckDB + SQLite query helpers
    sde             — in-memory SDE cache (the core.sde module itself)
    raw_esi         — direct ESI HTTP (rate-limited)
    token_resolution — token refresh helpers for collectors
    esi             — typed ESI client (auto-generated)
    tokens          — raw token map access
    tasks           — background task enqueue
    char_data       — per-character private SQLite reads
    esi_registry    — ESI spec registry status
    db_admin        — administrative DuckDB/SQLite operations
    esi_manifest    — auto-generated ESI operation manifest
    queue_info      — task queue state + SSE streams
    scheduler       — background job scheduler control
"""

from __future__ import annotations

from typing import Any

import requests

from core.esi.generated.client import execute_operation, fetch_all_pages
from core.db import publicDB
from core.queue.scheduler import enqueue as _enqueue
from core.esi.auth import get_token

# The SDE module is its own clean API — expose it directly.
import core.sde as sde  # noqa: F401 — re-exported as singleton below


# ---------------------------------------------------------------------------
# DB adapter — connection-lifecycle-aware query helpers
# ---------------------------------------------------------------------------

class _LiveDBAdapter:
    """Parameterised query helpers that own the connection lifecycle.

    Use ``query``, ``query_one``, or ``scalar`` for straightforward reads.
    Use ``connect()`` as an escape hatch for complex/transactional work.
    """

    def connect(self) -> Any:
        """Return a fresh DuckDB connection. Caller is responsible for closing."""
        return publicDB.connect()

    def query(self, sql: str, params: list | None = None) -> list[dict]:
        """Execute *sql* against the public DuckDB and return rows as dicts."""
        con = publicDB.connect()
        try:
            cur = con.execute(sql, params or [])
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            con.close()

    def query_one(self, sql: str, params: list | None = None) -> dict | None:
        """Return the first row as a dict, or None if no results."""
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: list | None = None) -> Any:
        """Return the first column of the first row, or None."""
        con = publicDB.connect()
        try:
            row = con.execute(sql, params or []).fetchone()
            return row[0] if row is not None else None
        finally:
            con.close()

    def private_query(self, owner_id: int, sql: str, params: list | None = None) -> list[dict]:
        """Execute *sql* against the owner's private SQLite and return rows as dicts."""
        from core.db.privateDB import get_private_session
        import sqlalchemy as sa
        session = get_private_session(owner_id)
        try:
            with session.bind.connect() as con:
                cur = con.execute(sa.text(sql), params or {})
                cols = list(cur.keys())
                return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            session.close()

    def market_price(self, type_id: int, region_id: int, buy: bool = False) -> float | None:
        """Best current price for *type_id* in *region_id*.

        buy=False → cheapest sell order; buy=True → highest buy order.
        Returns None when no orders exist.
        """
        if buy:
            return self.scalar(
                "SELECT MAX(price) FROM market_orders WHERE type_id = ? AND region_id = ? AND is_buy_order = TRUE",
                [type_id, region_id],
            )
        return self.scalar(
            "SELECT MIN(price) FROM market_orders WHERE type_id = ? AND region_id = ? AND is_buy_order = FALSE",
            [type_id, region_id],
        )


# ---------------------------------------------------------------------------
# Raw ESI adapter (direct HTTP, rate-limited)
# ---------------------------------------------------------------------------

class _LiveRawESIAdapter:
    def get(self, url: str, **kwargs) -> requests.Response:
        from core.queue.esi_req import esi_get
        return esi_get(url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        from core.queue.esi_req import esi_post
        return esi_post(url, **kwargs)

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        from core.queue.esi_req import esi_request
        return esi_request(method, url, **kwargs)


# ---------------------------------------------------------------------------
# Token resolution adapter (collector auth helpers)
# ---------------------------------------------------------------------------

class _LiveTokenResolutionAdapter:
    def resolve_default_owner_id(self) -> int | None:
        from core.esi.auth import resolve_default_owner_id
        return resolve_default_owner_id()

    def pick_token(self, owner_id: int) -> tuple[int, dict]:
        from core.esi.auth import pick_token
        return pick_token(owner_id)

    def fresh_token(self, owner_id: int, char_id: int, token_data: dict) -> tuple[int, dict]:
        from core.esi.auth import fresh_token
        return fresh_token(owner_id, char_id, token_data)


# ---------------------------------------------------------------------------
# ESI adapter (typed auto-generated client)
# ---------------------------------------------------------------------------

class _LiveESIAdapter:
    def execute(
        self,
        op_id: str,
        *,
        path_params: dict | None = None,
        query_params: dict | None = None,
        token: str | None = None,
        page: int | None = None,
    ) -> dict:
        return execute_operation(
            op_id,
            path_params=path_params or {},
            query_params=query_params or {},
            token=token,
            page=page,
        )

    def fetch_pages(
        self,
        op_id: str,
        *,
        path_params: dict | None = None,
        query_params: dict | None = None,
        token: str | None = None,
    ) -> list:
        return fetch_all_pages(
            op_id,
            path_params=path_params or {},
            query_params=query_params or {},
            token=token,
        )


# ---------------------------------------------------------------------------
# Token adapter (raw token map access)
# ---------------------------------------------------------------------------

class _LiveTokenAdapter:
    def get(self, owner_id: int, character_ids=None) -> dict[int, dict]:
        return get_token(owner_id, character_ids=character_ids)


# ---------------------------------------------------------------------------
# Task adapter
# ---------------------------------------------------------------------------

class _LiveTaskAdapter:
    def enqueue(self, name: str, fn, *args, owner_id: int = 0, queue: str = "public") -> str:
        return _enqueue(name, fn, *args, owner_id=owner_id, queue=queue)


# ---------------------------------------------------------------------------
# Character data adapter
# ---------------------------------------------------------------------------

class _LiveCharacterDataAdapter:
    def get_character(self, owner_id: int, character_id: int) -> dict | None:
        from core.db.privateDB import get_private_session
        from core.db.models import Character
        session = get_private_session(owner_id)
        try:
            char = session.get(Character, character_id)
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

    def get_scopes(self, owner_id: int, character_id: int) -> list[str]:
        info = self.get_character(owner_id, character_id)
        if not info or not info.get("scopes"):
            return []
        return info["scopes"].split()


# ---------------------------------------------------------------------------
# ESI registry adapter
# ---------------------------------------------------------------------------

class _LiveESIRegistryAdapter:
    def get_status(self) -> dict:
        from core.esi.registry import get_registry_status
        return get_registry_status()


# ---------------------------------------------------------------------------
# DB admin adapter (for db_browser and admin_panel)
# ---------------------------------------------------------------------------

class _LiveDBAdminAdapter:
    def list_tables(self) -> dict[str, list[str]]:
        return publicDB.list_browser_tables()

    def list_private_tables(self, owner_id: int) -> dict[str, list[str]]:
        return publicDB.list_private_browser_tables(owner_id)

    def query_sql(self, sql: str, *, row_limit: int = 500) -> dict:
        return publicDB.query_browser_sql(sql, row_limit=row_limit)

    def query_private_sql(self, owner_id: int, sql: str, *, row_limit: int = 500) -> dict:
        return publicDB.query_private_browser_sql(owner_id, sql, row_limit=row_limit)

    def table_counts(self) -> dict[str, int]:
        return publicDB.public_table_counts()

    def get_warehouse_status(self) -> dict:
        return publicDB.get_warehouse_status()

    def get_site_admin(self, owner_id: int) -> dict | None:
        return publicDB.get_site_admin(owner_id)

    def list_users(self) -> list[dict]:
        return publicDB.list_public_users()

    def upsert_site_admin(self, **kwargs) -> None:
        publicDB.upsert_site_admin(**kwargs)

    def delete_site_admin(self, owner_id: int) -> bool:
        return publicDB.delete_site_admin(owner_id)


# ---------------------------------------------------------------------------
# ESI manifest adapter
# ---------------------------------------------------------------------------

class _LiveESIManifestAdapter:
    def get_operations(self) -> list[dict]:
        from core.esi.generated.manifest import OPERATIONS
        return sorted(
            OPERATIONS.values(),
            key=lambda o: ((o.get("tags") or [""])[0], o.get("operation_id", "")),
        )

    def get_operation(self, op_id: str) -> dict | None:
        from core.esi.generated.manifest import OPERATIONS
        return OPERATIONS.get(op_id)

    def get_meta(self) -> dict:
        from core.esi.generated.manifest import COMPATIBILITY_DATE, OPERATION_COUNT, ALL_SCOPES
        return {
            "compatibility_date": COMPATIBILITY_DATE,
            "operation_count": OPERATION_COUNT,
            "scope_count": len(ALL_SCOPES),
        }


# ---------------------------------------------------------------------------
# Queue info adapter
# ---------------------------------------------------------------------------

class _LiveQueueInfoAdapter:
    def get_all_tasks(self) -> list:
        from core.queue import get_all_tasks
        return get_all_tasks()

    def get_tasks_for_owner(self, owner_id: int) -> list:
        from core.queue import get_tasks_for_owner
        return get_tasks_for_owner(owner_id)

    def get_task(self, task_id: str) -> Any:
        from core.queue import get_task
        return get_task(task_id)

    def cancel_task(self, task_id: str) -> bool:
        from core.queue import cancel_task
        return cancel_task(task_id)

    def clear_tasks(self, owner_id: int = 0) -> int:
        from core.queue import clear_tasks
        return clear_tasks(owner_id)

    def get_esi_rate_stats(self) -> dict:
        from core.queue.esi_req import get_esi_rate_limiter
        limiter = get_esi_rate_limiter()
        return limiter.get_stats() if limiter else {}

    def rate_stream(self) -> Any:
        from core.queue import rate_stream
        return rate_stream()

    def log_stream(self, task_id: str) -> Any:
        from core.queue import log_stream
        return log_stream(task_id)


# ---------------------------------------------------------------------------
# Scheduler adapter
# ---------------------------------------------------------------------------

class _LiveSchedulerAdapter:
    def list_jobs(self) -> list[dict]:
        from core.scheduler import get_engine
        return get_engine().list_jobs()

    def set_enabled(self, job_id: str, enabled: bool) -> None:
        from core.scheduler import get_engine
        get_engine().set_enabled(job_id, enabled)

    def run_now(self, job_id: str) -> str:
        from core.scheduler import get_engine
        return get_engine().run_now(job_id)


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

db: _LiveDBAdapter = _LiveDBAdapter()
# sde is the core.sde module itself (imported at top) — identical public API, zero indirection
raw_esi: _LiveRawESIAdapter = _LiveRawESIAdapter()
token_resolution: _LiveTokenResolutionAdapter = _LiveTokenResolutionAdapter()
esi: _LiveESIAdapter = _LiveESIAdapter()
tokens: _LiveTokenAdapter = _LiveTokenAdapter()
tasks: _LiveTaskAdapter = _LiveTaskAdapter()
char_data: _LiveCharacterDataAdapter = _LiveCharacterDataAdapter()
esi_registry: _LiveESIRegistryAdapter = _LiveESIRegistryAdapter()
db_admin: _LiveDBAdminAdapter = _LiveDBAdminAdapter()
esi_manifest: _LiveESIManifestAdapter = _LiveESIManifestAdapter()
queue_info: _LiveQueueInfoAdapter = _LiveQueueInfoAdapter()
scheduler: _LiveSchedulerAdapter = _LiveSchedulerAdapter()

# Backward-compat alias — migrate callers to `db`, then remove
storage = db
