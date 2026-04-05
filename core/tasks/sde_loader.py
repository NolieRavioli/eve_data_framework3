"""SDE pipeline: download → unzip → prune → build DuckDB warehouse.

Merged from workers/publicData/SDEBootstrap.py + SDELoader.py.

Entry points:
    update_sde()               — full pipeline: download, extract, prune, build
    rebuild_sde_warehouse()    — rebuild from existing _sde/ files
    build_sde_warehouse()      — low-level: parse YAML → DuckDB
    update_esi_spec()          — refresh ESI OpenAPI registry
"""
from __future__ import annotations

import csv
import hashlib
import logging
import os
import re
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Iterable

import duckdb
import requests
import yaml

from core.db.publicDB import (
    _as_bool,
    _as_float,
    _as_int,
    _ensure_public_schema,
    _ensure_registry_schema,
    _query_one,
    _to_json,
    _utc_now,
    connect,
    get_database_path,
    get_public_data_dir,
    get_sde_root,
    get_supported_languages,
    get_warehouse_status,
    compute_file_sha256,
)
from core.esi.registry import refresh_esi_spec_registry
from core.sde import refresh_all_caches

logger = logging.getLogger(__name__)

SDE_URL = "https://eve-static-data-export.s3-eu-west-1.amazonaws.com/tranquility/sde.zip"
SDE_PATH = Path(os.getenv("SDE_PATH", "_sde"))
SDE_ZIP_PATH = Path("_sde_tmp.zip")

FIELDS_TO_CLEAN = [
    "name",
    "description",
    "shortDescription",
    "descriptionID",
    "nameID",
    "displayNameID",
    "tooltipDescriptionID",
    "leaderTypeNameID",
    "serviceNameID",
    "operationNameID",
]

# ---------------------------------------------------------------------------
# Progress / UI helpers
# ---------------------------------------------------------------------------


def _yaml_loader():
    return getattr(yaml, "CLoader", yaml.SafeLoader)


def _supported_languages() -> list[str]:
    raw = os.getenv("SUPPORTED_LANGUAGES", "en")
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Small helpers (build-time only)
# ---------------------------------------------------------------------------

def _xyz(values: Any) -> tuple[float | None, float | None, float | None]:
    if isinstance(values, (list, tuple)) and len(values) == 3:
        return (_as_float(values[0]), _as_float(values[1]), _as_float(values[2]))
    if isinstance(values, dict):
        return (_as_float(values.get("x")), _as_float(values.get("y")), _as_float(values.get("z")))
    return (None, None, None)


def _best_row_key(index: int, value: Any) -> str:
    if isinstance(value, dict):
        for preferred in (
            "itemID", "stationID", "typeID", "blueprintTypeID",
            "marketGroupID", "groupID", "categoryID", "iconID",
            "graphicID", "flagID", "raceID", "bloodlineID", "factionID",
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


# ---------------------------------------------------------------------------
# Hash / integrity utilities
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# YAML / bulk-insert helpers
# ---------------------------------------------------------------------------

def _load_yaml_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.load(handle, Loader=_yaml_loader())


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
        mode="w", encoding="utf-8", newline="", suffix=".tsv",
        prefix=f"{table_name}_", dir=temp_dir, delete=False,
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


# ---------------------------------------------------------------------------
# SDE table DDL (ensure_tables equivalent — creates all SDE dimension/fact tables)
# ---------------------------------------------------------------------------

def _bootstrap_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create all SDE warehouse tables. Called during a fresh warehouse build."""
    con.execute("""
        CREATE TABLE sde_manifest (
            manifest_id INTEGER, build_started_at TIMESTAMP, build_finished_at TIMESTAMP,
            sde_version VARCHAR, source_hash VARCHAR, source_root VARCHAR,
            source_zip_path VARCHAR, source_etag VARCHAR, source_last_modified VARCHAR,
            supported_languages_json VARCHAR, fsd_file_count BIGINT, bsd_file_count BIGINT,
            universe_region_count BIGINT, universe_constellation_count BIGINT,
            universe_system_count BIGINT, warehouse_file VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE sde_dataset_manifest (
            layer VARCHAR, dataset_name VARCHAR, table_name VARCHAR,
            source_path VARCHAR, row_count BIGINT
        )
    """)
    _ensure_registry_schema(con)
    con.execute("""
        CREATE TABLE dim_types (
            type_id BIGINT PRIMARY KEY, group_id BIGINT, market_group_id BIGINT,
            published BOOLEAN, name_en VARCHAR, mass DOUBLE, volume DOUBLE,
            capacity DOUBLE, portion_size BIGINT, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_groups (
            group_id BIGINT PRIMARY KEY, category_id BIGINT, published BOOLEAN,
            name_en VARCHAR, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_categories (
            category_id BIGINT PRIMARY KEY, published BOOLEAN, name_en VARCHAR,
            payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_market_groups (
            market_group_id BIGINT PRIMARY KEY, parent_group_id BIGINT, icon_id BIGINT,
            has_types BOOLEAN, name_en VARCHAR, description_en VARCHAR, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE fact_blueprints (
            blueprint_type_id BIGINT PRIMARY KEY, max_production_limit BIGINT,
            manufacturing_time BIGINT, other_activities_json VARCHAR, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE fact_blueprint_materials (
            blueprint_type_id BIGINT, activity VARCHAR, material_type_id BIGINT,
            quantity BIGINT, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE fact_blueprint_products (
            blueprint_type_id BIGINT, activity VARCHAR, product_type_id BIGINT,
            quantity BIGINT, probability DOUBLE, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE fact_type_materials (
            type_id BIGINT, material_type_id BIGINT, quantity BIGINT, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE fact_type_dogma_attributes (
            type_id BIGINT, attribute_id BIGINT, value DOUBLE, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE fact_type_dogma_effects (
            type_id BIGINT, effect_id BIGINT, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_stations (
            station_id BIGINT PRIMARY KEY, station_name VARCHAR, station_type_id BIGINT,
            corporation_id BIGINT, operation_id BIGINT, solar_system_id BIGINT,
            constellation_id BIGINT, region_id BIGINT, security DOUBLE,
            x DOUBLE, y DOUBLE, z DOUBLE, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_inv_items (
            item_id BIGINT PRIMARY KEY, type_id BIGINT, location_id BIGINT,
            owner_id BIGINT, flag_id BIGINT, quantity BIGINT, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_inv_names (
            item_id BIGINT PRIMARY KEY, item_name VARCHAR, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_inv_positions (
            item_id BIGINT PRIMARY KEY, x DOUBLE, y DOUBLE, z DOUBLE,
            yaw DOUBLE, pitch DOUBLE, roll DOUBLE, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_regions (
            region_id BIGINT PRIMARY KEY, region_name VARCHAR, faction_id BIGINT,
            x DOUBLE, y DOUBLE, z DOUBLE, x_min DOUBLE, y_min DOUBLE, z_min DOUBLE,
            x_max DOUBLE, y_max DOUBLE, z_max DOUBLE, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_constellations (
            constellation_id BIGINT PRIMARY KEY, constellation_name VARCHAR, region_id BIGINT,
            x DOUBLE, y DOUBLE, z DOUBLE, x_min DOUBLE, y_min DOUBLE, z_min DOUBLE,
            x_max DOUBLE, y_max DOUBLE, z_max DOUBLE, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_systems (
            system_id BIGINT PRIMARY KEY, system_name VARCHAR, constellation_id BIGINT,
            region_id BIGINT, security DOUBLE, sun_type_id BIGINT, border BOOLEAN,
            corridor BOOLEAN, fringe BOOLEAN, hub BOOLEAN, international BOOLEAN,
            regional BOOLEAN, planet_count BIGINT, stargate_count BIGINT,
            x DOUBLE, y DOUBLE, z DOUBLE, x_min DOUBLE, y_min DOUBLE, z_min DOUBLE,
            x_max DOUBLE, y_max DOUBLE, z_max DOUBLE, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_stargates (
            stargate_id BIGINT PRIMARY KEY, system_id BIGINT,
            destination_stargate_id BIGINT, destination_system_id BIGINT,
            type_id BIGINT, x DOUBLE, y DOUBLE, z DOUBLE, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_planets (
            planet_id BIGINT PRIMARY KEY, system_id BIGINT, constellation_id BIGINT,
            region_id BIGINT, celestial_index BIGINT, type_id BIGINT,
            x DOUBLE, y DOUBLE, z DOUBLE, radius DOUBLE, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_moons (
            moon_id BIGINT PRIMARY KEY, planet_id BIGINT, system_id BIGINT,
            type_id BIGINT, x DOUBLE, y DOUBLE, z DOUBLE, radius DOUBLE,
            payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_asteroid_belts (
            asteroid_belt_id BIGINT PRIMARY KEY, planet_id BIGINT, system_id BIGINT,
            x DOUBLE, y DOUBLE, z DOUBLE, payload_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_stars (
            star_id BIGINT PRIMARY KEY, system_id BIGINT, type_id BIGINT,
            radius DOUBLE, x DOUBLE, y DOUBLE, z DOUBLE, payload_json VARCHAR
        )
    """)
    _ensure_public_schema(con)


# ---------------------------------------------------------------------------
# Dataset recording helper
# ---------------------------------------------------------------------------

def _record_dataset(
    stats: list[dict], layer: str, dataset_name: str,
    table_name: str, source_path: str | None, row_count: int,
) -> None:
    stats.append({
        "layer": layer, "dataset_name": dataset_name, "table_name": table_name,
        "source_path": source_path or "", "row_count": int(row_count),
    })


def _build_raw_table(
    con: duckdb.DuckDBPyConnection, layer: str, path: Path,
    data: Any, sde_version: str,
) -> tuple[str, int]:
    table_name = _sanitize_table_name(f"raw_{layer}", path.stem)
    con.execute(f"""
        CREATE TABLE "{table_name}" (
            row_key VARCHAR, payload_json VARCHAR,
            sde_version VARCHAR, source_path VARCHAR
        )
    """)
    row_count = _copy_rows(
        con, table_name,
        ["row_key", "payload_json", "sde_version", "source_path"],
        ((row_key, payload_json, sde_version, str(path)) for row_key, payload_json in _iter_raw_rows(data)),
        directory=path.parent,
    )
    return table_name, row_count


# ---------------------------------------------------------------------------
# FSD dimension inserters
# ---------------------------------------------------------------------------

def _insert_dim_types(con: duckdb.DuckDBPyConnection, data: dict) -> int:
    return _copy_rows(
        con, "dim_types",
        ["type_id", "group_id", "market_group_id", "published", "name_en", "mass", "volume", "capacity", "portion_size", "payload_json"],
        (
            (
                _as_int(type_id), _as_int(props.get("groupID")),
                _as_int(props.get("marketGroupID")), _as_bool(props.get("published")),
                ((props.get("name") or {}).get("en") if isinstance(props.get("name"), dict) else None),
                _as_float(props.get("mass")), _as_float(props.get("volume")),
                _as_float(props.get("capacity")), _as_int(props.get("portionSize")),
                _to_json(props),
            )
            for type_id, props in data.items()
        ),
    )


def _insert_dim_groups(con: duckdb.DuckDBPyConnection, data: dict) -> int:
    return _copy_rows(
        con, "dim_groups",
        ["group_id", "category_id", "published", "name_en", "payload_json"],
        (
            (
                _as_int(group_id), _as_int(props.get("categoryID")),
                _as_bool(props.get("published")),
                ((props.get("name") or {}).get("en") if isinstance(props.get("name"), dict) else None),
                _to_json(props),
            )
            for group_id, props in data.items()
        ),
    )


def _insert_dim_categories(con: duckdb.DuckDBPyConnection, data: dict) -> int:
    return _copy_rows(
        con, "dim_categories",
        ["category_id", "published", "name_en", "payload_json"],
        (
            (
                _as_int(category_id), _as_bool(props.get("published")),
                ((props.get("name") or {}).get("en") if isinstance(props.get("name"), dict) else None),
                _to_json(props),
            )
            for category_id, props in data.items()
        ),
    )


def _insert_dim_market_groups(con: duckdb.DuckDBPyConnection, data: dict) -> int:
    return _copy_rows(
        con, "dim_market_groups",
        ["market_group_id", "parent_group_id", "icon_id", "has_types", "name_en", "description_en", "payload_json"],
        (
            (
                _as_int(group_id), _as_int(props.get("parentGroupID")),
                _as_int(props.get("iconID")), _as_bool(props.get("hasTypes")),
                ((props.get("nameID") or {}).get("en") if isinstance(props.get("nameID"), dict) else None),
                ((props.get("descriptionID") or {}).get("en") if isinstance(props.get("descriptionID"), dict) else None),
                _to_json(props),
            )
            for group_id, props in data.items()
        ),
    )


def _insert_fact_blueprints(con: duckdb.DuckDBPyConnection, data: dict) -> tuple[int, int, int]:
    blueprint_rows, material_rows, product_rows = [], [], []
    for blueprint_type_id, props in data.items():
        activities = props.get("activities") or {}
        manufacturing = activities.get("manufacturing") or {}
        other_activities = {k: v for k, v in activities.items() if k != "manufacturing"}
        blueprint_rows.append((
            _as_int(blueprint_type_id), _as_int(props.get("maxProductionLimit")),
            _as_int(manufacturing.get("time")), _to_json(other_activities), _to_json(props),
        ))
        for activity_name, activity in activities.items():
            for material in activity.get("materials", []) or []:
                material_rows.append((
                    _as_int(blueprint_type_id), activity_name,
                    _as_int(material.get("typeID")), _as_int(material.get("quantity")),
                    _to_json(material),
                ))
            for product in activity.get("products", []) or []:
                product_rows.append((
                    _as_int(blueprint_type_id), activity_name,
                    _as_int(product.get("typeID")), _as_int(product.get("quantity")),
                    _as_float(product.get("probability")), _to_json(product),
                ))
    count_bp = _copy_rows(con, "fact_blueprints",
        ["blueprint_type_id", "max_production_limit", "manufacturing_time", "other_activities_json", "payload_json"],
        blueprint_rows)
    count_mat = _copy_rows(con, "fact_blueprint_materials",
        ["blueprint_type_id", "activity", "material_type_id", "quantity", "payload_json"],
        material_rows)
    count_prod = _copy_rows(con, "fact_blueprint_products",
        ["blueprint_type_id", "activity", "product_type_id", "quantity", "probability", "payload_json"],
        product_rows)
    return count_bp, count_mat, count_prod


def _insert_fact_type_materials(con: duckdb.DuckDBPyConnection, data: dict) -> int:
    return _copy_rows(
        con, "fact_type_materials",
        ["type_id", "material_type_id", "quantity", "payload_json"],
        (
            (_as_int(type_id), _as_int(m.get("materialTypeID")),
             _as_int(m.get("quantity")), _to_json(m))
            for type_id, props in data.items()
            for m in (props.get("materials") or [])
        ),
    )


def _insert_fact_type_dogma(con: duckdb.DuckDBPyConnection, data: dict) -> tuple[int, int]:
    attr_rows, effect_rows = [], []
    for type_id, props in data.items():
        for a in props.get("dogmaAttributes", []) or []:
            attr_rows.append((_as_int(type_id), _as_int(a.get("attributeID")),
                              _as_float(a.get("value")), _to_json(a)))
        for e in props.get("dogmaEffects", []) or []:
            effect_rows.append((_as_int(type_id), _as_int(e.get("effectID")), _to_json(e)))
    count_a = _copy_rows(con, "fact_type_dogma_attributes",
        ["type_id", "attribute_id", "value", "payload_json"], attr_rows)
    count_e = _copy_rows(con, "fact_type_dogma_effects",
        ["type_id", "effect_id", "payload_json"], effect_rows)
    return count_a, count_e


# ---------------------------------------------------------------------------
# BSD dimension inserters
# ---------------------------------------------------------------------------

def _insert_dim_stations(con: duckdb.DuckDBPyConnection, data: list[dict]) -> int:
    return _copy_rows(
        con, "dim_stations",
        ["station_id", "station_name", "station_type_id", "corporation_id",
         "operation_id", "solar_system_id", "constellation_id", "region_id",
         "security", "x", "y", "z", "payload_json"],
        (
            (_as_int(r.get("stationID")), r.get("stationName"),
             _as_int(r.get("stationTypeID")), _as_int(r.get("corporationID")),
             _as_int(r.get("operationID")), _as_int(r.get("solarSystemID")),
             _as_int(r.get("constellationID")), _as_int(r.get("regionID")),
             _as_float(r.get("security")), _as_float(r.get("x")),
             _as_float(r.get("y")), _as_float(r.get("z")), _to_json(r))
            for r in data
        ),
    )


def _insert_dim_inv_items(con: duckdb.DuckDBPyConnection, data: list[dict]) -> int:
    return _copy_rows(
        con, "dim_inv_items",
        ["item_id", "type_id", "location_id", "owner_id", "flag_id", "quantity", "payload_json"],
        (
            (_as_int(r.get("itemID")), _as_int(r.get("typeID")),
             _as_int(r.get("locationID")), _as_int(r.get("ownerID")),
             _as_int(r.get("flagID")), _as_int(r.get("quantity")), _to_json(r))
            for r in data
        ),
    )


def _insert_dim_inv_names(con: duckdb.DuckDBPyConnection, data: list[dict]) -> int:
    return _copy_rows(
        con, "dim_inv_names",
        ["item_id", "item_name", "payload_json"],
        ((_as_int(r.get("itemID")), r.get("itemName"), _to_json(r)) for r in data),
    )


def _insert_dim_inv_positions(con: duckdb.DuckDBPyConnection, data: list[dict]) -> int:
    return _copy_rows(
        con, "dim_inv_positions",
        ["item_id", "x", "y", "z", "yaw", "pitch", "roll", "payload_json"],
        (
            (_as_int(r.get("itemID")), _as_float(r.get("x")), _as_float(r.get("y")),
             _as_float(r.get("z")), _as_float(r.get("yaw")), _as_float(r.get("pitch")),
             _as_float(r.get("roll")), _to_json(r))
            for r in data
        ),
    )


# ---------------------------------------------------------------------------
# Universe dimension inserter
# ---------------------------------------------------------------------------

def _insert_universe(con: duckdb.DuckDBPyConnection, universe_root: Path) -> dict[str, int]:
    inv_names: dict[int, str] = {
        row[0]: row[1]
        for row in con.execute("SELECT item_id, item_name FROM dim_inv_names").fetchall()
    }
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
        region_rows.append((
            region_id, inv_names.get(region_id), _as_int(data.get("factionID")),
            x, y, z, x_min, y_min, z_min, x_max, y_max, z_max, _to_json(data),
        ))

    for constellation_path in sorted(universe_root.rglob("constellation.yaml")):
        data = _load_yaml_file(constellation_path) or {}
        constellation_dir = constellation_path.parent
        region_dir = constellation_dir.parent
        constellation_id = _as_int(data.get("constellationID"))
        constellation_dir_to_id[constellation_dir] = constellation_id or 0
        x, y, z = _xyz(data.get("center"))
        x_min, y_min, z_min = _xyz(data.get("min"))
        x_max, y_max, z_max = _xyz(data.get("max"))
        constellation_rows.append((
            constellation_id, inv_names.get(constellation_id),
            region_dir_to_id.get(region_dir),
            x, y, z, x_min, y_min, z_min, x_max, y_max, z_max, _to_json(data),
        ))

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
        system_rows.append((
            system_id, inv_names.get(system_id), constellation_id, region_id,
            _as_float(data.get("security")), _as_int(data.get("sunTypeID")),
            _as_bool(data.get("border")), _as_bool(data.get("corridor")),
            _as_bool(data.get("fringe")), _as_bool(data.get("hub")),
            _as_bool(data.get("international")), _as_bool(data.get("regional")),
            len(planets), len(stargates),
            x, y, z, x_min, y_min, z_min, x_max, y_max, z_max, _to_json(data),
        ))
        for planet_id, planet in planets.items():
            px, py, pz = _xyz(planet.get("position"))
            planet_rows.append((
                _as_int(planet_id), system_id, constellation_id, region_id,
                _as_int(planet.get("celestialIndex")), _as_int(planet.get("typeID")),
                px, py, pz, _as_float(planet.get("radius")), _to_json(planet),
            ))
            moons = planet.get("moons") or {}
            if isinstance(moons, dict):
                for moon_id, moon in moons.items():
                    mx, my, mz = _xyz(moon.get("position"))
                    moon_rows.append((
                        _as_int(moon_id), _as_int(planet_id), system_id,
                        _as_int(moon.get("typeID")), mx, my, mz,
                        _as_float(moon.get("radius")), _to_json(moon),
                    ))
            belts = planet.get("asteroidBelts") or {}
            if isinstance(belts, dict):
                for belt_id, belt in belts.items():
                    bx, by, bz = _xyz(belt.get("position"))
                    belt_rows.append((
                        _as_int(belt_id), _as_int(planet_id), system_id,
                        bx, by, bz, _to_json(belt),
                    ))
            elif isinstance(belts, list):
                for index, belt in enumerate(belts):
                    bx, by, bz = _xyz((belt or {}).get("position"))
                    fallback_id = f"{planet_id}{index}"
                    belt_rows.append((
                        _as_int((belt or {}).get("id")) or _as_int(fallback_id) or index,
                        _as_int(planet_id), system_id, bx, by, bz, _to_json(belt),
                    ))
        star = data.get("star") or {}
        if star:
            sx, sy, sz = _xyz(star.get("position"))
            star_rows.append((
                _as_int(star.get("id")), system_id, _as_int(star.get("typeID")),
                _as_float(star.get("radius")), sx, sy, sz, _to_json(star),
            ))
        for stargate_id, gate in stargates.items():
            gx, gy, gz = _xyz(gate.get("position"))
            gate_row = [
                _as_int(stargate_id), system_id, _as_int(gate.get("destination")),
                None, _as_int(gate.get("typeID")), gx, gy, gz, _to_json(gate),
            ]
            stargate_rows.append(gate_row)
            if gate_row[0] is not None:
                gate_to_system[gate_row[0]] = system_id or 0

    for row in stargate_rows:
        row[3] = gate_to_system.get(row[2])

    return {
        "dim_regions": _copy_rows(con, "dim_regions",
            ["region_id", "region_name", "faction_id", "x", "y", "z",
             "x_min", "y_min", "z_min", "x_max", "y_max", "z_max", "payload_json"],
            region_rows),
        "dim_constellations": _copy_rows(con, "dim_constellations",
            ["constellation_id", "constellation_name", "region_id", "x", "y", "z",
             "x_min", "y_min", "z_min", "x_max", "y_max", "z_max", "payload_json"],
            constellation_rows),
        "dim_systems": _copy_rows(con, "dim_systems",
            ["system_id", "system_name", "constellation_id", "region_id",
             "security", "sun_type_id", "border", "corridor", "fringe",
             "hub", "international", "regional", "planet_count", "stargate_count",
             "x", "y", "z", "x_min", "y_min", "z_min", "x_max", "y_max", "z_max", "payload_json"],
            system_rows),
        "dim_stargates": _copy_rows(con, "dim_stargates",
            ["stargate_id", "system_id", "destination_stargate_id", "destination_system_id",
             "type_id", "x", "y", "z", "payload_json"],
            stargate_rows),
        "dim_planets": _copy_rows(con, "dim_planets",
            ["planet_id", "system_id", "constellation_id", "region_id",
             "celestial_index", "type_id", "x", "y", "z", "radius", "payload_json"],
            planet_rows),
        "dim_moons": _copy_rows(con, "dim_moons",
            ["moon_id", "planet_id", "system_id", "type_id", "x", "y", "z",
             "radius", "payload_json"], moon_rows),
        "dim_asteroid_belts": _copy_rows(con, "dim_asteroid_belts",
            ["asteroid_belt_id", "planet_id", "system_id", "x", "y", "z", "payload_json"],
            belt_rows),
        "dim_stars": _copy_rows(con, "dim_stars",
            ["star_id", "system_id", "type_id", "radius", "x", "y", "z", "payload_json"],
            star_rows),
    }


# ---------------------------------------------------------------------------
# Warehouse validation and atomic file replace
# ---------------------------------------------------------------------------

def _validate_warehouse(con: duckdb.DuckDBPyConnection) -> None:
    required_tables = {
        "dim_types": 1, "dim_groups": 1, "dim_categories": 1,
        "dim_market_groups": 1, "dim_regions": 1, "dim_constellations": 1,
        "dim_systems": 1, "dim_stations": 1,
    }
    for table_name, minimum in required_tables.items():
        row = _query_one(con, f'SELECT COUNT(*) AS row_count FROM "{table_name}"')
        count = int((row or {}).get("row_count") or 0)
        if count <= minimum:
            raise RuntimeError(
                f"Warehouse validation failed for {table_name}: expected > {minimum}, found {count}"
            )


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


# ---------------------------------------------------------------------------
# Download / extract / prune (from SDEBootstrap)
# ---------------------------------------------------------------------------

def download_sde(url: str = SDE_URL, dest: Path = SDE_ZIP_PATH, retries: int = 3) -> dict:
    backoff = 2
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            logger.info("Downloading SDE (attempt %s)...", attempt)
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            with dest.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=8192):
                    handle.write(chunk)
            logger.info("SDE download complete.")
            return {
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
                "sha256": compute_file_sha256(dest),
                "zip_path": str(dest),
            }
        except requests.RequestException as exc:
            last_error = exc
            logger.warning("SDE download attempt %s failed: %s", attempt, exc)
            if attempt < retries:
                time.sleep(backoff)
                backoff *= 2
    raise RuntimeError(f"Failed to download SDE after {retries} attempts: {last_error}")


def unzip_sde(zip_path: Path = SDE_ZIP_PATH, extract_to: Path = SDE_PATH) -> None:
    if extract_to.exists():
        logger.info("Cleaning existing SDE folder at %s", extract_to)
        shutil.rmtree(extract_to)
    extract_to.mkdir(parents=True, exist_ok=True)
    logger.info("Extracting %s to %s", zip_path, extract_to)
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(extract_to)
    logger.info("SDE extraction complete.")


def cleanup(zip_path: Path = SDE_ZIP_PATH) -> None:
    if zip_path.exists():
        zip_path.unlink()
        logger.info("Removed temporary SDE archive %s", zip_path)


def clean_multilang_fields(data):
    supported_languages = _supported_languages()
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            if key in FIELDS_TO_CLEAN and isinstance(value, dict):
                cleaned[key] = {lang: value[lang] for lang in supported_languages if lang in value}
            else:
                cleaned[key] = clean_multilang_fields(value)
        return cleaned
    if isinstance(data, list):
        return [clean_multilang_fields(item) for item in data]
    return data


def migrate_sde_inplace(fsd_dir: Path | None = None) -> None:
    fsd_dir = fsd_dir or (SDE_PATH / "fsd")
    if not fsd_dir.exists():
        logger.warning("No fsd folder found at %s, skipping language pruning.", fsd_dir)
        return
    yaml_paths = sorted(fsd_dir.rglob("*.yaml"))
    logger.info("Pruning FSD language maps to supported languages: %s", ", ".join(_supported_languages()))
    if not yaml_paths:
        logger.info("No FSD YAML files found under %s; skipping language pruning.", fsd_dir)
        return
    for index, path in enumerate(yaml_paths, start=1):
        relative_path = path.relative_to(fsd_dir).as_posix()
        logger.debug("[SDE] pruning %s/%s %s", index, len(yaml_paths), relative_path)
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.load(handle, Loader=_yaml_loader())
            cleaned = clean_multilang_fields(data)
            with path.open("w", encoding="utf-8") as handle:
                yaml.safe_dump(cleaned, handle, allow_unicode=True)
        except Exception as exc:
            logger.error("Error pruning %s: %s", path, exc)
    logger.info("SDE language pruning complete.")


# ---------------------------------------------------------------------------
# Warehouse build entry point
# ---------------------------------------------------------------------------

def build_sde_warehouse(
    database_file: str | Path | None = None,
    source_root: str | Path | None = None,
    supported_languages: list[str] | None = None,
    source_hash: str | None = None,
    source_zip_path: str | None = None,
    source_etag: str | None = None,
    source_last_modified: str | None = None,
) -> dict:
    """Parse SDE YAML files and write a fresh DuckDB warehouse."""
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
    universe_counts = {"dim_regions": 0, "dim_constellations": 0, "dim_systems": 0}

    logger.info("Building SDE warehouse at %s", target_path)
    con = connect(temp_path, read_only=False)
    try:
        _bootstrap_schema(con)

        fsd_paths = sorted((source_root_path / "fsd").glob("*.yaml"))
        bsd_paths = sorted((source_root_path / "bsd").glob("*.yaml"))
        total_steps = len(fsd_paths) + len(bsd_paths) + (1 if (source_root_path / "universe").exists() else 0)
        current_step = 0

        for path in fsd_paths:
            current_step += 1
            logger.info("[SDE Warehouse] %s/%s loading fsd/%s", current_step, total_steps, path.name)
            data = _load_yaml_file(path) or {}
            table_name, row_count = _build_raw_table(con, "fsd", path, data, sde_version)
            _record_dataset(dataset_stats, "raw", path.stem, table_name, str(path), row_count)
            logger.info("[SDE Warehouse] raw %s -> %s rows", path.name, row_count)

            if path.name == "types.yaml":
                count = _insert_dim_types(con, data)
                _record_dataset(dataset_stats, "dim", "types", "dim_types", str(path), count)
            elif path.name == "groups.yaml":
                count = _insert_dim_groups(con, data)
                _record_dataset(dataset_stats, "dim", "groups", "dim_groups", str(path), count)
            elif path.name == "categories.yaml":
                count = _insert_dim_categories(con, data)
                _record_dataset(dataset_stats, "dim", "categories", "dim_categories", str(path), count)
            elif path.name == "marketGroups.yaml":
                count = _insert_dim_market_groups(con, data)
                _record_dataset(dataset_stats, "dim", "market_groups", "dim_market_groups", str(path), count)
            elif path.name == "blueprints.yaml":
                c_bp, c_mat, c_prod = _insert_fact_blueprints(con, data)
                _record_dataset(dataset_stats, "fact", "blueprints", "fact_blueprints", str(path), c_bp)
                _record_dataset(dataset_stats, "fact", "blueprint_materials", "fact_blueprint_materials", str(path), c_mat)
                _record_dataset(dataset_stats, "fact", "blueprint_products", "fact_blueprint_products", str(path), c_prod)
            elif path.name == "typeMaterials.yaml":
                count = _insert_fact_type_materials(con, data)
                _record_dataset(dataset_stats, "fact", "type_materials", "fact_type_materials", str(path), count)
            elif path.name == "typeDogma.yaml":
                c_a, c_e = _insert_fact_type_dogma(con, data)
                _record_dataset(dataset_stats, "fact", "type_dogma_attributes", "fact_type_dogma_attributes", str(path), c_a)
                _record_dataset(dataset_stats, "fact", "type_dogma_effects", "fact_type_dogma_effects", str(path), c_e)

        for path in bsd_paths:
            current_step += 1
            logger.info("[SDE Warehouse] %s/%s loading bsd/%s", current_step, total_steps, path.name)
            data = _load_yaml_file(path) or []
            table_name, row_count = _build_raw_table(con, "bsd", path, data, sde_version)
            _record_dataset(dataset_stats, "raw", path.stem, table_name, str(path), row_count)

            if path.name == "staStations.yaml":
                count = _insert_dim_stations(con, data)
                _record_dataset(dataset_stats, "dim", "stations", "dim_stations", str(path), count)
            elif path.name == "invItems.yaml":
                count = _insert_dim_inv_items(con, data)
                _record_dataset(dataset_stats, "dim", "inv_items", "dim_inv_items", str(path), count)
            elif path.name == "invNames.yaml":
                count = _insert_dim_inv_names(con, data)
                _record_dataset(dataset_stats, "dim", "inv_names", "dim_inv_names", str(path), count)
            elif path.name == "invPositions.yaml":
                count = _insert_dim_inv_positions(con, data)
                _record_dataset(dataset_stats, "dim", "inv_positions", "dim_inv_positions", str(path), count)

        universe_root = source_root_path / "universe"
        if universe_root.exists():
            current_step += 1
            logger.info("[SDE Warehouse] %s/%s loading universe", current_step, total_steps)
            logger.info("[SDE Warehouse] building universe dimensions from %s", universe_root)
            universe_counts = _insert_universe(con, universe_root)
            for tbl, rc in universe_counts.items():
                _record_dataset(dataset_stats, "dim", tbl.replace("dim_", ""), tbl, str(universe_root), rc)

        _validate_warehouse(con)

        con.executemany(
            "INSERT INTO sde_dataset_manifest (layer, dataset_name, table_name, source_path, row_count) VALUES (?, ?, ?, ?, ?)",
            [(r["layer"], r["dataset_name"], r["table_name"], r["source_path"], r["row_count"]) for r in dataset_stats],
        )

        build_finished = _utc_now()
        con.execute(
            """INSERT INTO sde_manifest (
                manifest_id, build_started_at, build_finished_at, sde_version, source_hash,
                source_root, source_zip_path, source_etag, source_last_modified,
                supported_languages_json, fsd_file_count, bsd_file_count,
                universe_region_count, universe_constellation_count, universe_system_count, warehouse_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                1, build_started, build_finished, sde_version, effective_source_hash,
                str(source_root_path), source_zip_path or "", source_etag or "",
                source_last_modified or "", _to_json(supported_languages),
                len(fsd_paths), len(bsd_paths),
                universe_counts.get("dim_regions", 0),
                universe_counts.get("dim_constellations", 0),
                universe_counts.get("dim_systems", 0), str(target_path),
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
        logger.error("[SDE Warehouse] build failed for %s", target_path)
        raise

    logger.info("SDE warehouse build complete: %s", target_path)
    return get_warehouse_status(target_path)


# ---------------------------------------------------------------------------
# High-level pipeline entry points
# ---------------------------------------------------------------------------

def rebuild_sde_warehouse(source_meta: dict | None = None) -> dict:
    source_meta = source_meta or {}
    build_sde_warehouse(
        source_root=SDE_PATH,
        supported_languages=_supported_languages(),
        source_hash=source_meta.get("sha256"),
        source_zip_path=source_meta.get("zip_path"),
        source_etag=source_meta.get("etag"),
        source_last_modified=source_meta.get("last_modified"),
    )
    try:
        from core.db.publicDB import sync_esi_registry_to_warehouse
        sync_esi_registry_to_warehouse()
    except (FileNotFoundError, ImportError):
        logger.info("No ESI registry present yet; skipping DuckDB registry sync after SDE rebuild.")
    refresh_all_caches()
    logger.info("[SDE] warehouse rebuild complete")
    return get_warehouse_status()


def update_sde() -> dict:
    """Refresh the local SDE files, rebuild the DuckDB warehouse, and warm caches."""
    source_meta = download_sde()
    try:
        unzip_sde()
        migrate_sde_inplace()
        status = rebuild_sde_warehouse(source_meta)
    finally:
        cleanup()
    logger.info("SDE warehouse refreshed and caches warmed.")
    return status


def update_esi_spec() -> dict:
    """Refresh the versioned ESI OpenAPI registry."""
    return refresh_esi_spec_registry()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    update_sde()

