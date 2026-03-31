"""Abstract port interfaces for the plugin framework (hexagonal / port-adapter pattern).

Concrete adapters live in adapters.py. Tests can inject stubs via these protocols.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ESIPort(Protocol):
    """Thin wrapper over the auto-generated ESI client."""

    def execute(
        self,
        op_id: str,
        *,
        path_params: dict | None = None,
        query_params: dict | None = None,
        token: str | None = None,
        page: int | None = None,
    ) -> dict:
        """Execute a single ESI operation; return the response dict."""
        ...

    def fetch_pages(
        self,
        op_id: str,
        *,
        path_params: dict | None = None,
        query_params: dict | None = None,
        token: str | None = None,
    ) -> list:
        """Fetch all pages for a paginated ESI operation; return combined body list."""
        ...


@runtime_checkable
class TokenPort(Protocol):
    """Access OAuth tokens for a given owner."""

    def get(self, owner_id: int) -> dict[int, dict]:
        """Return the token map for *owner_id* as returned by auth.get_token."""
        ...


@runtime_checkable
class StoragePort(Protocol):
    """DuckDB / SDE query helpers used by tools."""

    def connect(self) -> Any:
        """Return a fresh DuckDB connection (caller must close it)."""
        ...

    def market_price(
        self,
        type_id: int,
        region_id: int,
        buy: bool = False,
    ) -> float | None:
        """
        Return the best current price for *type_id* in *region_id*.

        buy=False → cheapest sell order (MIN price WHERE NOT is_buy_order)
        buy=True  → highest buy order  (MAX price WHERE     is_buy_order)
        Returns None when no orders exist.
        """
        ...

    def type_name(self, type_id: int) -> str:
        """Return the English name for *type_id*, or 'Type <id>' when not found."""
        ...

    def region_name(self, region_id: int) -> str:
        """Return the English name for *region_id*, or 'Region <id>' when not found."""
        ...


@runtime_checkable
class TaskPort(Protocol):
    """Background task queue interface."""

    def enqueue(
        self,
        name: str,
        fn,
        *args,
        owner_id: int = 0,
        queue: str = "public",
    ) -> str:
        """Enqueue *fn(*args)* and return the new task_id string."""
        ...
