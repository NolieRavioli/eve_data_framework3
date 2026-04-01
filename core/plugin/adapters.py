"""Concrete adapters that wire the port interfaces to the live project infrastructure.

Module-level singletons (esi, tokens, storage, tasks, raw_esi, sde, token_resolution,
char_data, esi_registry, db_admin, esi_manifest, queue_info) are imported by tool modules.
"""

from __future__ import annotations

from typing import Any

import requests

from core.esi.generated.client import execute_operation, fetch_all_pages
from core.db import publicDB
from core.queue.scheduler import enqueue as _enqueue
from core.esi.auth import get_token


# ---------------------------------------------------------------------------
# ESI adapter (typed client)
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
# Token adapter
# ---------------------------------------------------------------------------

class _LiveTokenAdapter:
    def get(self, owner_id: int, character_ids=None) -> dict[int, dict]:
        return get_token(owner_id, character_ids=character_ids)


# ---------------------------------------------------------------------------
# Storage adapter
# ---------------------------------------------------------------------------

class _LiveStorageAdapter:
    def connect(self) -> Any:
        return publicDB.connect()

    def market_price(
        self,
        type_id: int,
        region_id: int,
        buy: bool = False,
    ) -> float | None:
        con = publicDB.connect()
        try:
            if buy:
                row = con.execute(
                    """
                    SELECT MAX(price) FROM market_orders
                    WHERE type_id = ? AND region_id = ? AND is_buy_order = TRUE
                    """,
                    [type_id, region_id],
                ).fetchone()
            else:
                row = con.execute(
                    """
                    SELECT MIN(price) FROM market_orders
                    WHERE type_id = ? AND region_id = ? AND is_buy_order = FALSE
                    """,
                    [type_id, region_id],
                ).fetchone()
            return row[0] if row and row[0] is not None else None
        finally:
            con.close()

    def type_name(self, type_id: int) -> str:
        con = publicDB.connect()
        try:
            row = con.execute(
                "SELECT name_en FROM dim_types WHERE type_id = ?",
                [type_id],
            ).fetchone()
            return row[0] if row and row[0] else f"Type {type_id}"
        except Exception:
            return f"Type {type_id}"
        finally:
            con.close()

    def region_name(self, region_id: int) -> str:
        con = publicDB.connect()
        try:
            row = con.execute(
                "SELECT region_name FROM dim_regions WHERE region_id = ?",
                [region_id],
            ).fetchone()
            return row[0] if row and row[0] else f"Region {region_id}"
        except Exception:
            return f"Region {region_id}"
        finally:
            con.close()


# ---------------------------------------------------------------------------
# Task adapter
# ---------------------------------------------------------------------------

class _LiveTaskAdapter:
    def enqueue(
        self,
        name: str,
        fn,
        *args,
        owner_id: int = 0,
        queue: str = "public",
    ) -> str:
        return _enqueue(name, fn, *args, owner_id=owner_id, queue=queue)


# ---------------------------------------------------------------------------
# Raw ESI adapter (direct HTTP)
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
# SDE cache adapter
# ---------------------------------------------------------------------------

class _LiveSDEAdapter:
    def name_from_type_id(self, type_id: int) -> str:
        from core.sde import name_from_type_id
        return name_from_type_id(type_id)

    def type_id_from_name(self, name: str) -> int | None:
        from core.sde import type_id_from_name
        return type_id_from_name(name)

    def region_id_from_system_id(self, system_id: int) -> int | None:
        from core.sde import region_id_from_system_id
        return region_id_from_system_id(system_id)

    def system_name_from_id(self, system_id: int) -> str:
        from core.sde import system_name_from_id
        return system_name_from_id(system_id)

    def region_name_from_id(self, region_id: int) -> str:
        from core.sde import region_name_from_id
        return region_name_from_id(region_id)

    def security_from_system_id(self, system_id: int) -> float | None:
        from core.sde import security_from_system_id
        return security_from_system_id(system_id)

    def suggest_type_names(self, prefix: str, limit: int = 10) -> list[str]:
        from core.sde import suggest_type_names
        return suggest_type_names(prefix, limit)

    def blueprint_for_type(self, type_id: int) -> dict | None:
        from core.sde import blueprint_for_type
        return blueprint_for_type(type_id)

    def reprocess_materials(self, type_id: int) -> list[dict]:
        from core.sde import reprocess_materials
        return reprocess_materials(type_id)

    def group_id_from_type_id(self, type_id: int) -> int | None:
        from core.sde import group_id_from_type_id
        return group_id_from_type_id(type_id)

    def category_id_from_type(self, type_id: int) -> int | None:
        from core.sde import category_id_from_type
        return category_id_from_type(type_id)


# ---------------------------------------------------------------------------
# Token resolution adapter
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
# DB admin adapter
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
        from core.esi.generated.manifest import (
            COMPATIBILITY_DATE,
            OPERATION_COUNT,
            ALL_SCOPES,
        )
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
# Module-level singletons — import these in tool modules
# ---------------------------------------------------------------------------

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
# Module-level singletons — import these in tool modules
# ---------------------------------------------------------------------------

esi: _LiveESIAdapter = _LiveESIAdapter()
tokens: _LiveTokenAdapter = _LiveTokenAdapter()
storage: _LiveStorageAdapter = _LiveStorageAdapter()
tasks: _LiveTaskAdapter = _LiveTaskAdapter()
raw_esi: _LiveRawESIAdapter = _LiveRawESIAdapter()
sde: _LiveSDEAdapter = _LiveSDEAdapter()
token_resolution: _LiveTokenResolutionAdapter = _LiveTokenResolutionAdapter()
char_data: _LiveCharacterDataAdapter = _LiveCharacterDataAdapter()
esi_registry: _LiveESIRegistryAdapter = _LiveESIRegistryAdapter()
db_admin: _LiveDBAdminAdapter = _LiveDBAdminAdapter()
esi_manifest: _LiveESIManifestAdapter = _LiveESIManifestAdapter()
queue_info: _LiveQueueInfoAdapter = _LiveQueueInfoAdapter()
scheduler: _LiveSchedulerAdapter = _LiveSchedulerAdapter()
