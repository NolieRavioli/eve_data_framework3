import csv
import hashlib
import json
import logging
import os
import re
import sqlite3
import sys
import tempfile
import time
from datetime import date, datetime, time as time_value, timezone
from pathlib import Path
from typing import Any, Iterable

import duckdb
import yaml

logger = logging.getLogger(__name__)

RAW_BATCH_SIZE = 1000
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
_LAST_PROGRESS_LENGTH = 0


def _yaml_loader():
    return getattr(yaml, "CLoader", yaml.SafeLoader)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _progress_print(message: str, *, final: bool = False) -> None:
    global _LAST_PROGRESS_LENGTH
    text = str(message)
    padding = " " * max(0, _LAST_PROGRESS_LENGTH - len(text))
    sys.stdout.write(f"\r{text}{padding}")
    if final:
        sys.stdout.write("\n")
        _LAST_PROGRESS_LENGTH = 0
    else:
        _LAST_PROGRESS_LENGTH = len(text)
    sys.stdout.flush()


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


def _xyz(values: Any) -> tuple[float | None, float | None, float | None]:
    if isinstance(values, (list, tuple)) and len(values) == 3:
        return (_as_float(values[0]), _as_float(values[1]), _as_float(values[2]))
    if isinstance(values, dict):
        return (_as_float(values.get("x")), _as_float(values.get("y")), _as_float(values.get("z")))
    return (None, None, None)


def _best_row_key(index: int, value: Any) -> str:
    if isinstance(value, dict):
        for preferred in (
            "itemID",
            "stationID",
            "typeID",
            "blueprintTypeID",
            "marketGroupID",
            "groupID",
            "categoryID",
            "iconID",
            "graphicID",
            "flagID",
            "raceID",
            "bloodlineID",
            "factionID",
        ):
            if preferred in value:
                return str(value[preferred])
        for key, item in value.items():
            if key.lower().endswith("id") and isinstance(item, (int, str)):
                return str(item)
    return str(index)


def _sanitize_table_name(prefix: str, stem: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_").lower()
    return f"{prefix}_{safe}"


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


def compute_file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_source_tree_hash(source_root: str | Path) -> str:
    digest = hashlib.sha256()
    root = Path(source_root)
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(str(stat.st_size).encode("utf-8"))
        digest.update(str(stat.st_mtime_ns).encode("utf-8"))
    return digest.hexdigest()


def _load_yaml_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.load(handle, Loader=_yaml_loader())


def _insert_batches(con: duckdb.DuckDBPyConnection, sql: str, rows: Iterable[tuple], batch_size: int = RAW_BATCH_SIZE) -> int:
    batch: list[tuple] = []
    total = 0
    for row in rows:
        batch.append(row)
        if len(batch) >= batch_size:
            con.executemany(sql, batch)
            total += len(batch)
            batch.clear()
    if batch:
        con.executemany(sql, batch)
        total += len(batch)
    return total


def _copy_rows(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    columns: list[str],
    rows: Iterable[tuple],
    directory: str | Path | None = None,
) -> int:
    total = 0
    temp_dir = Path(directory) if directory else get_public_data_dir()
    temp_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        suffix=".tsv",
        prefix=f"{table_name}_",
        dir=temp_dir,
        delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        for row in rows:
            writer.writerow(["\\N" if value is None else value for value in row])
            total += 1
    try:
        joined_columns = ", ".join(f'"{column}"' for column in columns)
        escaped_path = str(temp_path).replace("\\", "\\\\").replace("'", "''")
        con.execute(
            f"""
            COPY "{table_name}" ({joined_columns})
            FROM '{escaped_path}'
            (DELIMITER '\t', NULL '\\N', QUOTE '"', ESCAPE '"')
            """
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return total


def _iter_raw_rows(data: Any) -> Iterable[tuple[str, str]]:
    if isinstance(data, dict):
        for key, value in data.items():
            yield str(key), _to_json(value)
        return
    if isinstance(data, list):
        for index, value in enumerate(data):
            yield _best_row_key(index, value), _to_json(value)
        return
    yield "0", _to_json(data)


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
            last_seen TIMESTAMP
        )
        """
    )
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

    main_tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    if "dim_systems" in main_tables and "dim_regions" in main_tables:
        con.execute(_systems_view_sql())
    if "dim_stargates" in main_tables:
        con.execute(_stargates_view_sql())


def _bootstrap_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE sde_manifest (
            manifest_id INTEGER,
            build_started_at TIMESTAMP,
            build_finished_at TIMESTAMP,
            sde_version VARCHAR,
            source_hash VARCHAR,
            source_root VARCHAR,
            source_zip_path VARCHAR,
            source_etag VARCHAR,
            source_last_modified VARCHAR,
            supported_languages_json VARCHAR,
            fsd_file_count BIGINT,
            bsd_file_count BIGINT,
            universe_region_count BIGINT,
            universe_constellation_count BIGINT,
            universe_system_count BIGINT,
            warehouse_file VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE sde_dataset_manifest (
            layer VARCHAR,
            dataset_name VARCHAR,
            table_name VARCHAR,
            source_path VARCHAR,
            row_count BIGINT
        )
        """
    )
    _ensure_registry_schema(con)
    con.execute(
        """
        CREATE TABLE dim_types (
            type_id BIGINT PRIMARY KEY,
            group_id BIGINT,
            market_group_id BIGINT,
            published BOOLEAN,
            name_en VARCHAR,
            mass DOUBLE,
            volume DOUBLE,
            capacity DOUBLE,
            portion_size BIGINT,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE dim_groups (
            group_id BIGINT PRIMARY KEY,
            category_id BIGINT,
            published BOOLEAN,
            name_en VARCHAR,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE dim_categories (
            category_id BIGINT PRIMARY KEY,
            published BOOLEAN,
            name_en VARCHAR,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE dim_market_groups (
            market_group_id BIGINT PRIMARY KEY,
            parent_group_id BIGINT,
            icon_id BIGINT,
            has_types BOOLEAN,
            name_en VARCHAR,
            description_en VARCHAR,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE fact_blueprints (
            blueprint_type_id BIGINT PRIMARY KEY,
            max_production_limit BIGINT,
            manufacturing_time BIGINT,
            other_activities_json VARCHAR,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE fact_blueprint_materials (
            blueprint_type_id BIGINT,
            activity VARCHAR,
            material_type_id BIGINT,
            quantity BIGINT,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE fact_blueprint_products (
            blueprint_type_id BIGINT,
            activity VARCHAR,
            product_type_id BIGINT,
            quantity BIGINT,
            probability DOUBLE,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE fact_type_materials (
            type_id BIGINT,
            material_type_id BIGINT,
            quantity BIGINT,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE fact_type_dogma_attributes (
            type_id BIGINT,
            attribute_id BIGINT,
            value DOUBLE,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE fact_type_dogma_effects (
            type_id BIGINT,
            effect_id BIGINT,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE dim_stations (
            station_id BIGINT PRIMARY KEY,
            station_name VARCHAR,
            station_type_id BIGINT,
            corporation_id BIGINT,
            operation_id BIGINT,
            solar_system_id BIGINT,
            constellation_id BIGINT,
            region_id BIGINT,
            security DOUBLE,
            x DOUBLE,
            y DOUBLE,
            z DOUBLE,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE dim_inv_items (
            item_id BIGINT PRIMARY KEY,
            type_id BIGINT,
            location_id BIGINT,
            owner_id BIGINT,
            flag_id BIGINT,
            quantity BIGINT,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE dim_inv_names (
            item_id BIGINT PRIMARY KEY,
            item_name VARCHAR,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE dim_inv_positions (
            item_id BIGINT PRIMARY KEY,
            x DOUBLE,
            y DOUBLE,
            z DOUBLE,
            yaw DOUBLE,
            pitch DOUBLE,
            roll DOUBLE,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE dim_regions (
            region_id BIGINT PRIMARY KEY,
            region_name VARCHAR,
            faction_id BIGINT,
            x DOUBLE,
            y DOUBLE,
            z DOUBLE,
            x_min DOUBLE,
            y_min DOUBLE,
            z_min DOUBLE,
            x_max DOUBLE,
            y_max DOUBLE,
            z_max DOUBLE,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE dim_constellations (
            constellation_id BIGINT PRIMARY KEY,
            constellation_name VARCHAR,
            region_id BIGINT,
            x DOUBLE,
            y DOUBLE,
            z DOUBLE,
            x_min DOUBLE,
            y_min DOUBLE,
            z_min DOUBLE,
            x_max DOUBLE,
            y_max DOUBLE,
            z_max DOUBLE,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE dim_systems (
            system_id BIGINT PRIMARY KEY,
            system_name VARCHAR,
            constellation_id BIGINT,
            region_id BIGINT,
            security DOUBLE,
            sun_type_id BIGINT,
            border BOOLEAN,
            corridor BOOLEAN,
            fringe BOOLEAN,
            hub BOOLEAN,
            international BOOLEAN,
            regional BOOLEAN,
            planet_count BIGINT,
            stargate_count BIGINT,
            x DOUBLE,
            y DOUBLE,
            z DOUBLE,
            x_min DOUBLE,
            y_min DOUBLE,
            z_min DOUBLE,
            x_max DOUBLE,
            y_max DOUBLE,
            z_max DOUBLE,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE dim_stargates (
            stargate_id BIGINT PRIMARY KEY,
            system_id BIGINT,
            destination_stargate_id BIGINT,
            destination_system_id BIGINT,
            type_id BIGINT,
            x DOUBLE,
            y DOUBLE,
            z DOUBLE,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE dim_planets (
            planet_id BIGINT PRIMARY KEY,
            system_id BIGINT,
            constellation_id BIGINT,
            region_id BIGINT,
            celestial_index BIGINT,
            type_id BIGINT,
            x DOUBLE,
            y DOUBLE,
            z DOUBLE,
            radius DOUBLE,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE dim_moons (
            moon_id BIGINT PRIMARY KEY,
            planet_id BIGINT,
            system_id BIGINT,
            type_id BIGINT,
            x DOUBLE,
            y DOUBLE,
            z DOUBLE,
            radius DOUBLE,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE dim_asteroid_belts (
            asteroid_belt_id BIGINT PRIMARY KEY,
            planet_id BIGINT,
            system_id BIGINT,
            x DOUBLE,
            y DOUBLE,
            z DOUBLE,
            payload_json VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE dim_stars (
            star_id BIGINT PRIMARY KEY,
            system_id BIGINT,
            type_id BIGINT,
            radius DOUBLE,
            x DOUBLE,
            y DOUBLE,
            z DOUBLE,
            payload_json VARCHAR
        )
        """
    )
    _ensure_public_schema(con)


def _record_dataset(stats: list[dict], layer: str, dataset_name: str, table_name: str, source_path: str | None, row_count: int) -> None:
    stats.append(
        {
            "layer": layer,
            "dataset_name": dataset_name,
            "table_name": table_name,
            "source_path": source_path or "",
            "row_count": int(row_count),
        }
    )


def _build_raw_table(
    con: duckdb.DuckDBPyConnection,
    layer: str,
    path: Path,
    data: Any,
    sde_version: str,
) -> tuple[str, int]:
    table_name = _sanitize_table_name(f"raw_{layer}", path.stem)
    con.execute(
        f"""
        CREATE TABLE "{table_name}" (
            row_key VARCHAR,
            payload_json VARCHAR,
            sde_version VARCHAR,
            source_path VARCHAR
        )
        """
    )
    row_count = _copy_rows(
        con,
        table_name,
        ["row_key", "payload_json", "sde_version", "source_path"],
        ((row_key, payload_json, sde_version, str(path)) for row_key, payload_json in _iter_raw_rows(data)),
        directory=path.parent,
    )
    return table_name, row_count


def _insert_dim_types(con: duckdb.DuckDBPyConnection, data: dict) -> int:
    return _copy_rows(
        con,
        "dim_types",
        ["type_id", "group_id", "market_group_id", "published", "name_en", "mass", "volume", "capacity", "portion_size", "payload_json"],
        (
            (
                _as_int(type_id),
                _as_int(props.get("groupID")),
                _as_int(props.get("marketGroupID")),
                _as_bool(props.get("published")),
                ((props.get("name") or {}).get("en") if isinstance(props.get("name"), dict) else None),
                _as_float(props.get("mass")),
                _as_float(props.get("volume")),
                _as_float(props.get("capacity")),
                _as_int(props.get("portionSize")),
                _to_json(props),
            )
            for type_id, props in data.items()
        ),
    )


def _insert_dim_groups(con: duckdb.DuckDBPyConnection, data: dict) -> int:
    return _copy_rows(
        con,
        "dim_groups",
        ["group_id", "category_id", "published", "name_en", "payload_json"],
        (
            (
                _as_int(group_id),
                _as_int(props.get("categoryID")),
                _as_bool(props.get("published")),
                ((props.get("name") or {}).get("en") if isinstance(props.get("name"), dict) else None),
                _to_json(props),
            )
            for group_id, props in data.items()
        ),
    )


def _insert_dim_categories(con: duckdb.DuckDBPyConnection, data: dict) -> int:
    return _copy_rows(
        con,
        "dim_categories",
        ["category_id", "published", "name_en", "payload_json"],
        (
            (
                _as_int(category_id),
                _as_bool(props.get("published")),
                ((props.get("name") or {}).get("en") if isinstance(props.get("name"), dict) else None),
                _to_json(props),
            )
            for category_id, props in data.items()
        ),
    )


def _insert_dim_market_groups(con: duckdb.DuckDBPyConnection, data: dict) -> int:
    return _copy_rows(
        con,
        "dim_market_groups",
        ["market_group_id", "parent_group_id", "icon_id", "has_types", "name_en", "description_en", "payload_json"],
        (
            (
                _as_int(group_id),
                _as_int(props.get("parentGroupID")),
                _as_int(props.get("iconID")),
                _as_bool(props.get("hasTypes")),
                ((props.get("nameID") or {}).get("en") if isinstance(props.get("nameID"), dict) else None),
                ((props.get("descriptionID") or {}).get("en") if isinstance(props.get("descriptionID"), dict) else None),
                _to_json(props),
            )
            for group_id, props in data.items()
        ),
    )


def _insert_fact_blueprints(con: duckdb.DuckDBPyConnection, data: dict) -> tuple[int, int, int]:
    blueprint_rows = []
    material_rows = []
    product_rows = []
    for blueprint_type_id, props in data.items():
        activities = props.get("activities") or {}
        manufacturing = activities.get("manufacturing") or {}
        other_activities = {key: value for key, value in activities.items() if key != "manufacturing"}
        blueprint_rows.append(
            (
                _as_int(blueprint_type_id),
                _as_int(props.get("maxProductionLimit")),
                _as_int(manufacturing.get("time")),
                _to_json(other_activities),
                _to_json(props),
            )
        )
        for activity_name, activity in activities.items():
            for material in activity.get("materials", []) or []:
                material_rows.append(
                    (
                        _as_int(blueprint_type_id),
                        activity_name,
                        _as_int(material.get("typeID")),
                        _as_int(material.get("quantity")),
                        _to_json(material),
                    )
                )
            for product in activity.get("products", []) or []:
                product_rows.append(
                    (
                        _as_int(blueprint_type_id),
                        activity_name,
                        _as_int(product.get("typeID")),
                        _as_int(product.get("quantity")),
                        _as_float(product.get("probability")),
                        _to_json(product),
                    )
                )
    count_blueprints = _copy_rows(
        con,
        "fact_blueprints",
        ["blueprint_type_id", "max_production_limit", "manufacturing_time", "other_activities_json", "payload_json"],
        blueprint_rows,
    )
    count_materials = _copy_rows(
        con,
        "fact_blueprint_materials",
        ["blueprint_type_id", "activity", "material_type_id", "quantity", "payload_json"],
        material_rows,
    )
    count_products = _copy_rows(
        con,
        "fact_blueprint_products",
        ["blueprint_type_id", "activity", "product_type_id", "quantity", "probability", "payload_json"],
        product_rows,
    )
    return count_blueprints, count_materials, count_products


def _insert_fact_type_materials(con: duckdb.DuckDBPyConnection, data: dict) -> int:
    return _copy_rows(
        con,
        "fact_type_materials",
        ["type_id", "material_type_id", "quantity", "payload_json"],
        (
            (
                _as_int(type_id),
                _as_int(material.get("materialTypeID")),
                _as_int(material.get("quantity")),
                _to_json(material),
            )
            for type_id, props in data.items()
            for material in (props.get("materials") or [])
        ),
    )


def _insert_fact_type_dogma(con: duckdb.DuckDBPyConnection, data: dict) -> tuple[int, int]:
    attr_rows = []
    effect_rows = []
    for type_id, props in data.items():
        for attribute in props.get("dogmaAttributes", []) or []:
            attr_rows.append(
                (
                    _as_int(type_id),
                    _as_int(attribute.get("attributeID")),
                    _as_float(attribute.get("value")),
                    _to_json(attribute),
                )
            )
        for effect in props.get("dogmaEffects", []) or []:
            effect_rows.append(
                (
                    _as_int(type_id),
                    _as_int(effect.get("effectID")),
                    _to_json(effect),
                )
            )
    count_attrs = _copy_rows(
        con,
        "fact_type_dogma_attributes",
        ["type_id", "attribute_id", "value", "payload_json"],
        attr_rows,
    )
    count_effects = _copy_rows(
        con,
        "fact_type_dogma_effects",
        ["type_id", "effect_id", "payload_json"],
        effect_rows,
    )
    return count_attrs, count_effects


def _insert_dim_stations(con: duckdb.DuckDBPyConnection, data: list[dict]) -> int:
    return _copy_rows(
        con,
        "dim_stations",
        [
            "station_id",
            "station_name",
            "station_type_id",
            "corporation_id",
            "operation_id",
            "solar_system_id",
            "constellation_id",
            "region_id",
            "security",
            "x",
            "y",
            "z",
            "payload_json",
        ],
        (
            (
                _as_int(row.get("stationID")),
                row.get("stationName"),
                _as_int(row.get("stationTypeID")),
                _as_int(row.get("corporationID")),
                _as_int(row.get("operationID")),
                _as_int(row.get("solarSystemID")),
                _as_int(row.get("constellationID")),
                _as_int(row.get("regionID")),
                _as_float(row.get("security")),
                _as_float(row.get("x")),
                _as_float(row.get("y")),
                _as_float(row.get("z")),
                _to_json(row),
            )
            for row in data
        ),
    )


def _insert_dim_inv_items(con: duckdb.DuckDBPyConnection, data: list[dict]) -> int:
    return _copy_rows(
        con,
        "dim_inv_items",
        ["item_id", "type_id", "location_id", "owner_id", "flag_id", "quantity", "payload_json"],
        (
            (
                _as_int(row.get("itemID")),
                _as_int(row.get("typeID")),
                _as_int(row.get("locationID")),
                _as_int(row.get("ownerID")),
                _as_int(row.get("flagID")),
                _as_int(row.get("quantity")),
                _to_json(row),
            )
            for row in data
        ),
    )


def _insert_dim_inv_names(con: duckdb.DuckDBPyConnection, data: list[dict]) -> int:
    return _copy_rows(
        con,
        "dim_inv_names",
        ["item_id", "item_name", "payload_json"],
        (
            (
                _as_int(row.get("itemID")),
                row.get("itemName"),
                _to_json(row),
            )
            for row in data
        ),
    )


def _insert_dim_inv_positions(con: duckdb.DuckDBPyConnection, data: list[dict]) -> int:
    return _copy_rows(
        con,
        "dim_inv_positions",
        ["item_id", "x", "y", "z", "yaw", "pitch", "roll", "payload_json"],
        (
            (
                _as_int(row.get("itemID")),
                _as_float(row.get("x")),
                _as_float(row.get("y")),
                _as_float(row.get("z")),
                _as_float(row.get("yaw")),
                _as_float(row.get("pitch")),
                _as_float(row.get("roll")),
                _to_json(row),
            )
            for row in data
        ),
    )


def _insert_universe(con: duckdb.DuckDBPyConnection, universe_root: Path) -> dict[str, int]:
    region_rows: list[tuple] = []
    constellation_rows: list[tuple] = []
    system_rows: list[tuple] = []
    stargate_rows: list[list[Any]] = []
    planet_rows: list[tuple] = []
    moon_rows: list[tuple] = []
    belt_rows: list[tuple] = []
    star_rows: list[tuple] = []

    region_dir_to_id: dict[Path, int] = {}
    constellation_dir_to_id: dict[Path, int] = {}
    gate_to_system: dict[int, int] = {}

    for region_path in sorted(universe_root.rglob("region.yaml")):
        data = _load_yaml_file(region_path) or {}
        region_dir = region_path.parent
        region_id = _as_int(data.get("regionID"))
        region_dir_to_id[region_dir] = region_id or 0
        x, y, z = _xyz(data.get("center"))
        x_min, y_min, z_min = _xyz(data.get("min"))
        x_max, y_max, z_max = _xyz(data.get("max"))
        region_rows.append(
            (
                region_id,
                region_dir.name,
                _as_int(data.get("factionID")),
                x,
                y,
                z,
                x_min,
                y_min,
                z_min,
                x_max,
                y_max,
                z_max,
                _to_json(data),
            )
        )

    for constellation_path in sorted(universe_root.rglob("constellation.yaml")):
        data = _load_yaml_file(constellation_path) or {}
        constellation_dir = constellation_path.parent
        region_dir = constellation_dir.parent
        constellation_id = _as_int(data.get("constellationID"))
        constellation_dir_to_id[constellation_dir] = constellation_id or 0
        x, y, z = _xyz(data.get("center"))
        x_min, y_min, z_min = _xyz(data.get("min"))
        x_max, y_max, z_max = _xyz(data.get("max"))
        constellation_rows.append(
            (
                constellation_id,
                constellation_dir.name,
                region_dir_to_id.get(region_dir),
                x,
                y,
                z,
                x_min,
                y_min,
                z_min,
                x_max,
                y_max,
                z_max,
                _to_json(data),
            )
        )

    for system_path in sorted(universe_root.rglob("solarsystem.yaml")):
        data = _load_yaml_file(system_path) or {}
        system_dir = system_path.parent
        constellation_dir = system_dir.parent
        region_dir = constellation_dir.parent
        system_id = _as_int(data.get("solarSystemID"))
        constellation_id = constellation_dir_to_id.get(constellation_dir)
        region_id = region_dir_to_id.get(region_dir)
        planets = data.get("planets") or {}
        stargates = data.get("stargates") or {}
        x, y, z = _xyz(data.get("center"))
        x_min, y_min, z_min = _xyz(data.get("min"))
        x_max, y_max, z_max = _xyz(data.get("max"))
        system_rows.append(
            (
                system_id,
                system_dir.name,
                constellation_id,
                region_id,
                _as_float(data.get("security")),
                _as_int(data.get("sunTypeID")),
                _as_bool(data.get("border")),
                _as_bool(data.get("corridor")),
                _as_bool(data.get("fringe")),
                _as_bool(data.get("hub")),
                _as_bool(data.get("international")),
                _as_bool(data.get("regional")),
                len(planets),
                len(stargates),
                x,
                y,
                z,
                x_min,
                y_min,
                z_min,
                x_max,
                y_max,
                z_max,
                _to_json(data),
            )
        )
        for planet_id, planet in planets.items():
            px, py, pz = _xyz(planet.get("position"))
            planet_rows.append(
                (
                    _as_int(planet_id),
                    system_id,
                    constellation_id,
                    region_id,
                    _as_int(planet.get("celestialIndex")),
                    _as_int(planet.get("typeID")),
                    px,
                    py,
                    pz,
                    _as_float(planet.get("radius")),
                    _to_json(planet),
                )
            )
            moons = planet.get("moons") or {}
            if isinstance(moons, dict):
                for moon_id, moon in moons.items():
                    mx, my, mz = _xyz(moon.get("position"))
                    moon_rows.append(
                        (
                            _as_int(moon_id),
                            _as_int(planet_id),
                            system_id,
                            _as_int(moon.get("typeID")),
                            mx,
                            my,
                            mz,
                            _as_float(moon.get("radius")),
                            _to_json(moon),
                        )
                    )
            belts = planet.get("asteroidBelts") or {}
            if isinstance(belts, dict):
                for belt_id, belt in belts.items():
                    bx, by, bz = _xyz(belt.get("position"))
                    belt_rows.append(
                        (
                            _as_int(belt_id),
                            _as_int(planet_id),
                            system_id,
                            bx,
                            by,
                            bz,
                            _to_json(belt),
                        )
                    )
            elif isinstance(belts, list):
                for index, belt in enumerate(belts):
                    bx, by, bz = _xyz((belt or {}).get("position"))
                    fallback_id = f"{planet_id}{index}"
                    belt_rows.append(
                        (
                            _as_int((belt or {}).get("id")) or _as_int(fallback_id) or index,
                            _as_int(planet_id),
                            system_id,
                            bx,
                            by,
                            bz,
                            _to_json(belt),
                        )
                    )
        star = data.get("star") or {}
        if star:
            sx, sy, sz = _xyz(star.get("position"))
            star_rows.append(
                (
                    _as_int(star.get("id")),
                    system_id,
                    _as_int(star.get("typeID")),
                    _as_float(star.get("radius")),
                    sx,
                    sy,
                    sz,
                    _to_json(star),
                )
            )
        for stargate_id, gate in stargates.items():
            gx, gy, gz = _xyz(gate.get("position"))
            gate_row = [
                _as_int(stargate_id),
                system_id,
                _as_int(gate.get("destination")),
                None,
                _as_int(gate.get("typeID")),
                gx,
                gy,
                gz,
                _to_json(gate),
            ]
            stargate_rows.append(gate_row)
            if gate_row[0] is not None:
                gate_to_system[gate_row[0]] = system_id or 0

    for row in stargate_rows:
        row[3] = gate_to_system.get(row[2])

    return {
        "dim_regions": _copy_rows(
            con,
            "dim_regions",
            ["region_id", "region_name", "faction_id", "x", "y", "z", "x_min", "y_min", "z_min", "x_max", "y_max", "z_max", "payload_json"],
            region_rows,
        ),
        "dim_constellations": _copy_rows(
            con,
            "dim_constellations",
            ["constellation_id", "constellation_name", "region_id", "x", "y", "z", "x_min", "y_min", "z_min", "x_max", "y_max", "z_max", "payload_json"],
            constellation_rows,
        ),
        "dim_systems": _copy_rows(
            con,
            "dim_systems",
            [
                "system_id",
                "system_name",
                "constellation_id",
                "region_id",
                "security",
                "sun_type_id",
                "border",
                "corridor",
                "fringe",
                "hub",
                "international",
                "regional",
                "planet_count",
                "stargate_count",
                "x",
                "y",
                "z",
                "x_min",
                "y_min",
                "z_min",
                "x_max",
                "y_max",
                "z_max",
                "payload_json",
            ],
            system_rows,
        ),
        "dim_stargates": _copy_rows(
            con,
            "dim_stargates",
            ["stargate_id", "system_id", "destination_stargate_id", "destination_system_id", "type_id", "x", "y", "z", "payload_json"],
            stargate_rows,
        ),
        "dim_planets": _copy_rows(
            con,
            "dim_planets",
            ["planet_id", "system_id", "constellation_id", "region_id", "celestial_index", "type_id", "x", "y", "z", "radius", "payload_json"],
            planet_rows,
        ),
        "dim_moons": _copy_rows(
            con,
            "dim_moons",
            ["moon_id", "planet_id", "system_id", "type_id", "x", "y", "z", "radius", "payload_json"],
            moon_rows,
        ),
        "dim_asteroid_belts": _copy_rows(
            con,
            "dim_asteroid_belts",
            ["asteroid_belt_id", "planet_id", "system_id", "x", "y", "z", "payload_json"],
            belt_rows,
        ),
        "dim_stars": _copy_rows(
            con,
            "dim_stars",
            ["star_id", "system_id", "type_id", "radius", "x", "y", "z", "payload_json"],
            star_rows,
        ),
    }


def _validate_warehouse(con: duckdb.DuckDBPyConnection) -> None:
    required_tables = {
        "dim_types": 1,
        "dim_groups": 1,
        "dim_categories": 1,
        "dim_market_groups": 1,
        "dim_regions": 1,
        "dim_constellations": 1,
        "dim_systems": 1,
        "dim_stations": 1,
    }
    for table_name, minimum in required_tables.items():
        row = _query_one(con, f'SELECT COUNT(*) AS row_count FROM "{table_name}"')
        count = int((row or {}).get("row_count") or 0)
        if count <= minimum:
            raise RuntimeError(f"Warehouse validation failed for {table_name}: expected > {minimum}, found {count}")


def _atomic_replace(temp_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    last_error = None
    for _ in range(10):
        try:
            os.replace(temp_path, target_path)
            return
        except OSError as exc:
            last_error = exc
            time.sleep(0.25)
    raise RuntimeError(f"Failed to replace {target_path} with {temp_path}: {last_error}")


def build_sde_warehouse(
    database_file: str | Path | None = None,
    source_root: str | Path | None = None,
    supported_languages: list[str] | None = None,
    source_hash: str | None = None,
    source_zip_path: str | None = None,
    source_etag: str | None = None,
    source_last_modified: str | None = None,
) -> dict:
    target_path = Path(database_file) if database_file else get_database_path()
    source_root_path = Path(source_root) if source_root else get_sde_root()
    supported_languages = supported_languages or get_supported_languages()
    temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    if temp_path.exists():
        temp_path.unlink()

    build_started = _utc_now()
    effective_source_hash = source_hash or compute_source_tree_hash(source_root_path)
    sde_version = source_last_modified or source_etag or effective_source_hash[:12]
    dataset_stats: list[dict] = []
    universe_counts = {
        "dim_regions": 0,
        "dim_constellations": 0,
        "dim_systems": 0,
    }

    logger.info("Building SDE warehouse at %s", target_path)
    _progress_print(f"[SDE Warehouse] building {target_path}")
    con = connect(temp_path, read_only=False)
    try:
        _bootstrap_schema(con)

        fsd_paths = sorted((source_root_path / "fsd").glob("*.yaml"))
        bsd_paths = sorted((source_root_path / "bsd").glob("*.yaml"))
        total_steps = len(fsd_paths) + len(bsd_paths) + (1 if (source_root_path / "universe").exists() else 0)
        current_step = 0

        for path in fsd_paths:
            current_step += 1
            _progress_print(f"[SDE Warehouse] {current_step}/{total_steps} loading fsd/{path.name}")
            data = _load_yaml_file(path) or {}
            table_name, row_count = _build_raw_table(con, "fsd", path, data, sde_version)
            _record_dataset(dataset_stats, "raw", path.stem, table_name, str(path), row_count)
            logger.info("[SDE Warehouse] raw %s -> %s rows", path.name, row_count)

            if path.name == "types.yaml":
                count = _insert_dim_types(con, data)
                _record_dataset(dataset_stats, "dim", "types", "dim_types", str(path), count)
                logger.info("[SDE Warehouse] dim_types -> %s rows", count)
            elif path.name == "groups.yaml":
                count = _insert_dim_groups(con, data)
                _record_dataset(dataset_stats, "dim", "groups", "dim_groups", str(path), count)
                logger.info("[SDE Warehouse] dim_groups -> %s rows", count)
            elif path.name == "categories.yaml":
                count = _insert_dim_categories(con, data)
                _record_dataset(dataset_stats, "dim", "categories", "dim_categories", str(path), count)
                logger.info("[SDE Warehouse] dim_categories -> %s rows", count)
            elif path.name == "marketGroups.yaml":
                count = _insert_dim_market_groups(con, data)
                _record_dataset(dataset_stats, "dim", "market_groups", "dim_market_groups", str(path), count)
                logger.info("[SDE Warehouse] dim_market_groups -> %s rows", count)
            elif path.name == "blueprints.yaml":
                count_blueprints, count_materials, count_products = _insert_fact_blueprints(con, data)
                _record_dataset(dataset_stats, "fact", "blueprints", "fact_blueprints", str(path), count_blueprints)
                _record_dataset(
                    dataset_stats,
                    "fact",
                    "blueprint_materials",
                    "fact_blueprint_materials",
                    str(path),
                    count_materials,
                )
                _record_dataset(
                    dataset_stats,
                    "fact",
                    "blueprint_products",
                    "fact_blueprint_products",
                    str(path),
                    count_products,
                )
                logger.info(
                    "[SDE Warehouse] blueprints -> %s blueprints, %s materials, %s products",
                    count_blueprints,
                    count_materials,
                    count_products,
                )
            elif path.name == "typeMaterials.yaml":
                count = _insert_fact_type_materials(con, data)
                _record_dataset(dataset_stats, "fact", "type_materials", "fact_type_materials", str(path), count)
                logger.info("[SDE Warehouse] fact_type_materials -> %s rows", count)
            elif path.name == "typeDogma.yaml":
                count_attrs, count_effects = _insert_fact_type_dogma(con, data)
                _record_dataset(
                    dataset_stats,
                    "fact",
                    "type_dogma_attributes",
                    "fact_type_dogma_attributes",
                    str(path),
                    count_attrs,
                )
                _record_dataset(
                    dataset_stats,
                    "fact",
                    "type_dogma_effects",
                    "fact_type_dogma_effects",
                    str(path),
                    count_effects,
                )
                logger.info(
                    "[SDE Warehouse] type dogma -> %s attributes, %s effects",
                    count_attrs,
                    count_effects,
                )

        for path in bsd_paths:
            current_step += 1
            _progress_print(f"[SDE Warehouse] {current_step}/{total_steps} loading bsd/{path.name}")
            data = _load_yaml_file(path) or []
            table_name, row_count = _build_raw_table(con, "bsd", path, data, sde_version)
            _record_dataset(dataset_stats, "raw", path.stem, table_name, str(path), row_count)
            logger.info("[SDE Warehouse] raw %s -> %s rows", path.name, row_count)

            if path.name == "staStations.yaml":
                count = _insert_dim_stations(con, data)
                _record_dataset(dataset_stats, "dim", "stations", "dim_stations", str(path), count)
                logger.info("[SDE Warehouse] dim_stations -> %s rows", count)
            elif path.name == "invItems.yaml":
                count = _insert_dim_inv_items(con, data)
                _record_dataset(dataset_stats, "dim", "inv_items", "dim_inv_items", str(path), count)
                logger.info("[SDE Warehouse] dim_inv_items -> %s rows", count)
            elif path.name == "invNames.yaml":
                count = _insert_dim_inv_names(con, data)
                _record_dataset(dataset_stats, "dim", "inv_names", "dim_inv_names", str(path), count)
                logger.info("[SDE Warehouse] dim_inv_names -> %s rows", count)
            elif path.name == "invPositions.yaml":
                count = _insert_dim_inv_positions(con, data)
                _record_dataset(dataset_stats, "dim", "inv_positions", "dim_inv_positions", str(path), count)
                logger.info("[SDE Warehouse] dim_inv_positions -> %s rows", count)

        universe_root = source_root_path / "universe"
        if universe_root.exists():
            current_step += 1
            _progress_print(f"[SDE Warehouse] {current_step}/{total_steps} loading universe")
            logger.info("[SDE Warehouse] building universe dimensions from %s", universe_root)
            universe_counts = _insert_universe(con, universe_root)
            for table_name, row_count in universe_counts.items():
                _record_dataset(
                    dataset_stats,
                    "dim",
                    table_name.replace("dim_", ""),
                    table_name,
                    str(universe_root),
                    row_count,
                )
                logger.info("[SDE Warehouse] %s -> %s rows", table_name, row_count)

        _validate_warehouse(con)

        con.executemany(
            """
            INSERT INTO sde_dataset_manifest (layer, dataset_name, table_name, source_path, row_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    row["layer"],
                    row["dataset_name"],
                    row["table_name"],
                    row["source_path"],
                    row["row_count"],
                )
                for row in dataset_stats
            ],
        )

        build_finished = _utc_now()
        con.execute(
            """
            INSERT INTO sde_manifest (
                manifest_id, build_started_at, build_finished_at, sde_version, source_hash,
                source_root, source_zip_path, source_etag, source_last_modified,
                supported_languages_json, fsd_file_count, bsd_file_count,
                universe_region_count, universe_constellation_count, universe_system_count, warehouse_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                1,
                build_started,
                build_finished,
                sde_version,
                effective_source_hash,
                str(source_root_path),
                source_zip_path or "",
                source_etag or "",
                source_last_modified or "",
                _to_json(supported_languages),
                len(fsd_paths),
                len(bsd_paths),
                universe_counts.get("dim_regions", 0),
                universe_counts.get("dim_constellations", 0),
                universe_counts.get("dim_systems", 0),
                str(target_path),
            ],
        )
        con.close()
        _atomic_replace(temp_path, target_path)
    except Exception:
        try:
            con.close()
        finally:
            if temp_path.exists():
                temp_path.unlink()
        _progress_print(f"[SDE Warehouse] build failed for {target_path}", final=True)
        raise

    logger.info("SDE warehouse build complete: %s", target_path)
    _progress_print(f"[SDE Warehouse] build complete: {target_path}", final=True)
    return get_warehouse_status(target_path)


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
            sql += " WHERE name IS NULL"
        return {int(row[0]) for row in con.execute(sql).fetchall()}
    finally:
        con.close()


def list_public_structures(database_file: str | Path | None = None) -> list[dict]:
    con = connect(database_file or get_database_path(), read_only=False)
    try:
        _ensure_public_schema(con)
        return _query_to_dicts(
            con,
            """
            SELECT structure_id, solar_system_id, region_id, owner_id, name, type_id, position_json, last_seen
            FROM structures
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
                structure_id, solar_system_id, region_id, owner_id, name, type_id, position_json, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
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
    from util import esi_spec_registry

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
    from util import esi_spec_registry

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
