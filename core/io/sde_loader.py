"""SDE pipeline: download → unzip → build DuckDB warehouse.

Merged from workers/publicData/SDEBootstrap.py + SDELoader.py.
Migrated from YAML to JSONL format for faster loading.

Entry points:
    update_sde()               — full pipeline: download, extract, build
    rebuild_sde_warehouse()    — rebuild from existing _sde/ files
    build_sde_warehouse()      — low-level: parse JSONL → DuckDB
    update_esi_spec()          — refresh ESI OpenAPI registry
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

import duckdb
import requests

from core.io.public import (
    _as_float,
    _ensure_registry_schema,
    _query_one,
    _to_json,
    _utc_now,
    connect,
    get_database_path,
    get_sde_root,
    get_supported_languages,
    get_warehouse_status,
    compute_file_sha256,
)
from core.esi.registry import refresh_esi_spec_registry
from core.io.sde import refresh_all_caches

logger = logging.getLogger(__name__)

SDE_URL = "https://developers.eveonline.com/static-data/eve-online-static-data-latest-jsonl.zip"
SDE_BUILD_URL = "https://developers.eveonline.com/static-data/tranquility/latest.jsonl"
SDE_PATH = Path(os.getenv("SDE_PATH", "_sde"))
SDE_ZIP_PATH = Path("_sde_tmp.zip")


# ---------------------------------------------------------------------------
# SDE currency check — build number comparison via CCP metadata endpoint
# ---------------------------------------------------------------------------

def warehouse_exists() -> bool:
    """Return True if the DuckDB warehouse has an sde_manifest table."""
    from core.io.public import warehouse_exists as _wh_exists
    return _wh_exists()


def _fetch_remote_build_number(url: str = SDE_BUILD_URL) -> int | None:
    """Fetch the current SDE build number from the CCP metadata endpoint."""
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        for line in resp.text.strip().splitlines():
            record = json.loads(line)
            if record.get("_key") == "sde":
                return int(record["buildNumber"])
    except Exception:
        return None
    return None


def check_sde_currency() -> dict:
    """Check whether the local SDE warehouse is still current.

    Fetches the latest SDE build number from the CCP metadata endpoint and
    compares it to the ``sde_version`` stored in ``sde_manifest``.

    Returns
    -------
    dict
        ``{"current": bool, "local_build": str | None, "remote_build": int | None,
           "error": str | None}``
    """
    local_build = None
    try:
        con = connect()
        try:
            row = con.execute(
                "SELECT sde_version FROM sde_manifest ORDER BY manifest_id DESC LIMIT 1"
            ).fetchone()
            local_build = row[0] if row else None
        finally:
            con.close()
    except Exception:
        pass  # warehouse may not exist yet

    remote_build = _fetch_remote_build_number()
    if remote_build is None:
        return {
            "current": True,  # assume current if we can't reach CCP
            "local_build": local_build,
            "remote_build": None,
            "error": "Could not fetch remote SDE build number",
        }

    if local_build and str(remote_build) == str(local_build):
        return {"current": True, "local_build": local_build, "remote_build": remote_build, "error": None}

    return {"current": False, "local_build": local_build, "remote_build": remote_build, "error": None}

# ---------------------------------------------------------------------------
# Small helpers (build-time only)
# ---------------------------------------------------------------------------

def _supported_languages() -> list[str]:
    raw = os.getenv("SUPPORTED_LANGUAGES", "en")
    return [item.strip() for item in raw.split(",") if item.strip()]


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
# DuckDB-native NDJSON insert helpers
# ---------------------------------------------------------------------------

def _sql_col_expr(col: dict, raw_col_names: set) -> str:
    """Return a SQL SELECT expression mapping a raw NDJSON column to a schema column.

    col           — one entry from sde_schema.json "columns" list
    raw_col_names — column names detected by DuckDB in the raw NDJSON temp table
    """
    out_q = f'"{col["name"]}"'
    src = col["source"]
    dtype = col["dtype"]
    extract = col.get("extract")

    if src == "_key":
        if "_key" not in raw_col_names:
            return f"NULL AS {out_q}"
        if dtype == "BIGINT":
            return f'TRY_CAST("_key" AS BIGINT) AS {out_q}'
        return f'TRY_CAST("_key" AS VARCHAR) AS {out_q}'

    if src == "_payload":
        # Handled by the caller via _payload_sql(); should not reach here.
        return f"NULL AS {out_q}"

    if src not in raw_col_names:
        return f"NULL AS {out_q}"

    src_q = f'"{src}"'

    if extract == "multilang_en":
        # DuckDB auto_detect reads multi-lang dicts as STRUCT; use to_json for safe .en access.
        return f"TRY_CAST(json_extract_string(to_json({src_q}), '$.en') AS VARCHAR) AS {out_q}"

    if extract == "json":
        return f"CASE WHEN {src_q} IS NULL THEN NULL ELSE to_json({src_q})::VARCHAR END AS {out_q}"

    if dtype == "BIGINT":
        return f"TRY_CAST({src_q} AS BIGINT) AS {out_q}"
    if dtype == "DOUBLE":
        return f"TRY_CAST({src_q} AS DOUBLE) AS {out_q}"
    if dtype == "BOOLEAN":
        return f"TRY_CAST({src_q} AS BOOLEAN) AS {out_q}"
    return f"TRY_CAST({src_q} AS VARCHAR) AS {out_q}"


def _payload_sql(payload_fields: list, out_name: str) -> str:
    """Build a SQL expression for a _payload column (full row as JSON, excluding _key)."""
    out_q = f'"{out_name}"'
    if not payload_fields:
        return f"NULL AS {out_q}"
    pairs = ", ".join(f'"{f}" := "{f}"' for f in payload_fields)
    return f"to_json(struct_pack({pairs}))::VARCHAR AS {out_q}"


def _ndjson_insert(
    con: duckdb.DuckDBPyConnection,
    ndjson_path: Path,
    table_defs: list,
    dataset_stats: list,
) -> None:
    """Load a JSONL file once with DuckDB's C++ parser and INSERT into all mapped schema tables."""
    safe_stem = ndjson_path.stem.replace("-", "_").replace(".", "_").replace(" ", "_")
    raw_table = f"_ndjson_{safe_stem}"
    escaped_path = str(ndjson_path).replace("\\", "/")
    try:
        con.execute(
            f'CREATE TEMP TABLE "{raw_table}" AS '
            f"SELECT * FROM read_ndjson('{escaped_path}', auto_detect=TRUE, ignore_errors=TRUE)"
        )
        raw_col_names = {r[0] for r in con.execute(f'DESCRIBE "{raw_table}"').fetchall()}
        for tdef in table_defs:
            columns = tdef["columns"]
            table_name = tdef["table_name"]
            payload_col = next((c for c in columns if c["source"] == "_payload"), None)
            payload_fields = sorted(raw_col_names - {"_key"}) if payload_col else []
            select_exprs = []
            for col in columns:
                if col["source"] == "_payload":
                    select_exprs.append(_payload_sql(payload_fields, col["name"]))
                else:
                    select_exprs.append(_sql_col_expr(col, raw_col_names))
            sel = ", ".join(select_exprs)
            con.execute(f'INSERT INTO "{table_name}" SELECT {sel} FROM "{raw_table}"')
            count = con.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
            _record_dataset(dataset_stats, "sde", ndjson_path.stem, table_name, str(ndjson_path), count)
    finally:
        con.execute(f'DROP TABLE IF EXISTS "{raw_table}"')


# ---------------------------------------------------------------------------
# SDE table DDL (ensure_tables equivalent — creates all SDE dimension/fact tables)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# SDE schema loading + schema-driven DDL
# ---------------------------------------------------------------------------

_SDE_SCHEMA_PATH = Path("core/io/generated/sde_schema.json")


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
# Warehouse validation and atomic file replace
# ---------------------------------------------------------------------------

def _validate_warehouse(con: duckdb.DuckDBPyConnection) -> None:
    required_tables = {
        "sde_types": 1, "sde_groups": 1, "sde_categories": 1,
        "sde_marketGroups": 1, "sde_mapRegions": 1, "sde_mapConstellations": 1,
        "sde_mapSolarSystems": 1, "sde_npcStations": 1,
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

    from core.io.writer import is_running, stop_writer, start_writer as _start_writer

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
    build_number = _fetch_remote_build_number()
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
                "build_number": str(build_number) if build_number else None,
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
    # JSONL zip may contain a nested directory — flatten if needed
    subdirs = [d for d in extract_to.iterdir() if d.is_dir()]
    jsonl_at_root = list(extract_to.glob("*.jsonl"))
    if not jsonl_at_root and len(subdirs) == 1:
        # All files are inside a single sub-directory — move them up
        nested = subdirs[0]
        for item in nested.iterdir():
            item.rename(extract_to / item.name)
        nested.rmdir()
    logger.info("SDE extraction complete.")


def cleanup(zip_path: Path = SDE_ZIP_PATH) -> None:
    if zip_path.exists():
        zip_path.unlink()
        logger.info("Removed temporary SDE archive %s", zip_path)


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
    build_number: str | None = None,
) -> dict:
    """Parse SDE JSONL files and write a fresh DuckDB warehouse."""
    target_path = Path(database_file) if database_file else get_database_path()
    source_root_path = Path(source_root) if source_root else get_sde_root()
    supported_languages = supported_languages or get_supported_languages()
    temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    if temp_path.exists():
        temp_path.unlink()

    build_started = _utc_now()
    effective_source_hash = source_hash or compute_source_tree_hash(source_root_path)
    sde_version = build_number or source_last_modified or source_etag or effective_source_hash[:12]
    dataset_stats: list[dict] = []

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

        jsonl_paths = sorted(source_root_path.glob("*.jsonl"))
        total_steps = len(jsonl_paths)
        current_step = 0

        for path in jsonl_paths:
            current_step += 1
            logger.info("[SDE Warehouse] %s/%s loading %s", current_step, total_steps, path.name)
            source_tables = schema_by_source.get(path.name, [])
            if source_tables:
                _ndjson_insert(con, path, source_tables, dataset_stats)

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
                len(jsonl_paths), 0,  # fsd_file_count repurposed as jsonl_file_count; bsd=0
                0, 0, 0, str(target_path),  # universe counts no longer tracked separately
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
        build_number=source_meta.get("build_number"),
    )
    try:
        from core.io.public import sync_esi_registry_to_warehouse
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

