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
import json
import logging
import os
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, Iterable

import duckdb
import requests
import yaml

from core.db.public import (
    _as_bool,
    _as_float,
    _as_int,
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
from core.db.sde import refresh_all_caches

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
# SDE currency check — HEAD request w/ ETag comparison
# ---------------------------------------------------------------------------

def warehouse_exists() -> bool:
    """Return True if the DuckDB warehouse has an sde_manifest table."""
    from core.db.public import warehouse_exists as _wh_exists
    return _wh_exists()


def check_sde_currency(url: str = SDE_URL) -> dict:
    """Check whether the local SDE warehouse is still current.

    Sends a HEAD request to the S3 SDE URL and compares the ETag with the
    value stored in ``sde_manifest``.

    Returns
    -------
    dict
        ``{"current": bool, "local_etag": str | None, "remote_etag": str | None,
           "error": str | None}``
    """
    local_etag = None
    try:
        con = connect()
        try:
            row = con.execute(
                "SELECT source_etag FROM sde_manifest ORDER BY manifest_id DESC LIMIT 1"
            ).fetchone()
            local_etag = row[0] if row else None
        finally:
            con.close()
    except Exception:
        pass  # warehouse may not exist yet

    remote_etag = None
    try:
        resp = requests.head(url, timeout=15)
        resp.raise_for_status()
        remote_etag = resp.headers.get("ETag")
    except Exception as exc:
        return {
            "current": True,  # assume current if we can't reach S3
            "local_etag": local_etag,
            "remote_etag": None,
            "error": str(exc),
        }

    if local_etag and remote_etag and local_etag == remote_etag:
        return {"current": True, "local_etag": local_etag, "remote_etag": remote_etag, "error": None}

    return {"current": False, "local_etag": local_etag, "remote_etag": remote_etag, "error": None}

# ---------------------------------------------------------------------------
# Progress / UI helpers
# ---------------------------------------------------------------------------


def _yaml_loader():
    return getattr(yaml, "CSafeLoader", yaml.SafeLoader)


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
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_ALL)
        for row in rows:
            cleaned = []
            for value in row:
                if value is None:
                    cleaned.append("\\N")
                elif isinstance(value, str):
                    # Strip \r — embedded \r\n confuses TSV parsers
                    cleaned.append(value.replace("\r", ""))
                else:
                    cleaned.append(value)
            writer.writerow(cleaned)
            total += 1
    try:
        if total == 0:
            return 0
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


# ---------------------------------------------------------------------------
# SDE table DDL (ensure_tables equivalent — creates all SDE dimension/fact tables)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# SDE schema loading + schema-driven DDL
# ---------------------------------------------------------------------------

_SDE_SCHEMA_PATH = Path("core/db/generated/sde_schema.json")


def _load_sde_schema() -> dict:
    """Load the generated SDE schema JSON. Raise if missing."""
    if not _SDE_SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"SDE schema not found at {_SDE_SCHEMA_PATH}. "
            "Run 'python build.py --sde-schema' to generate it."
        )
    with _SDE_SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _ddl_for_table(table_def: dict) -> str:
    """Generate a CREATE TABLE statement from a schema table definition."""
    table_name = table_def["table_name"]
    parts = []
    for col in table_def["columns"]:
        col_str = f'"{col["name"]}" {col["dtype"]}'
        if col.get("pk"):
            col_str += " PRIMARY KEY"
        parts.append(col_str)
    return f'CREATE TABLE "{table_name}" ({", ".join(parts)})'


def _bootstrap_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create all SDE warehouse tables from the generated schema JSON."""
    # Manifest / metadata tables (not in schema — always present)
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

    # Schema-driven dimension / fact tables
    schema = _load_sde_schema()
    for table_def in schema["tables"]:
        ddl = _ddl_for_table(table_def)
        con.execute(ddl)

    # Universe sub-object tables (populated by _insert_universe, not schema-driven)
    con.execute("""
        CREATE TABLE sde_planets (
            planet_id        BIGINT PRIMARY KEY,
            system_id        BIGINT,
            type_id          INTEGER,
            celestial_index  INTEGER,
            x                DOUBLE,
            y                DOUBLE,
            z                DOUBLE,
            radius           DOUBLE,
            density          DOUBLE,
            eccentricity     DOUBLE,
            escape_velocity  DOUBLE,
            fragmented       BOOLEAN,
            life             DOUBLE,
            locked           BOOLEAN,
            mass_dust        DOUBLE,
            mass_gas         DOUBLE,
            orbit_period     DOUBLE,
            orbit_radius     DOUBLE,
            pressure         DOUBLE,
            rotation_rate    DOUBLE,
            spectral_class   VARCHAR,
            surface_gravity  DOUBLE,
            temperature      DOUBLE,
            payload_json     VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE sde_moons (
            moon_id          BIGINT PRIMARY KEY,
            system_id        BIGINT,
            planet_id        BIGINT,
            type_id          INTEGER,
            x                DOUBLE,
            y                DOUBLE,
            z                DOUBLE,
            radius           DOUBLE,
            density          DOUBLE,
            eccentricity     DOUBLE,
            escape_velocity  DOUBLE,
            fragmented       BOOLEAN,
            life             DOUBLE,
            locked           BOOLEAN,
            mass_dust        DOUBLE,
            mass_gas         DOUBLE,
            orbit_period     DOUBLE,
            orbit_radius     DOUBLE,
            pressure         DOUBLE,
            rotation_rate    DOUBLE,
            spectral_class   VARCHAR,
            surface_gravity  DOUBLE,
            temperature      DOUBLE,
            payload_json     VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE sde_asteroidBelts (
            belt_id          BIGINT PRIMARY KEY,
            system_id        BIGINT,
            planet_id        BIGINT,
            type_id          INTEGER,
            x                DOUBLE,
            y                DOUBLE,
            z                DOUBLE,
            density          DOUBLE,
            eccentricity     DOUBLE,
            escape_velocity  DOUBLE,
            fragmented       BOOLEAN,
            life             DOUBLE,
            locked           BOOLEAN,
            mass_dust        DOUBLE,
            mass_gas         DOUBLE,
            orbit_period     DOUBLE,
            orbit_radius     DOUBLE,
            pressure         DOUBLE,
            rotation_rate    DOUBLE,
            spectral_class   VARCHAR,
            surface_gravity  DOUBLE,
            temperature      DOUBLE,
            payload_json     VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE sde_stargates (
            stargate_id             BIGINT PRIMARY KEY,
            system_id               BIGINT,
            type_id                 INTEGER,
            destination_stargate_id BIGINT,
            destination_system_id   BIGINT,
            x                       DOUBLE,
            y                       DOUBLE,
            z                       DOUBLE,
            payload_json            VARCHAR
        )
    """)

    # NOTE: _ensure_public_schema is intentionally NOT called here.
    # The temp file contains only SDE tables; user/auth tables (users,
    # site_admins, user_roles) live in the live DB and must not be overwritten.


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


# ---------------------------------------------------------------------------
# Generic schema-driven inserter
# ---------------------------------------------------------------------------

def _extract_value(col: dict, key: Any, props: dict) -> Any:
    """Extract a single column value from an entry based on schema column def."""
    src = col["source"]
    dtype = col["dtype"]

    if src == "_key":
        return _as_int(key) if dtype == "BIGINT" else str(key) if key is not None else None
    if src == "_payload":
        return _to_json(props)

    raw = props.get(src)

    extract = col.get("extract")
    if extract == "multilang_en":
        return (raw or {}).get("en") if isinstance(raw, dict) else None
    if extract == "json":
        return _to_json(raw)

    if dtype == "BIGINT":
        return _as_int(raw)
    if dtype == "DOUBLE":
        return _as_float(raw)
    if dtype == "BOOLEAN":
        return _as_bool(raw)
    return raw


def _insert_from_schema(
    con: duckdb.DuckDBPyConnection,
    table_def: dict,
    data: Any,
) -> int:
    """Insert data into a table using schema column definitions.

    Handles both dict_of_dicts (FSD) and list_of_dicts (BSD) structures.
    """
    columns = table_def["columns"]
    col_names = [c["name"] for c in columns]
    structure = table_def["structure"]

    if structure == "dict_of_dicts":
        rows = (
            tuple(_extract_value(c, k, v) for c in columns)
            for k, v in (data if isinstance(data, dict) else {}).items()
        )
    else:
        rows = (
            tuple(_extract_value(c, None, entry) for c in columns)
            for entry in (data if isinstance(data, list) else [])
            if isinstance(entry, dict)
        )

    return _copy_rows(con, table_def["table_name"], col_names, rows)


# ---------------------------------------------------------------------------
# Universe dimension inserter
# ---------------------------------------------------------------------------

def _insert_universe(con: duckdb.DuckDBPyConnection, universe_root: Path) -> dict[str, int]:
    inv_names: dict[int, str] = {
        row[0]: row[1]
        for row in con.execute("SELECT item_id, item_name FROM sde_invNames").fetchall()
    }
    region_rows: list[tuple] = []
    constellation_rows: list[tuple] = []
    system_rows: list[tuple] = []
    planet_rows: list[tuple] = []
    moon_rows: list[tuple] = []
    belt_rows: list[tuple] = []
    # Stargates need a two-pass: collect all gate→system mappings first, then
    # resolve destination_system_id from the destination stargate id.
    stargate_rows_partial: list[tuple] = []  # (gate_id, sys_id, type_id, dest_gate_id, x, y, z, payload)
    stargate_to_system: dict[int, int] = {}
    region_dir_to_id: dict[Path, int] = {}
    region_dir_to_space_type: dict[Path, str] = {}
    constellation_dir_to_id: dict[Path, int] = {}

    for region_path in sorted(universe_root.rglob("region.yaml")):
        data = _load_yaml_file(region_path) or {}
        region_dir = region_path.parent
        space_type = region_dir.relative_to(universe_root).parts[0]
        region_id = _as_int(data.get("regionID"))
        region_dir_to_id[region_dir] = region_id or 0
        region_dir_to_space_type[region_dir] = space_type
        x, y, z = _xyz(data.get("center"))
        x_min, y_min, z_min = _xyz(data.get("min"))
        x_max, y_max, z_max = _xyz(data.get("max"))
        region_rows.append((
            region_id, inv_names.get(region_id), space_type,
            _as_int(data.get("factionID")),
            x, y, z, x_min, y_min, z_min, x_max, y_max, z_max, _to_json(data),
        ))

    for constellation_path in sorted(universe_root.rglob("constellation.yaml")):
        data = _load_yaml_file(constellation_path) or {}
        constellation_dir = constellation_path.parent
        region_dir = constellation_dir.parent
        space_type = region_dir_to_space_type.get(region_dir, "unknown")
        constellation_id = _as_int(data.get("constellationID"))
        constellation_dir_to_id[constellation_dir] = constellation_id or 0
        x, y, z = _xyz(data.get("center"))
        x_min, y_min, z_min = _xyz(data.get("min"))
        x_max, y_max, z_max = _xyz(data.get("max"))
        constellation_rows.append((
            constellation_id, inv_names.get(constellation_id), space_type,
            region_dir_to_id.get(region_dir),
            x, y, z, x_min, y_min, z_min, x_max, y_max, z_max, _to_json(data),
        ))

    for system_path in sorted(universe_root.rglob("solarsystem.yaml")):
        data = _load_yaml_file(system_path) or {}
        system_dir = system_path.parent
        constellation_dir = system_dir.parent
        region_dir = constellation_dir.parent
        space_type = region_dir_to_space_type.get(region_dir, "unknown")
        system_id = _as_int(data.get("solarSystemID"))
        constellation_id = constellation_dir_to_id.get(constellation_dir)
        region_id = region_dir_to_id.get(region_dir)
        planets = data.get("planets") or {}
        stargates = data.get("stargates") or {}
        x, y, z = _xyz(data.get("center"))
        x_min, y_min, z_min = _xyz(data.get("min"))
        x_max, y_max, z_max = _xyz(data.get("max"))
        system_rows.append((
            system_id, inv_names.get(system_id), space_type,
            constellation_id, region_id,
            _as_float(data.get("security")), _as_int(data.get("sunTypeID")),
            _as_bool(data.get("border")), _as_bool(data.get("corridor")),
            _as_bool(data.get("fringe")), _as_bool(data.get("hub")),
            _as_bool(data.get("international")), _as_bool(data.get("regional")),
            len(planets), len(stargates),
            x, y, z, x_min, y_min, z_min, x_max, y_max, z_max, _to_json(data),
        ))

        for planet_id_raw, planet_data in planets.items():
            planet_id = _as_int(planet_id_raw)
            px, py, pz = _xyz(planet_data.get("position"))
            p_stats = planet_data.get("statistics") or {}
            planet_rows.append((
                planet_id, system_id, _as_int(planet_data.get("typeID")),
                _as_int(planet_data.get("celestialIndex")),
                px, py, pz,
                _as_float(planet_data.get("radius")),
                _as_float(p_stats.get("density")),
                _as_float(p_stats.get("eccentricity")),
                _as_float(p_stats.get("escapeVelocity")),
                _as_bool(p_stats.get("fragmented")),
                _as_float(p_stats.get("life")),
                _as_bool(p_stats.get("locked")),
                _as_float(p_stats.get("massDust")),
                _as_float(p_stats.get("massGas")),
                _as_float(p_stats.get("orbitPeriod")),
                _as_float(p_stats.get("orbitRadius")),
                _as_float(p_stats.get("pressure")),
                _as_float(p_stats.get("rotationRate")),
                str(p_stats["spectralClass"]) if "spectralClass" in p_stats else None,
                _as_float(p_stats.get("surfaceGravity")),
                _as_float(p_stats.get("temperature")),
                _to_json(planet_data),
            ))
            for moon_id_raw, moon_data in (planet_data.get("moons") or {}).items():
                mx, my, mz = _xyz(moon_data.get("position"))
                m_stats = moon_data.get("statistics") or {}
                moon_rows.append((
                    _as_int(moon_id_raw), system_id, planet_id,
                    _as_int(moon_data.get("typeID")),
                    mx, my, mz,
                    _as_float(moon_data.get("radius")),
                    _as_float(m_stats.get("density")),
                    _as_float(m_stats.get("eccentricity")),
                    _as_float(m_stats.get("escapeVelocity")),
                    _as_bool(m_stats.get("fragmented")),
                    _as_float(m_stats.get("life")),
                    _as_bool(m_stats.get("locked")),
                    _as_float(m_stats.get("massDust")),
                    _as_float(m_stats.get("massGas")),
                    _as_float(m_stats.get("orbitPeriod")),
                    _as_float(m_stats.get("orbitRadius")),
                    _as_float(m_stats.get("pressure")),
                    _as_float(m_stats.get("rotationRate")),
                    str(m_stats["spectralClass"]) if "spectralClass" in m_stats else None,
                    _as_float(m_stats.get("surfaceGravity")),
                    _as_float(m_stats.get("temperature")),
                    _to_json(moon_data),
                ))
            for belt_id_raw, belt_data in (planet_data.get("asteroidBelts") or {}).items():
                bx, by, bz = _xyz(belt_data.get("position"))
                b_stats = belt_data.get("statistics") or {}
                belt_rows.append((
                    _as_int(belt_id_raw), system_id, planet_id,
                    _as_int(belt_data.get("typeID")),
                    bx, by, bz,
                    _as_float(b_stats.get("density")),
                    _as_float(b_stats.get("eccentricity")),
                    _as_float(b_stats.get("escapeVelocity")),
                    _as_bool(b_stats.get("fragmented")),
                    _as_float(b_stats.get("life")),
                    _as_bool(b_stats.get("locked")),
                    _as_float(b_stats.get("massDust")),
                    _as_float(b_stats.get("massGas")),
                    _as_float(b_stats.get("orbitPeriod")),
                    _as_float(b_stats.get("orbitRadius")),
                    _as_float(b_stats.get("pressure")),
                    _as_float(b_stats.get("rotationRate")),
                    str(b_stats["spectralClass"]) if "spectralClass" in b_stats else None,
                    _as_float(b_stats.get("surfaceGravity")),
                    _as_float(b_stats.get("temperature")),
                    _to_json(belt_data),
                ))

        for gate_id_raw, gate_data in stargates.items():
            gate_id = _as_int(gate_id_raw)
            gx, gy, gz = _xyz(gate_data.get("position"))
            stargate_rows_partial.append((
                gate_id, system_id, _as_int(gate_data.get("typeID")),
                _as_int(gate_data.get("destination")), gx, gy, gz, _to_json(gate_data),
            ))
            stargate_to_system[gate_id] = system_id

    # Resolve destination_system_id now that all gates are collected
    stargate_rows = [
        (gate_id, sys_id, type_id, dest_gate_id,
         stargate_to_system.get(dest_gate_id) if dest_gate_id is not None else None,
         gx, gy, gz, payload)
        for gate_id, sys_id, type_id, dest_gate_id, gx, gy, gz, payload in stargate_rows_partial
    ]

    return {
        "sde_regions": _copy_rows(con, "sde_regions",
            ["region_id", "region_name", "space_type", "faction_id", "x", "y", "z",
             "x_min", "y_min", "z_min", "x_max", "y_max", "z_max", "payload_json"],
            region_rows),
        "sde_constellations": _copy_rows(con, "sde_constellations",
            ["constellation_id", "constellation_name", "space_type", "region_id", "x", "y", "z",
             "x_min", "y_min", "z_min", "x_max", "y_max", "z_max", "payload_json"],
            constellation_rows),
        "sde_systems": _copy_rows(con, "sde_systems",
            ["system_id", "system_name", "space_type", "constellation_id", "region_id",
             "security", "sun_type_id", "border", "corridor", "fringe",
             "hub", "international", "regional", "planet_count", "stargate_count",
             "x", "y", "z", "x_min", "y_min", "z_min", "x_max", "y_max", "z_max", "payload_json"],
            system_rows),
        "sde_planets": _copy_rows(con, "sde_planets",
            ["planet_id", "system_id", "type_id", "celestial_index",
             "x", "y", "z", "radius",
             "density", "eccentricity", "escape_velocity", "fragmented",
             "life", "locked", "mass_dust", "mass_gas",
             "orbit_period", "orbit_radius", "pressure", "rotation_rate",
             "spectral_class", "surface_gravity", "temperature",
             "payload_json"],
            planet_rows),
        "sde_moons": _copy_rows(con, "sde_moons",
            ["moon_id", "system_id", "planet_id", "type_id",
             "x", "y", "z", "radius",
             "density", "eccentricity", "escape_velocity", "fragmented",
             "life", "locked", "mass_dust", "mass_gas",
             "orbit_period", "orbit_radius", "pressure", "rotation_rate",
             "spectral_class", "surface_gravity", "temperature",
             "payload_json"],
            moon_rows),
        "sde_asteroidBelts": _copy_rows(con, "sde_asteroidBelts",
            ["belt_id", "system_id", "planet_id", "type_id",
             "x", "y", "z",
             "density", "eccentricity", "escape_velocity", "fragmented",
             "life", "locked", "mass_dust", "mass_gas",
             "orbit_period", "orbit_radius", "pressure", "rotation_rate",
             "spectral_class", "surface_gravity", "temperature",
             "payload_json"],
            belt_rows),
        "sde_stargates": _copy_rows(con, "sde_stargates",
            ["stargate_id", "system_id", "type_id", "destination_stargate_id",
             "destination_system_id", "x", "y", "z", "payload_json"],
            stargate_rows),
    }


# ---------------------------------------------------------------------------
# Warehouse validation and atomic file replace
# ---------------------------------------------------------------------------

def _validate_warehouse(con: duckdb.DuckDBPyConnection) -> None:
    required_tables = {
        "sde_types": 1, "sde_groups": 1, "sde_categories": 1,
        "sde_marketGroups": 1, "sde_regions": 1, "sde_constellations": 1,
        "sde_systems": 1, "sde_staStations": 1,
    }
    for table_name, minimum in required_tables.items():
        row = _query_one(con, f'SELECT COUNT(*) AS row_count FROM "{table_name}"')
        count = int((row or {}).get("row_count") or 0)
        if count <= minimum:
            raise RuntimeError(
                f"Warehouse validation failed for {table_name}: expected > {minimum}, found {count}"
            )


def _merge_sde_to_live(temp_path: Path, target_path: Path) -> None:
    """Merge all tables from the freshly-built temp warehouse into the live DB.

    Only tables that exist in *temp_path* are replaced in *target_path*.  All
    other tables in the live DB (users, market_orders, structures, scheduler
    jobs, ESI cache, etc.) are left completely untouched.

    The merge is a single BEGIN/COMMIT transaction — on any failure the live DB
    rolls back to its prior state and the temp file is left on disk for
    debugging.  The writer thread is paused for the duration so it does not
    hold the Windows file lock on *target_path*.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)

    from core.db.writer import is_running, stop_writer, start_writer as _start_writer

    writer_was_running = is_running()
    if writer_was_running:
        stop_writer(timeout=30.0)

    try:
        live_con = connect(target_path, read_only=False)
        try:
            live_con.execute(f"ATTACH '{temp_path}' AS sde_tmp (READ_ONLY)")
            try:
                rows = live_con.execute(
                    "SELECT table_name FROM duckdb_tables() "
                    "WHERE database_name = 'sde_tmp' AND schema_name = 'main' ORDER BY table_name"
                ).fetchall()
                table_names = [r[0] for r in rows]
                logger.info("[SDE Merge] merging %d tables into live DB", len(table_names))

                live_con.execute("BEGIN")
                try:
                    for tname in table_names:
                        live_con.execute(f'DROP TABLE IF EXISTS "{tname}"')
                        live_con.execute(f'CREATE TABLE "{tname}" AS SELECT * FROM sde_tmp."{tname}"')
                    live_con.execute("COMMIT")
                except Exception:
                    try:
                        live_con.execute("ROLLBACK")
                    except Exception:
                        pass
                    raise
            finally:
                try:
                    live_con.execute("DETACH sde_tmp")
                except Exception:
                    pass
        finally:
            live_con.close()
    finally:
        if writer_was_running:
            _start_writer()

    # Clean up the temp file now that the merge succeeded.
    try:
        temp_path.unlink()
    except Exception:
        pass

    logger.info("[SDE Merge] complete — live DB updated in place")


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
    universe_counts = {"sde_regions": 0, "sde_constellations": 0, "sde_systems": 0}

    logger.info("Building SDE warehouse at %s", target_path)
    con = connect(temp_path, read_only=False)
    try:
        _bootstrap_schema(con)

        # Build schema lookup: source_file → list[table_def]
        schema = _load_sde_schema()
        schema_by_source: dict[str, list[dict]] = {}
        for table_def in schema["tables"]:
            src = table_def["source_file"]
            schema_by_source.setdefault(src, []).append(table_def)

        fsd_paths = sorted((source_root_path / "fsd").glob("*.yaml"))
        bsd_paths = sorted((source_root_path / "bsd").glob("*.yaml"))
        total_steps = len(fsd_paths) + len(bsd_paths) + (1 if (source_root_path / "universe").exists() else 0)
        current_step = 0

        for path in fsd_paths:
            current_step += 1
            logger.info("[SDE Warehouse] %s/%s loading fsd/%s", current_step, total_steps, path.name)
            data = _load_yaml_file(path) or {}
            source_key = f"fsd/{path.name}"
            for tdef in schema_by_source.get(source_key, []):
                count = _insert_from_schema(con, tdef, data)
                _record_dataset(dataset_stats, "sde", path.stem, tdef["table_name"], str(path), count)

        for path in bsd_paths:
            current_step += 1
            logger.info("[SDE Warehouse] %s/%s loading bsd/%s", current_step, total_steps, path.name)
            data = _load_yaml_file(path) or []
            source_key = f"bsd/{path.name}"
            for tdef in schema_by_source.get(source_key, []):
                count = _insert_from_schema(con, tdef, data)
                _record_dataset(dataset_stats, "sde", path.stem, tdef["table_name"], str(path), count)

        universe_root = source_root_path / "universe"
        if universe_root.exists():
            current_step += 1
            logger.info("%s/%s loading universe", current_step, total_steps)
            logger.info("building universe dimensions from %s", universe_root)
            universe_counts = _insert_universe(con, universe_root)
            for tbl, rc in universe_counts.items():
                _record_dataset(dataset_stats, "sde", tbl.removeprefix("sde_"), tbl, str(universe_root), rc)

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
                universe_counts.get("sde_regions", 0),
                universe_counts.get("sde_constellations", 0),
                universe_counts.get("sde_systems", 0), str(target_path),
            ],
        )
        con.close()
        _merge_sde_to_live(temp_path, target_path)
    except Exception:
        try:
            con.close()
        finally:
            if temp_path.exists():
                temp_path.unlink()
        logger.error("build failed for %s", target_path)
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
        from core.db.public import sync_esi_registry_to_warehouse
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

