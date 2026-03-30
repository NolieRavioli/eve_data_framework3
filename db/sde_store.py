import json
import logging
import os
import re
import sqlite3
import time
from datetime import date, datetime, time as time_value, timezone
from pathlib import Path
from typing import Any, Iterable

import duckdb

logger = logging.getLogger(__name__)

DEFAULT_SDE_DATABASE = "_publicData/public.duckdb"
DEFAULT_PUBLIC_DATABASE = "_publicData/public.db"
_BROWSER_PUBLIC_TABLES = (
    "users",
    "site_admins",
    "market_orders",
    "public_contracts",
    "structures",
    "market_structures",
)
_BROWSER_ALLOWED_PREFIXES = ("SELECT", "WITH", "PRAGMA", "SHOW", "DESCRIBE")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _coerce_timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
    return None


def _json_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return _to_json(value)


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _query_to_dicts(con: duckdb.DuckDBPyConnection, sql: str, params: Iterable[Any] | None = None) -> list[dict]:
    result = con.execute(sql, params or [])
    columns = [desc[0] for desc in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def _query_one(con: duckdb.DuckDBPyConnection, sql: str, params: Iterable[Any] | None = None) -> dict | None:
    rows = _query_to_dicts(con, sql, params)
    return rows[0] if rows else None


def get_supported_languages() -> list[str]:
    raw = os.getenv("SUPPORTED_LANGUAGES", "en")
    values = [item.strip() for item in raw.split(",")]
    return [item for item in values if item]


def get_public_data_dir() -> Path:
    return Path(os.getenv("PUBLIC_DATA_FOLDER", "_publicData"))


def get_sde_root() -> Path:
    return Path(os.getenv("SDE_PATH", "_sde"))


def get_database_path(cfg: dict | None = None) -> Path:
    if cfg and cfg.get("database_file"):
        return Path(cfg["database_file"])
    return Path(os.getenv("SDE_DATABASE_FILE", DEFAULT_SDE_DATABASE))


def get_public_database_path() -> Path:
    raw_value = os.getenv("EVE_PUBLIC_DATABASE_FILE", DEFAULT_PUBLIC_DATABASE)
    candidate = Path(raw_value)
    if candidate.exists() or candidate.is_absolute() or candidate.parent != Path("."):
        return candidate
    fallback = get_public_data_dir() / candidate.name
    return fallback


def get_private_database_path(owner_id: int) -> Path:
    private_root = Path(os.getenv("EVE_PRIVATE_DATABASE_FOLDER", "_privateData/"))
    owner_value = int(owner_id)
    return private_root / str(owner_value) / f"{owner_value}.db"


def warehouse_exists(database_file: str | Path | None = None) -> bool:
    target = Path(database_file) if database_file else get_database_path()
    if not target.exists():
        return False
    try:
        con = connect(target, read_only=True)
        try:
            tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        finally:
            con.close()
        return "sde_manifest" in tables
    except Exception:
        return False


def connect(database_file: str | Path | None = None, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    target = Path(database_file) if database_file else get_database_path()
    if not read_only:
        target.parent.mkdir(parents=True, exist_ok=True)
    # DuckDB does not allow mixing read-only and read-write connections to the
    # same file within the same process. This app opens many short-lived
    # connections from different UI/task paths, so keep file-backed DuckDB
    # connections on a single configuration.
    effective_read_only = read_only
    if str(target) != ":memory:":
        effective_read_only = False
    con = duckdb.connect(str(target), read_only=effective_read_only)
    con.execute("PRAGMA threads=4")
    return con


def _ensure_registry_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS esi_registry_manifest (
            compatibility_date VARCHAR PRIMARY KEY,
            generated_at TIMESTAMP,
            routes_path VARCHAR,
            scopes_path VARCHAR,
            schemas_path VARCHAR,
            latest_pointer VARCHAR,
            route_count BIGINT,
            scope_count BIGINT,
            schema_count BIGINT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS esi_routes (
            compatibility_date VARCHAR,
            route_key VARCHAR,
            method VARCHAR,
            path VARCHAR,
            operation_id VARCHAR,
            summary VARCHAR,
            description VARCHAR,
            tags_json VARCHAR,
            compatibility_date_override VARCHAR,
            cache_age BIGINT,
            cache_mode VARCHAR,
            pagination_mode VARCHAR,
            has_page_param BOOLEAN,
            required_roles_json VARCHAR,
            rate_limit_json VARCHAR,
            scopes_json VARCHAR,
            security_json VARCHAR,
            parameters_json VARCHAR,
            requires_auth BOOLEAN,
            queue_channel VARCHAR,
            request_body_schema_refs_json VARCHAR,
            response_schema_refs_json VARCHAR,
            PRIMARY KEY (compatibility_date, route_key)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS esi_route_parameters (
            compatibility_date VARCHAR,
            route_key VARCHAR,
            parameter_name VARCHAR,
            parameter_in VARCHAR,
            required BOOLEAN,
            schema_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS esi_route_schema_refs (
            compatibility_date VARCHAR,
            route_key VARCHAR,
            direction VARCHAR,
            status_code VARCHAR,
            schema_name VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS esi_schemas (
            compatibility_date VARCHAR,
            schema_name VARCHAR,
            payload_json VARCHAR,
            PRIMARY KEY (compatibility_date, schema_name)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS esi_scopes (
            compatibility_date VARCHAR,
            scope_name VARCHAR,
            routes_json VARCHAR,
            PRIMARY KEY (compatibility_date, scope_name)
        )
        """
    )


def _systems_view_sql(*, temporary: bool = False) -> str:
    create_clause = "CREATE OR REPLACE TEMP VIEW" if temporary else "CREATE OR REPLACE VIEW"
    return f"""
        {create_clause} systems AS
        WITH
        planet_ids AS (
            SELECT system_id, list_sort(list(planet_id)) AS planets
            FROM dim_planets
            GROUP BY system_id
        ),
        moon_ids AS (
            SELECT system_id, list_sort(list(moon_id)) AS moons
            FROM dim_moons
            GROUP BY system_id
        ),
        stargate_ids AS (
            SELECT system_id, list_sort(list(stargate_id)) AS stargates
            FROM dim_stargates
            GROUP BY system_id
        ),
        neighbor_ids AS (
            SELECT system_id, list_sort(list(DISTINCT destination_system_id)) AS neighbors
            FROM dim_stargates
            GROUP BY system_id
        )
        SELECT
            s.system_id,
            s.region_id,
            CAST(NULL AS BIGINT) AS owner_id,
            r.faction_id,
            s.constellation_id,
            s.security,
            s.system_name,
            r.region_name,
            COALESCE(to_json(planet_ids.planets), '[]') AS planets,
            COALESCE(to_json(moon_ids.moons), '[]') AS moons,
            COALESCE(to_json(stargate_ids.stargates), '[]') AS stargates,
            COALESCE(to_json(neighbor_ids.neighbors), '[]') AS neighbors,
            s.planet_count,
            s.stargate_count,
            s.payload_json
        FROM dim_systems AS s
        LEFT JOIN dim_regions AS r
          ON r.region_id = s.region_id
        LEFT JOIN planet_ids
          ON planet_ids.system_id = s.system_id
        LEFT JOIN moon_ids
          ON moon_ids.system_id = s.system_id
        LEFT JOIN stargate_ids
          ON stargate_ids.system_id = s.system_id
        LEFT JOIN neighbor_ids
          ON neighbor_ids.system_id = s.system_id
    """


def _stargates_view_sql(*, temporary: bool = False) -> str:
    create_clause = "CREATE OR REPLACE TEMP VIEW" if temporary else "CREATE OR REPLACE VIEW"
    return f"""
        {create_clause} stargates AS
        SELECT
            stargate_id,
            CAST(NULL AS BIGINT) AS owner_id,
            type_id,
            system_id,
            destination_stargate_id AS destination_gate_id,
            destination_system_id,
            payload_json AS position,
            x,
            y,
            z,
            payload_json
        FROM dim_stargates
    """


def _ensure_public_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            owner_id BIGINT,
            character_id BIGINT PRIMARY KEY
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS site_admins (
            owner_id BIGINT PRIMARY KEY,
            is_site_owner BOOLEAN DEFAULT FALSE,
            granted_by BIGINT,
            granted_at TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS market_orders (
            order_id BIGINT PRIMARY KEY,
            type_id BIGINT,
            location_id BIGINT,
            region_id BIGINT,
            is_buy_order BOOLEAN,
            issued TIMESTAMP,
            duration BIGINT,
            price DOUBLE,
            order_range VARCHAR,
            volume_remain BIGINT,
            volume_total BIGINT,
            min_volume BIGINT,
            last_seen TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS public_contracts (
            contract_id BIGINT PRIMARY KEY,
            region_id BIGINT,
            issuer_id BIGINT,
            issuer_corporation_id BIGINT,
            contract_type VARCHAR,
            date_issued TIMESTAMP,
            date_expired TIMESTAMP,
            title VARCHAR,
            volume DOUBLE,
            price DOUBLE,
            buyout DOUBLE,
            collateral DOUBLE,
            reward DOUBLE,
            days_to_complete BIGINT,
            start_location_id BIGINT,
            end_location_id BIGINT,
            for_corporation BOOLEAN,
            last_seen TIMESTAMP
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS structures (
            structure_id BIGINT PRIMARY KEY,
            solar_system_id BIGINT,
            region_id BIGINT,
            owner_id BIGINT,
            name VARCHAR,
            type_id BIGINT,
            position_json VARCHAR,
            last_seen TIMESTAMP,
            forbidden_until TIMESTAMP,
            market_forbidden_until TIMESTAMP,
            market_refreshed_until TIMESTAMP,
            enrich_refreshed_until TIMESTAMP
        )
        """
    )
    # Migrate existing databases that predate optional columns.
    existing_cols = {row[0] for row in con.execute("DESCRIBE structures").fetchall()}
    if "forbidden_until" not in existing_cols:
        con.execute("ALTER TABLE structures ADD COLUMN forbidden_until TIMESTAMP")
    if "market_forbidden_until" not in existing_cols:
        con.execute("ALTER TABLE structures ADD COLUMN market_forbidden_until TIMESTAMP")
    if "market_refreshed_until" not in existing_cols:
        con.execute("ALTER TABLE structures ADD COLUMN market_refreshed_until TIMESTAMP")
    if "enrich_refreshed_until" not in existing_cols:
        con.execute("ALTER TABLE structures ADD COLUMN enrich_refreshed_until TIMESTAMP")

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS market_structures (
            structure_id BIGINT PRIMARY KEY,
            solar_system_id BIGINT,
            region_id BIGINT,
            owner_id BIGINT,
            name VARCHAR,
            type_id BIGINT,
            position_json VARCHAR,
            last_seen TIMESTAMP
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS market_region_cooldowns (
            region_id BIGINT PRIMARY KEY,
            refreshed_until TIMESTAMP
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS isk_per_hour_results (
            type_id     BIGINT NOT NULL,
            type_name   VARCHAR,
            region_id   BIGINT NOT NULL,
            category_id BIGINT,
            isk_per_run DOUBLE,
            isk_per_hour DOUBLE,
            margin_pct  DOUBLE,
            computed_at TIMESTAMP,
            PRIMARY KEY (type_id, region_id)
        )
        """
    )

    main_tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    if "dim_systems" in main_tables and "dim_regions" in main_tables:
        con.execute(_systems_view_sql())
    if "dim_stargates" in main_tables:
        con.execute(_stargates_view_sql())


def _executemany_if_rows(con: duckdb.DuckDBPyConnection, sql: str, rows: list[tuple]) -> int:
    if not rows:
        return 0
    con.executemany(sql, rows)
    return len(rows)


def ensure_public_database(database_file: str | Path | None = None) -> dict:
    target = Path(database_file) if database_file else get_database_path()
    con = connect(target, read_only=False)
    try:
        _ensure_registry_schema(con)
        _ensure_public_schema(con)
    finally:
        con.close()
    return get_warehouse_status(target)


def reset_public_operational_tables(
    *,
    clear_users: bool = True,
    database_file: str | Path | None = None,
) -> None:
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        con.execute("DELETE FROM market_orders")
        con.execute("DELETE FROM public_contracts")
        con.execute("DELETE FROM market_structures")
        con.execute("DELETE FROM structures")
        if clear_users:
            con.execute("DELETE FROM site_admins")
            con.execute("DELETE FROM users")
    finally:
        con.close()


def retire_legacy_public_database() -> dict:
    removed: list[str] = []
    public_db = get_public_database_path()
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(public_db) + suffix)
        if path.exists():
            path.unlink()
            removed.append(str(path))
    return {"removed": removed, "legacy_database": str(public_db)}


def link_public_user(owner_id: int, character_id: int, database_file: str | Path | None = None) -> None:
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        con.execute(
            "INSERT OR REPLACE INTO users (owner_id, character_id) VALUES (?, ?)",
            [owner_id, character_id],
        )
    finally:
        con.close()


def count_public_owners(database_file: str | Path | None = None) -> int:
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        row = con.execute("SELECT COUNT(DISTINCT owner_id) FROM users").fetchone()
        return int(row[0] or 0)
    finally:
        con.close()


def get_site_admin(owner_id: int, database_file: str | Path | None = None) -> dict | None:
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        return _query_one(
            con,
            """
            SELECT owner_id, is_site_owner, granted_by, granted_at
            FROM site_admins
            WHERE owner_id = ?
            """,
            [owner_id],
        )
    finally:
        con.close()


def upsert_site_admin(
    owner_id: int,
    *,
    is_site_owner: bool = False,
    granted_by: int | None = None,
    granted_at: datetime | None = None,
    database_file: str | Path | None = None,
) -> None:
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        con.execute(
            """
            INSERT OR REPLACE INTO site_admins (owner_id, is_site_owner, granted_by, granted_at)
            VALUES (?, ?, ?, ?)
            """,
            [owner_id, is_site_owner, granted_by, granted_at or _utc_now()],
        )
    finally:
        con.close()


def delete_site_admin(owner_id: int, database_file: str | Path | None = None) -> bool:
    if not get_site_admin(owner_id, database_file):
        return False
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        con.execute("DELETE FROM site_admins WHERE owner_id = ?", [owner_id])
    finally:
        con.close()
    return True


def list_public_users(database_file: str | Path | None = None) -> list[dict]:
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        return _query_to_dicts(
            con,
            """
            SELECT
                u.owner_id,
                COUNT(*) AS character_count,
                a.owner_id IS NOT NULL AS is_admin,
                COALESCE(a.is_site_owner, FALSE) AS is_site_owner,
                a.granted_at
            FROM users AS u
            LEFT JOIN site_admins AS a
              ON a.owner_id = u.owner_id
            GROUP BY u.owner_id, a.owner_id, a.is_site_owner, a.granted_at
            ORDER BY is_site_owner DESC, is_admin DESC, u.owner_id
            """,
        )
    finally:
        con.close()


def public_table_counts(
    table_names: list[str] | None = None,
    database_file: str | Path | None = None,
) -> dict[str, int]:
    names = table_names or [
        "users",
        "site_admins",
        "market_orders",
        "public_contracts",
        "structures",
        "market_structures",
        "systems",
        "stargates",
        "esi_routes",
        "esi_schemas",
    ]
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        counts: dict[str, int] = {}
        for table_name in names:
            try:
                row = con.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()
            except Exception:
                continue
            counts[table_name] = int(row[0] or 0)
        return counts
    finally:
        con.close()


def upsert_market_orders(rows: list[dict], database_file: str | Path | None = None) -> int:
    payload = [
        (
            _as_int(row.get("order_id")),
            _as_int(row.get("type_id")),
            _as_int(row.get("location_id")),
            _as_int(row.get("region_id")),
            _as_bool(row.get("is_buy_order")),
            _coerce_timestamp(row.get("issued")),
            _as_int(row.get("duration")),
            _as_float(row.get("price")),
            row.get("order_range") or row.get("range"),
            _as_int(row.get("volume_remain")),
            _as_int(row.get("volume_total")),
            _as_int(row.get("min_volume")),
            _coerce_timestamp(row.get("last_seen")) or _utc_now(),
        )
        for row in rows
        if row.get("order_id") is not None
    ]
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        return _executemany_if_rows(
            con,
            """
            INSERT OR REPLACE INTO market_orders (
                order_id, type_id, location_id, region_id, is_buy_order, issued, duration,
                price, order_range, volume_remain, volume_total, min_volume, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
    finally:
        con.close()


def upsert_public_contracts(rows: list[dict], database_file: str | Path | None = None) -> int:
    payload = [
        (
            _as_int(row.get("contract_id")),
            _as_int(row.get("region_id")),
            _as_int(row.get("issuer_id")),
            _as_int(row.get("issuer_corporation_id")),
            row.get("contract_type") or row.get("type"),
            _coerce_timestamp(row.get("date_issued")),
            _coerce_timestamp(row.get("date_expired")),
            row.get("title"),
            _as_float(row.get("volume")),
            _as_float(row.get("price")),
            _as_float(row.get("buyout")),
            _as_float(row.get("collateral")),
            _as_float(row.get("reward")),
            _as_int(row.get("days_to_complete")),
            _as_int(row.get("start_location_id")),
            _as_int(row.get("end_location_id")),
            _as_bool(row.get("for_corporation")),
            _coerce_timestamp(row.get("last_seen")) or _utc_now(),
        )
        for row in rows
        if row.get("contract_id") is not None
    ]
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        return _executemany_if_rows(
            con,
            """
            INSERT OR REPLACE INTO public_contracts (
                contract_id, region_id, issuer_id, issuer_corporation_id, contract_type,
                date_issued, date_expired, title, volume, price, buyout, collateral, reward,
                days_to_complete, start_location_id, end_location_id, for_corporation, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
    finally:
        con.close()


def seed_structures(structure_ids: Iterable[int], database_file: str | Path | None = None) -> int:
    requested_ids = sorted({_as_int(value) for value in structure_ids if _as_int(value) is not None})
    if not requested_ids:
        return 0
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        placeholders = ", ".join(["?"] * len(requested_ids))
        existing = {
            int(row[0])
            for row in con.execute(
                f"SELECT structure_id FROM structures WHERE structure_id IN ({placeholders})",
                requested_ids,
            ).fetchall()
        }
        rows = [
            (structure_id, None, None, None, None, None, None, _utc_now())
            for structure_id in requested_ids
            if structure_id not in existing
        ]
        return _executemany_if_rows(
            con,
            """
            INSERT INTO structures (
                structure_id, solar_system_id, region_id, owner_id, name, type_id, position_json, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    finally:
        con.close()


def list_public_structure_ids(
    *,
    missing_name_only: bool = False,
    database_file: str | Path | None = None,
) -> set[int]:
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        sql = "SELECT structure_id FROM structures"
        if missing_name_only:
            sql += (
                " WHERE name IS NULL"
                " AND (forbidden_until IS NULL OR forbidden_until < now())"
                " AND (enrich_refreshed_until IS NULL OR enrich_refreshed_until < now())"
            )
        return {int(row[0]) for row in con.execute(sql).fetchall()}
    finally:
        con.close()


def list_public_structures(
    *,
    skip_market_forbidden: bool = False,
    database_file: str | Path | None = None,
) -> list[dict]:
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        where = (
            "WHERE (market_forbidden_until IS NULL OR market_forbidden_until < now())"
            "  AND (market_refreshed_until IS NULL OR market_refreshed_until < now())"
            if skip_market_forbidden
            else ""
        )
        return _query_to_dicts(
            con,
            f"""
            SELECT structure_id, solar_system_id, region_id, owner_id, name, type_id, position_json, last_seen
            FROM structures
            {where}
            ORDER BY structure_id
            """,
        )
    finally:
        con.close()


def upsert_structures(rows: list[dict], database_file: str | Path | None = None) -> int:
    payload = [
        (
            _as_int(row.get("structure_id")),
            _as_int(row.get("solar_system_id")),
            _as_int(row.get("region_id")),
            _as_int(row.get("owner_id")),
            row.get("name"),
            _as_int(row.get("type_id")),
            _json_or_none(row.get("position_json") if "position_json" in row else row.get("position")),
            _coerce_timestamp(row.get("last_seen")) or _utc_now(),
            _coerce_timestamp(row.get("forbidden_until")),  # NULL clears any prior ban on success
        )
        for row in rows
        if row.get("structure_id") is not None
    ]
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        return _executemany_if_rows(
            con,
            """
            INSERT OR REPLACE INTO structures (
                structure_id, solar_system_id, region_id, owner_id, name, type_id, position_json, last_seen, forbidden_until
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
    finally:
        con.close()


def mark_structures_forbidden(
    structure_ids: list[int],
    cooldown_seconds: int = 21 * 24 * 3600,
    database_file: str | Path | None = None,
) -> None:
    """Record that a batch of structures returned 403/are inaccessible for enrichment.

    Sets forbidden_until = now + cooldown so that list_public_structure_ids
    skips them for the cooldown period.  Only updates rows where name IS NULL
    so successfully-enriched structures are never penalised.
    """
    if not structure_ids:
        return
    from datetime import timedelta
    forbidden_until = _utc_now() + timedelta(seconds=cooldown_seconds)
    placeholders = ", ".join(["?"] * len(structure_ids))
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        con.execute(
            f"UPDATE structures SET forbidden_until = ? WHERE structure_id IN ({placeholders}) AND name IS NULL",
            [forbidden_until, *structure_ids],
        )
    finally:
        con.close()


def mark_structures_enrich_refreshed(
    structure_ids: list[int],
    cooldown_seconds: int = 3600,
    database_file: str | Path | None = None,
) -> None:
    """Record that a batch of structures were successfully enriched with metadata.

    Sets enrich_refreshed_until = now + cooldown so that list_public_structure_ids
    (when called with missing_name_only=True) skips them until the data is stale.
    """
    if not structure_ids:
        return
    from datetime import timedelta
    refreshed_until = _utc_now() + timedelta(seconds=cooldown_seconds)
    placeholders = ", ".join(["?"] * len(structure_ids))
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        con.execute(
            f"UPDATE structures SET enrich_refreshed_until = ? WHERE structure_id IN ({placeholders})",
            [refreshed_until, *structure_ids],
        )
    finally:
        con.close()


def mark_market_structures_forbidden(
    structure_ids: list[int],
    cooldown_seconds: int = 7 * 24 * 3600,
    database_file: str | Path | None = None,
) -> None:
    """Record that a batch of structures returned 403 on the market endpoint.

    Sets market_forbidden_until = now + cooldown so that list_public_structures
    (when called with skip_market_forbidden=True) skips them.
    """
    if not structure_ids:
        return
    from datetime import timedelta
    forbidden_until = _utc_now() + timedelta(seconds=cooldown_seconds)
    placeholders = ", ".join(["?"] * len(structure_ids))
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        con.execute(
            f"UPDATE structures SET market_forbidden_until = ? WHERE structure_id IN ({placeholders})",
            [forbidden_until, *structure_ids],
        )
    finally:
        con.close()


def mark_structures_market_refreshed(
    structure_ids: list[int],
    cooldown_seconds: int = 3600,
    database_file: str | Path | None = None,
) -> None:
    """Record that a batch of structures returned market orders successfully.

    Sets market_refreshed_until = now + cooldown so that list_public_structures
    (when called with skip_market_forbidden=True) skips them until the data is stale.
    """
    if not structure_ids:
        return
    from datetime import timedelta
    refreshed_until = _utc_now() + timedelta(seconds=cooldown_seconds)
    placeholders = ", ".join(["?"] * len(structure_ids))
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        con.execute(
            f"UPDATE structures SET market_refreshed_until = ? WHERE structure_id IN ({placeholders})",
            [refreshed_until, *structure_ids],
        )
    finally:
        con.close()


def list_market_region_ids(
    *,
    skip_recently_refreshed: bool = True,
    database_file: str | Path | None = None,
) -> list[int]:
    """Return region IDs that still need a market refresh.

    Regions recorded in market_region_cooldowns with a future refreshed_until
    are excluded when skip_recently_refreshed=True.
    """
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        if "dim_regions" not in tables:
            return []
        if skip_recently_refreshed:
            rows = con.execute(
                """
                SELECT r.region_id
                FROM dim_regions AS r
                LEFT JOIN market_region_cooldowns AS c ON c.region_id = r.region_id
                WHERE c.region_id IS NULL OR c.refreshed_until < now()
                ORDER BY r.region_id
                """
            ).fetchall()
        else:
            rows = con.execute("SELECT region_id FROM dim_regions ORDER BY region_id").fetchall()
        return [row[0] for row in rows]
    finally:
        con.close()


def mark_region_market_refreshed(
    region_id: int,
    cooldown_seconds: int = 3600,
    database_file: str | Path | None = None,
) -> None:
    """Record that a region's market was successfully fetched; skip it for cooldown_seconds."""
    from datetime import timedelta
    refreshed_until = _utc_now() + timedelta(seconds=cooldown_seconds)
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        con.execute(
            """
            INSERT INTO market_region_cooldowns (region_id, refreshed_until)
            VALUES (?, ?)
            ON CONFLICT (region_id) DO UPDATE SET refreshed_until = excluded.refreshed_until
            """,
            [region_id, refreshed_until],
        )
    finally:
        con.close()


def upsert_market_structures(rows: list[dict], database_file: str | Path | None = None) -> int:
    payload = [
        (
            _as_int(row.get("structure_id")),
            _as_int(row.get("solar_system_id")),
            _as_int(row.get("region_id")),
            _as_int(row.get("owner_id")),
            row.get("name"),
            _as_int(row.get("type_id")),
            _json_or_none(row.get("position_json") if "position_json" in row else row.get("position")),
            _coerce_timestamp(row.get("last_seen")) or _utc_now(),
        )
        for row in rows
        if row.get("structure_id") is not None
    ]
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        return _executemany_if_rows(
            con,
            """
            INSERT OR REPLACE INTO market_structures (
                structure_id, solar_system_id, region_id, owner_id, name, type_id, position_json, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
    finally:
        con.close()


def search_market_orders(
    *,
    type_ids: set[int] | None = None,
    has_type_filter: bool = False,
    region_id: int | None = None,
    location_id: int | None = None,
    is_buy: int | None = None,
    sort_by: str = "price",
    page: int = 1,
    page_size: int = 50,
    database_file: str | Path | None = None,
) -> tuple[int, list[dict]]:
    where: list[str] = []
    params: list[Any] = []
    if type_ids:
        ordered = sorted(type_ids)
        where.append(f"type_id IN ({', '.join(['?'] * len(ordered))})")
        params.extend(ordered)
    elif has_type_filter:
        where.append("1 = 0")

    if region_id:
        where.append("region_id = ?")
        params.append(region_id)
    if location_id:
        where.append("location_id = ?")
        params.append(location_id)
    if is_buy in (0, 1):
        where.append("is_buy_order = ?")
        params.append(bool(is_buy))

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    order_sql = "volume_remain DESC, price ASC" if sort_by == "volume" else "price ASC, volume_remain DESC"
    offset = max(page - 1, 0) * page_size

    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        total_row = con.execute(
            f"SELECT COUNT(*) FROM market_orders {where_sql}",
            params,
        ).fetchone()
        rows = _query_to_dicts(
            con,
            f"""
            SELECT
                order_id, type_id, location_id, region_id, is_buy_order, issued,
                duration, price, order_range, volume_remain, volume_total, min_volume, last_seen
            FROM market_orders
            {where_sql}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        )
        return int(total_row[0] or 0), rows
    finally:
        con.close()


def sync_esi_registry_to_warehouse(
    *,
    compatibility_date: str | None = None,
    registry_root: str | Path | None = None,
    database_file: str | Path | None = None,
) -> dict:
    from esi import spec_registry as esi_spec_registry

    status = esi_spec_registry.get_registry_status()
    if not status.get("available"):
        raise FileNotFoundError("No ESI registry is available to sync into DuckDB.")

    active_date = compatibility_date or status.get("compatibility_date")
    if not active_date:
        raise RuntimeError("Unable to determine the active ESI compatibility date.")

    paths = esi_spec_registry.get_registry_paths(active_date)
    if registry_root:
        root = Path(registry_root)
        paths = {
            **paths,
            "root": root,
            "target_dir": root / active_date,
            "openapi_json": root / active_date / "openapi.json",
            "routes_json": root / active_date / "routes.json",
            "scopes_json": root / active_date / "scopes.json",
            "schemas_json": root / active_date / "schemas.json",
            "agents_md": root / active_date / "AGENTS.md",
            "latest_json": root / "latest.json",
        }

    routes = json.loads(paths["routes_json"].read_text(encoding="utf-8"))
    scopes = json.loads(paths["scopes_json"].read_text(encoding="utf-8"))
    schemas = json.loads(paths["schemas_json"].read_text(encoding="utf-8"))
    route_rows = [
        (
            active_date,
            route.get("route_key") or f"{route.get('method')} {route.get('path')}",
            route.get("method"),
            route.get("path"),
            route.get("operation_id"),
            route.get("summary"),
            route.get("description"),
            _to_json(route.get("tags") or []),
            route.get("compatibility_date"),
            route.get("cache_age"),
            route.get("cache_mode"),
            ((route.get("pagination") or {}).get("mode")),
            ((route.get("pagination") or {}).get("has_page_param", False)),
            _to_json(route.get("required_roles") or []),
            _to_json(route.get("rate_limit")),
            _to_json(route.get("scopes") or []),
            _to_json(route.get("security") or []),
            _to_json(route.get("parameters") or []),
            bool(route.get("requires_auth")),
            route.get("queue_channel") or "public",
            _to_json(route.get("request_body_schema_refs") or []),
            _to_json(route.get("response_schema_refs") or {}),
        )
        for route in routes
    ]
    parameter_rows = [
        (
            active_date,
            route.get("route_key") or f"{route.get('method')} {route.get('path')}",
            param.get("name"),
            param.get("in"),
            bool(param.get("required")),
            _to_json(param.get("schema")),
        )
        for route in routes
        for param in (route.get("parameters") or [])
    ]
    route_schema_rows = [
        row
        for route in routes
        for row in (
            [
                (
                    active_date,
                    route.get("route_key") or f"{route.get('method')} {route.get('path')}",
                    "request",
                    None,
                    schema_name,
                )
                for schema_name in (route.get("request_body_schema_refs") or [])
            ]
            + [
                (
                    active_date,
                    route.get("route_key") or f"{route.get('method')} {route.get('path')}",
                    "response",
                    str(status_code),
                    schema_name,
                )
                for status_code, schema_names in (route.get("response_schema_refs") or {}).items()
                for schema_name in schema_names
            ]
        )
    ]
    schema_rows = [
        (active_date, schema_name, _to_json(payload))
        for schema_name, payload in schemas.items()
    ]
    scope_rows = [
        (active_date, scope_name, _to_json(entries))
        for scope_name, entries in scopes.items()
    ]

    target = Path(database_file) if database_file else get_database_path()
    con = connect(target, read_only=False)
    try:
        _ensure_registry_schema(con)
        con.execute("DELETE FROM esi_route_parameters WHERE compatibility_date = ?", [active_date])
        con.execute("DELETE FROM esi_route_schema_refs WHERE compatibility_date = ?", [active_date])
        con.execute("DELETE FROM esi_routes WHERE compatibility_date = ?", [active_date])
        con.execute("DELETE FROM esi_schemas WHERE compatibility_date = ?", [active_date])
        con.execute("DELETE FROM esi_scopes WHERE compatibility_date = ?", [active_date])
        con.execute("DELETE FROM esi_registry_manifest WHERE compatibility_date = ?", [active_date])

        if route_rows:
            con.executemany(
                """
                INSERT INTO esi_routes (
                    compatibility_date, route_key, method, path, operation_id, summary, description,
                    tags_json, compatibility_date_override, cache_age, cache_mode, pagination_mode,
                    has_page_param, required_roles_json, rate_limit_json, scopes_json, security_json,
                    parameters_json, requires_auth, queue_channel,
                    request_body_schema_refs_json, response_schema_refs_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                route_rows,
            )

        if parameter_rows:
            con.executemany(
                """
                INSERT INTO esi_route_parameters (
                    compatibility_date, route_key, parameter_name, parameter_in, required, schema_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                parameter_rows,
            )

        if route_schema_rows:
            con.executemany(
                """
                INSERT INTO esi_route_schema_refs (
                    compatibility_date, route_key, direction, status_code, schema_name
                ) VALUES (?, ?, ?, ?, ?)
                """,
                route_schema_rows,
            )

        if schema_rows:
            con.executemany(
                "INSERT INTO esi_schemas (compatibility_date, schema_name, payload_json) VALUES (?, ?, ?)",
                schema_rows,
            )
        if scope_rows:
            con.executemany(
                "INSERT INTO esi_scopes (compatibility_date, scope_name, routes_json) VALUES (?, ?, ?)",
                scope_rows,
            )
        con.execute(
            """
            INSERT INTO esi_registry_manifest (
                compatibility_date, generated_at, routes_path, scopes_path, schemas_path,
                latest_pointer, route_count, scope_count, schema_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                active_date,
                datetime.fromisoformat(str(status["generated_at"]).replace("Z", "+00:00")),
                str(paths["routes_json"]),
                str(paths["scopes_json"]),
                str(paths["schemas_json"]),
                str(paths["latest_json"]),
                len(routes),
                len(scopes),
                len(schemas),
            ],
        )
    finally:
        con.close()

    logger.info("Synced ESI registry %s into DuckDB warehouse %s", active_date, target)
    return {
        "compatibility_date": active_date,
        "route_count": len(routes),
        "scope_count": len(scopes),
        "schema_count": len(schemas),
        "database_file": str(target),
    }


def ensure_esi_registry_current(database_file: str | Path | None = None) -> dict | None:
    from esi import spec_registry as esi_spec_registry

    registry_status = esi_spec_registry.get_registry_status()
    if not registry_status.get("available"):
        return None

    warehouse_status = get_warehouse_status(database_file)
    existing = warehouse_status.get("esi_registry") or {}
    if (
        existing.get("compatibility_date") == registry_status.get("compatibility_date")
        and int(existing.get("route_count") or 0) == int(registry_status.get("route_count") or 0)
        and int(existing.get("schema_count") or 0) == int(registry_status.get("schema_count") or 0)
    ):
        return existing

    return sync_esi_registry_to_warehouse(
        compatibility_date=registry_status.get("compatibility_date"),
        database_file=database_file,
    )


def _create_browser_views(con: duckdb.DuckDBPyConnection) -> None:
    available_main_tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    if "systems" not in available_main_tables and "dim_systems" in available_main_tables and "dim_regions" in available_main_tables:
        con.execute(_systems_view_sql(temporary=True))
    if "stargates" not in available_main_tables and "dim_stargates" in available_main_tables:
        con.execute(_stargates_view_sql(temporary=True))


def connect_browser_workspace(
    database_file: str | Path | None = None,
    *,
    read_only: bool = True,
) -> duckdb.DuckDBPyConnection:
    target = Path(database_file) if database_file else get_database_path()
    if target.exists():
        con = connect(target, read_only=read_only)
    else:
        con = duckdb.connect(":memory:")
        con.execute("PRAGMA threads=4")
    _create_browser_views(con)
    return con


def list_browser_tables(database_file: str | Path | None = None) -> dict[str, list[str]]:
    con = connect_browser_workspace(database_file, read_only=True)
    try:
        rows = con.execute("SHOW ALL TABLES").fetchall()
        tables: dict[str, list[str]] = {}
        for database_name, _schema_name, table_name, columns, _types, _temporary in rows:
            if database_name == "live_public":
                continue
            tables[table_name] = list(columns)
        return dict(sorted(tables.items()))
    finally:
        con.close()


def _validate_browser_sql(raw_sql: str) -> str:
    sql = raw_sql.strip()
    if not sql:
        raise ValueError("No SQL provided.")
    sql_no_trailing = sql.rstrip().rstrip(";").rstrip()
    if ";" in sql_no_trailing:
        raise ValueError("Only a single read-only statement is allowed.")
    normalized = sql_no_trailing.lstrip().upper()
    if not normalized.startswith(_BROWSER_ALLOWED_PREFIXES):
        raise ValueError("Only SELECT, WITH, PRAGMA, SHOW, and DESCRIBE statements are allowed.")
    return sql_no_trailing


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date, time_value)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def query_browser_sql(
    raw_sql: str,
    *,
    row_limit: int = 500,
    database_file: str | Path | None = None,
) -> dict:
    sql = _validate_browser_sql(raw_sql)
    con = connect_browser_workspace(database_file, read_only=True)
    try:
        result = con.execute(sql)
        columns = [desc[0] for desc in result.description] if result.description else []
        rows = [
            {columns[index]: _json_safe(value) for index, value in enumerate(row)}
            for row in result.fetchmany(row_limit)
        ]
        return {"columns": columns, "rows": rows}
    finally:
        con.close()


def _connect_private_browser(owner_id: int) -> sqlite3.Connection:
    target = get_private_database_path(owner_id)
    if not target.exists():
        raise FileNotFoundError(f"Private database not found for owner {owner_id}: {target}")
    con = sqlite3.connect(
        f"file:{target.as_posix()}?mode=ro",
        uri=True,
        timeout=30,
        check_same_thread=False,
    )
    con.row_factory = sqlite3.Row
    return con


def list_private_browser_tables(owner_id: int) -> dict[str, list[str]]:
    con = _connect_private_browser(owner_id)
    try:
        rows = con.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        tables: dict[str, list[str]] = {}
        for row in rows:
            table_name = str(row["name"])
            column_rows = con.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            tables[table_name] = [str(col["name"]) for col in column_rows]
        return tables
    finally:
        con.close()


def query_private_browser_sql(
    owner_id: int,
    raw_sql: str,
    *,
    row_limit: int = 500,
) -> dict:
    sql = _validate_browser_sql(raw_sql)
    con = _connect_private_browser(owner_id)
    try:
        cursor = con.execute(sql)
        columns = [desc[0] for desc in (cursor.description or [])]
        rows = [
            {columns[index]: _json_safe(value) for index, value in enumerate(row)}
            for row in cursor.fetchmany(row_limit)
        ]
        return {"columns": columns, "rows": rows}
    finally:
        con.close()


def get_warehouse_status(database_file: str | Path | None = None) -> dict:
    target = Path(database_file) if database_file else get_database_path()
    status = {
        "available": target.exists(),
        "database_file": str(target),
        "initialized": False,
    }
    if not target.exists():
        return status

    status["file_size_bytes"] = target.stat().st_size
    try:
        con = connect(target, read_only=True)
        try:
            tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
            status["tables"] = sorted(tables)
            if "sde_manifest" not in tables:
                status["note"] = "DuckDB file exists but the SDE warehouse has not been built yet."
                return status
            manifest = _query_one(
                con,
                """
                SELECT
                    build_started_at,
                    build_finished_at,
                    sde_version,
                    source_hash,
                    source_root,
                    source_zip_path,
                    source_etag,
                    source_last_modified,
                    supported_languages_json,
                    fsd_file_count,
                    bsd_file_count,
                    universe_region_count,
                    universe_constellation_count,
                    universe_system_count,
                    warehouse_file
                FROM sde_manifest
                ORDER BY build_finished_at DESC
                LIMIT 1
                """,
            )
            datasets = _query_to_dicts(
                con,
                """
                SELECT layer, dataset_name, table_name, source_path, row_count
                FROM sde_dataset_manifest
                ORDER BY layer, dataset_name
                """,
            )
            try:
                registry = _query_one(
                    con,
                    """
                    SELECT compatibility_date, generated_at, route_count, scope_count, schema_count
                    FROM esi_registry_manifest
                    ORDER BY generated_at DESC
                    LIMIT 1
                    """,
                )
            except Exception:
                registry = None
            status["manifest"] = manifest or {}
            status["datasets"] = datasets
            status["esi_registry"] = registry or {}
            if manifest and manifest.get("supported_languages_json"):
                try:
                    status["supported_languages"] = json.loads(manifest["supported_languages_json"])
                except json.JSONDecodeError:
                    status["supported_languages"] = []
            status["initialized"] = bool(manifest)
        finally:
            con.close()
    except Exception as exc:
        logger.warning("Failed to read SDE warehouse status from %s: %s", target, exc)
        status["error"] = str(exc)
    return status
