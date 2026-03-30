# tools/_adapters.py
"""Concrete adapters that wire the port interfaces to the live project infrastructure.

Module-level singletons (esi, tokens, storage, tasks) are imported by tool modules.
"""

from __future__ import annotations

from typing import Any

from esi.client.client import execute_operation, fetch_all_pages
from util import sde_store
from util.task_queue import enqueue as _enqueue
from util.utils import get_token


# ---------------------------------------------------------------------------
# ESI adapter
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
    def get(self, owner_id: int) -> dict[int, dict]:
        return get_token(owner_id)


# ---------------------------------------------------------------------------
# Storage adapter
# ---------------------------------------------------------------------------

class _LiveStorageAdapter:
    def connect(self) -> Any:
        return sde_store.connect()

    def market_price(
        self,
        type_id: int,
        region_id: int,
        buy: bool = False,
    ) -> float | None:
        con = sde_store.connect()
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
        con = sde_store.connect()
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
        con = sde_store.connect()
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
# Module-level singletons — import these in tool modules
# ---------------------------------------------------------------------------

esi: _LiveESIAdapter = _LiveESIAdapter()
tokens: _LiveTokenAdapter = _LiveTokenAdapter()
storage: _LiveStorageAdapter = _LiveStorageAdapter()
tasks: _LiveTaskAdapter = _LiveTaskAdapter()
