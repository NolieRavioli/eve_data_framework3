"""Abstract port interfaces for the plugin framework (hexagonal / port-adapter pattern).

Concrete adapters live in adapters.py. Tests can inject stubs via these protocols.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import requests


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

    def get(self, owner_id: int, character_ids=None) -> dict[int, dict]:
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


# ---------------------------------------------------------------------------
# New ports — Phase 1c
# ---------------------------------------------------------------------------


@runtime_checkable
class RawESIPort(Protocol):
    """Direct ESI HTTP access (for collectors that build their own URLs)."""

    def get(self, url: str, **kwargs) -> requests.Response:
        """HTTP GET via the rate-limited ESI transport."""
        ...

    def post(self, url: str, **kwargs) -> requests.Response:
        """HTTP POST via the rate-limited ESI transport."""
        ...

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Arbitrary HTTP method via the rate-limited ESI transport."""
        ...


@runtime_checkable
class SDEPort(Protocol):
    """In-memory SDE cache lookups."""

    def name_from_type_id(self, type_id: int) -> str: ...
    def type_id_from_name(self, name: str) -> int | None: ...
    def region_id_from_system_id(self, system_id: int) -> int | None: ...
    def system_name_from_id(self, system_id: int) -> str: ...
    def region_name_from_id(self, region_id: int) -> str: ...
    def security_from_system_id(self, system_id: int) -> float | None: ...
    def suggest_type_names(self, prefix: str, limit: int = 10) -> list[str]: ...
    def blueprint_for_type(self, type_id: int) -> dict | None: ...
    def reprocess_materials(self, type_id: int) -> list[dict]: ...
    def group_id_from_type_id(self, type_id: int) -> int | None: ...
    def category_id_from_type(self, type_id: int) -> int | None: ...


@runtime_checkable
class TokenResolutionPort(Protocol):
    """Token resolution helpers used by collectors and admin tools."""

    def resolve_default_owner_id(self) -> int | None:
        """Return the first available owner_id, or None."""
        ...

    def pick_token(self, owner_id: int) -> tuple[int, dict]:
        """Return (character_id, token_data) for *owner_id*."""
        ...

    def fresh_token(self, owner_id: int, char_id: int, token_data: dict) -> tuple[int, dict]:
        """Refresh if needed and return (char_id, updated_token_data)."""
        ...


@runtime_checkable
class CharacterDataPort(Protocol):
    """Read-only access to per-character private data."""

    def get_character(self, owner_id: int, character_id: int) -> dict | None:
        """Return character info dict or None."""
        ...

    def get_scopes(self, owner_id: int, character_id: int) -> list[str]:
        """Return granted ESI scopes for a character."""
        ...


@runtime_checkable
class ESIRegistryPort(Protocol):
    """ESI spec registry status."""

    def get_status(self) -> dict:
        """Return a status summary dict (compatibility_date, route_count, etc.)."""
        ...


@runtime_checkable
class DBAdminPort(Protocol):
    """Administrative database operations (for admin tools like db_browser)."""

    def list_tables(self) -> dict[str, list[str]]:
        """Return {table_name: [column_names]} for the public DuckDB."""
        ...

    def list_private_tables(self, owner_id: int) -> dict[str, list[str]]:
        """Return {table_name: [column_names]} for a private SQLite DB."""
        ...

    def query_sql(self, sql: str, *, row_limit: int = 500) -> dict:
        """Execute read-only SQL against the public DuckDB; return {columns, rows}."""
        ...

    def query_private_sql(self, owner_id: int, sql: str, *, row_limit: int = 500) -> dict:
        """Execute read-only SQL against a private SQLite DB; return {columns, rows}."""
        ...

    def table_counts(self) -> dict[str, int]:
        """Return {table_name: row_count} for all public tables."""
        ...

    def get_warehouse_status(self) -> dict:
        """Return SDE warehouse status dict."""
        ...

    def get_site_admin(self, owner_id: int) -> dict | None:
        """Return site_admin row for *owner_id* or None."""
        ...

    def list_users(self) -> list[dict]:
        """Return all registered users."""
        ...

    def upsert_site_admin(self, **kwargs) -> None:
        """Insert or update a site_admin row."""
        ...

    def delete_site_admin(self, owner_id: int) -> bool:
        """Remove a site_admin row. Return True if deleted."""
        ...


@runtime_checkable
class ESIManifestPort(Protocol):
    """Access to the auto-generated ESI operation manifest."""

    def get_operations(self) -> list[dict]:
        """Return all operations sorted by (tag, operation_id)."""
        ...

    def get_operation(self, op_id: str) -> dict | None:
        """Return a single operation dict, or None."""
        ...

    def get_meta(self) -> dict:
        """Return {compatibility_date, operation_count, scope_count}."""
        ...


@runtime_checkable
class QueueInfoPort(Protocol):
    """Read-only access to task queue state and ESI rate stats."""

    def get_all_tasks(self) -> list:
        """Return all tasks across all owners."""
        ...

    def get_tasks_for_owner(self, owner_id: int) -> list:
        """Return tasks for a specific owner."""
        ...

    def get_task(self, task_id: str) -> Any:
        """Return a single task by ID."""
        ...

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending/running task."""
        ...

    def clear_tasks(self, owner_id: int = 0) -> int:
        """Clear completed/failed tasks. Return count removed."""
        ...

    def get_esi_rate_stats(self) -> dict:
        """Return ESI rate limiter statistics snapshot."""
        ...

    def rate_stream(self) -> Any:
        """Return a generator yielding SSE rate-limit events."""
        ...

    def log_stream(self, task_id: str) -> Any:
        """Return a generator yielding SSE log events for a task."""
        ...


@runtime_checkable
class SchedulerPort(Protocol):
    """Manage the background job scheduler."""

    def list_jobs(self) -> list[dict]:
        """Return all registered jobs with their current state."""
        ...

    def set_enabled(self, job_id: str, enabled: bool) -> None:
        """Enable or disable a job (persisted to DuckDB)."""
        ...

    def run_now(self, job_id: str) -> str:
        """Fire a job immediately; return the task_id."""
        ...
