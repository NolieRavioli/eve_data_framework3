"""SDE schema codegen — introspect ``_sde/`` YAML files and emit a JSON schema.

The generated schema (``core/db/generated/sde_schema.json``) drives the SDE
warehouse builder in ``core/db/sde_loader.py``.  All SDE tables use the
``sde_{yaml_stem}`` naming convention.

Entry point
-----------
  generate_sde_schema(source_root=None, output_path=None) -> dict

CLI (via build.py)::

    python build.py --sde-schema
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

_DEFAULT_SDE_ROOT = Path(os.getenv("SDE_PATH", "_sde"))
_DEFAULT_OUTPUT = Path("core/db/generated/sde_schema.json")

# ---------------------------------------------------------------------------
# camelCase → snake_case conversion
# ---------------------------------------------------------------------------

_CAMEL_RE_1 = re.compile(r"([A-Z]+)([A-Z][a-z])")  # handle ABCDef → ABC_Def
_CAMEL_RE_2 = re.compile(r"([a-z0-9])([A-Z])")     # handle abcDef → abc_Def


def _camel_to_snake(name: str) -> str:
    """Convert camelCase / PascalCase to snake_case.

    Handles acronyms: ``graphicIDs`` → ``graphic_ids``, ``npcCorporations`` → ``npc_corporations``.
    """
    s = _CAMEL_RE_1.sub(r"\1_\2", name)
    s = _CAMEL_RE_2.sub(r"\1_\2", s)
    s = s.lower()
    # Fix common multi-letter abbreviations that split incorrectly
    s = s.replace("_i_ds", "_ids")
    return s


# ---------------------------------------------------------------------------
# Table naming: all SDE tables use sde_{yaml_stem} prefix
# ---------------------------------------------------------------------------

# Primary key column name overrides (when auto-detection isn't ideal).
_PK_NAME_OVERRIDES: dict[str, str] = {
    "sde_types": "type_id",
    "sde_groups": "group_id",
    "sde_categories": "category_id",
    "sde_marketGroups": "market_group_id",
    "sde_staStations": "station_id",
    "sde_invItems": "item_id",
    "sde_invNames": "item_id",
    "sde_invPositions": "item_id",
    "sde_invFlags": "flag_id",
    "sde_invUniqueNames": "item_id",
    "sde_blueprints": "blueprint_type_id",
    "sde_typeMaterials": "type_id",
    "sde_typeDogma": "type_id",
}


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

def _yaml_loader():
    return getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.load(fh, Loader=_yaml_loader())


# ---------------------------------------------------------------------------
# Type inference
# ---------------------------------------------------------------------------

_SUPPORTED_LANGS = {"en", "de", "es", "fr", "ja", "ko", "ru", "zh"}


def _is_multilang(sample_values: list[Any]) -> bool:
    """Return True if the values look like multilang dicts ({en: ..., de: ...})."""
    for v in sample_values:
        if not isinstance(v, dict):
            return False
        keys = set(v.keys())
        if not keys:
            continue
        if keys <= _SUPPORTED_LANGS:
            return True
    return False


def _infer_dtype(values: list[Any]) -> str:
    """Infer DuckDB column type from observed Python values."""
    types_seen: set[str] = set()
    for v in values:
        if v is None:
            continue
        t = type(v).__name__
        types_seen.add(t)

    if not types_seen:
        return "VARCHAR"

    # Single type
    if types_seen == {"int"}:
        return "BIGINT"
    if types_seen == {"float"}:
        return "DOUBLE"
    if types_seen == {"bool"}:
        return "BOOLEAN"
    if types_seen == {"str"}:
        return "VARCHAR"
    # Mixed int/float → DOUBLE
    if types_seen <= {"int", "float"}:
        return "DOUBLE"
    # Mixed int/bool → BIGINT
    if types_seen <= {"int", "bool"}:
        return "BIGINT"
    # dict or list → VARCHAR (JSON-encoded)
    if types_seen & {"dict", "list"}:
        return "VARCHAR"
    return "VARCHAR"


# ---------------------------------------------------------------------------
# Schema introspection
# ---------------------------------------------------------------------------

def _introspect_entries(entries: list[dict], max_sample: int = 5000) -> list[dict]:
    """Introspect a list of entry dicts and return column definitions.

    Each returned dict has: name, dtype, source, nullable, extract (optional).
    """
    # Collect all keys and sample values
    key_values: dict[str, list[Any]] = {}
    sampled = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for k, v in entry.items():
            key_values.setdefault(k, []).append(v)
        sampled += 1
        if sampled >= max_sample:
            break

    total_entries = len(entries)
    columns: list[dict] = []

    for key in sorted(key_values.keys()):
        values = key_values[key]
        non_none = [v for v in values if v is not None][:200]
        nullable = len(values) < total_entries or any(v is None for v in values)

        # Check for multilang dict
        dict_samples = [v for v in non_none if isinstance(v, dict)]
        if dict_samples and _is_multilang(dict_samples):
            # CCP uses *ID suffix for translated string dicts (nameID, descriptionID).
            # Strip the _id suffix for readability: nameID → name_en, not name_id_en.
            base = _camel_to_snake(key)
            if base.endswith("_id"):
                base = base[:-3]
            col_name = base + "_en"
            columns.append({
                "name": col_name,
                "dtype": "VARCHAR",
                "source": key,
                "extract": "multilang_en",
                "nullable": True,
            })
            continue

        dtype = _infer_dtype(non_none)

        # If complex type (dict/list), store as JSON
        extract = None
        col_name = _camel_to_snake(key)
        if dtype == "VARCHAR" and any(isinstance(v, (dict, list)) for v in non_none):
            extract = "json"
            if not col_name.endswith("_json"):
                col_name = col_name + "_json"

        columns.append({
            "name": col_name,
            "dtype": dtype,
            "source": key,
            "nullable": nullable,
            **({"extract": extract} if extract else {}),
        })

    return columns


def _detect_pk_for_list(columns: list[dict], stem: str) -> str | None:
    """Detect the primary key column for a list-of-dicts (BSD) file."""
    # Look for columns ending in _id that match common patterns
    id_cols = [c for c in columns if c["name"].endswith("_id") and c["dtype"] == "BIGINT"]
    if not id_cols:
        return None

    # Prefer columns whose name matches known patterns
    stem_snake = _camel_to_snake(stem)
    for col in id_cols:
        if col["name"] == f"{stem_snake}_id":
            return col["name"]

    # Common PK names
    for preferred in ("item_id", "station_id", "flag_id", "type_id"):
        for col in id_cols:
            if col["name"] == preferred:
                return col["name"]

    # Just pick the first ID column
    return id_cols[0]["name"] if id_cols else None


def _build_table_def(
    layer: str,
    stem: str,
    source_file: str,
    data: Any,
) -> dict:
    """Build a single table schema definition from YAML data."""
    table_name = f"sde_{stem}"

    structure = "dict_of_dicts" if isinstance(data, dict) else "list_of_dicts"
    custom_handler = False

    # Collect entries for introspection
    if isinstance(data, dict):
        entries = list(data.values())
    elif isinstance(data, list):
        entries = data
    else:
        entries = []

    if not entries:
        return {
            "table_name": table_name,
            "source_file": source_file,
            "layer": layer,
            "structure": structure,
            "custom_handler": custom_handler,
            "pk_column": None,
            "columns": [{"name": "payload_json", "dtype": "VARCHAR", "source": "_payload"}],
        }

    columns = _introspect_entries(entries)

    # Determine PK
    pk_name = _PK_NAME_OVERRIDES.get(table_name)
    if pk_name is None and structure == "dict_of_dicts":
        # For dict-of-dicts, the dict key is the PK. Derive name from table.
        # e.g., sde_agents → agent_id, sde_types → type_id
        base = _camel_to_snake(table_name.removeprefix("sde_"))
        # Singularize simple plurals
        if base.endswith("ies"):
            base = base[:-3] + "y"
        elif base.endswith("ses"):
            base = base[:-2]
        elif base.endswith("s") and not base.endswith("ss"):
            base = base[:-1]
        pk_name = f"{base}_id"
    elif pk_name is None and structure == "list_of_dicts":
        pk_name = _detect_pk_for_list(columns, stem)

    # Build final column list
    final_columns: list[dict] = []

    # Add PK column for dict-of-dicts (the dict key)
    if structure == "dict_of_dicts" and pk_name:
        # Detect key type: sample first few keys
        sample_keys = list(data.keys())[:20] if isinstance(data, dict) else []
        all_int = all(isinstance(k, int) or (isinstance(k, str) and k.isdigit()) for k in sample_keys) if sample_keys else True
        pk_dtype = "BIGINT" if all_int else "VARCHAR"
        final_columns.append({
            "name": pk_name,
            "dtype": pk_dtype,
            "source": "_key",
            "pk": True,
            "nullable": False,
        })

    # Add introspected columns, marking PK for list-of-dicts
    for col in columns:
        # Skip columns that duplicate the PK already added from _key
        if structure == "dict_of_dicts" and pk_name and col["name"] == pk_name:
            continue
        entry = dict(col)
        if structure == "list_of_dicts" and pk_name and col["name"] == pk_name:
            entry["pk"] = True
            entry["nullable"] = False
        final_columns.append(entry)

    # Add payload_json at the end
    final_columns.append({
        "name": "payload_json",
        "dtype": "VARCHAR",
        "source": "_payload",
        "nullable": True,
    })

    return {
        "table_name": table_name,
        "source_file": source_file,
        "layer": layer,
        "structure": structure,
        "custom_handler": custom_handler,
        "pk_column": pk_name,
        "columns": final_columns,
    }





# ---------------------------------------------------------------------------
# Universe tables (schema-only — insertion stays custom)
# ---------------------------------------------------------------------------

def _universe_tables() -> list[dict]:
    """Return schema defs for universe dimension tables (DDL only)."""
    return [
        {
            "table_name": "sde_regions",
            "source_file": "universe/",
            "layer": "universe",
            "structure": "custom",
            "custom_handler": True,
            "pk_column": "region_id",
            "columns": [
                {"name": "region_id", "dtype": "BIGINT", "source": "regionID", "pk": True, "nullable": False},
                {"name": "region_name", "dtype": "VARCHAR", "source": "_inv_name", "nullable": True},
                {"name": "space_type", "dtype": "VARCHAR", "source": "_space_type", "nullable": False},
                {"name": "faction_id", "dtype": "BIGINT", "source": "factionID", "nullable": True},
                {"name": "x", "dtype": "DOUBLE", "source": "center.x", "nullable": True},
                {"name": "y", "dtype": "DOUBLE", "source": "center.y", "nullable": True},
                {"name": "z", "dtype": "DOUBLE", "source": "center.z", "nullable": True},
                {"name": "x_min", "dtype": "DOUBLE", "source": "min.x", "nullable": True},
                {"name": "y_min", "dtype": "DOUBLE", "source": "min.y", "nullable": True},
                {"name": "z_min", "dtype": "DOUBLE", "source": "min.z", "nullable": True},
                {"name": "x_max", "dtype": "DOUBLE", "source": "max.x", "nullable": True},
                {"name": "y_max", "dtype": "DOUBLE", "source": "max.y", "nullable": True},
                {"name": "z_max", "dtype": "DOUBLE", "source": "max.z", "nullable": True},
                {"name": "payload_json", "dtype": "VARCHAR", "source": "_payload", "nullable": True},
            ],
        },
        {
            "table_name": "sde_constellations",
            "source_file": "universe/",
            "layer": "universe",
            "structure": "custom",
            "custom_handler": True,
            "pk_column": "constellation_id",
            "columns": [
                {"name": "constellation_id", "dtype": "BIGINT", "source": "constellationID", "pk": True, "nullable": False},
                {"name": "constellation_name", "dtype": "VARCHAR", "source": "_inv_name", "nullable": True},
                {"name": "space_type", "dtype": "VARCHAR", "source": "_space_type", "nullable": False},
                {"name": "region_id", "dtype": "BIGINT", "source": "_parent_region", "nullable": True},
                {"name": "x", "dtype": "DOUBLE", "source": "center.x", "nullable": True},
                {"name": "y", "dtype": "DOUBLE", "source": "center.y", "nullable": True},
                {"name": "z", "dtype": "DOUBLE", "source": "center.z", "nullable": True},
                {"name": "x_min", "dtype": "DOUBLE", "source": "min.x", "nullable": True},
                {"name": "y_min", "dtype": "DOUBLE", "source": "min.y", "nullable": True},
                {"name": "z_min", "dtype": "DOUBLE", "source": "min.z", "nullable": True},
                {"name": "x_max", "dtype": "DOUBLE", "source": "max.x", "nullable": True},
                {"name": "y_max", "dtype": "DOUBLE", "source": "max.y", "nullable": True},
                {"name": "z_max", "dtype": "DOUBLE", "source": "max.z", "nullable": True},
                {"name": "payload_json", "dtype": "VARCHAR", "source": "_payload", "nullable": True},
            ],
        },
        {
            "table_name": "sde_systems",
            "source_file": "universe/",
            "layer": "universe",
            "structure": "custom",
            "custom_handler": True,
            "pk_column": "system_id",
            "columns": [
                {"name": "system_id", "dtype": "BIGINT", "source": "solarSystemID", "pk": True, "nullable": False},
                {"name": "system_name", "dtype": "VARCHAR", "source": "_inv_name", "nullable": True},
                {"name": "space_type", "dtype": "VARCHAR", "source": "_space_type", "nullable": False},
                {"name": "constellation_id", "dtype": "BIGINT", "source": "_parent_constellation", "nullable": True},
                {"name": "region_id", "dtype": "BIGINT", "source": "_parent_region", "nullable": True},
                {"name": "security", "dtype": "DOUBLE", "source": "security", "nullable": True},
                {"name": "sun_type_id", "dtype": "BIGINT", "source": "sunTypeID", "nullable": True},
                {"name": "border", "dtype": "BOOLEAN", "source": "border", "nullable": True},
                {"name": "corridor", "dtype": "BOOLEAN", "source": "corridor", "nullable": True},
                {"name": "fringe", "dtype": "BOOLEAN", "source": "fringe", "nullable": True},
                {"name": "hub", "dtype": "BOOLEAN", "source": "hub", "nullable": True},
                {"name": "international", "dtype": "BOOLEAN", "source": "international", "nullable": True},
                {"name": "regional", "dtype": "BOOLEAN", "source": "regional", "nullable": True},
                {"name": "planet_count", "dtype": "BIGINT", "source": "_computed", "nullable": True},
                {"name": "stargate_count", "dtype": "BIGINT", "source": "_computed", "nullable": True},
                {"name": "x", "dtype": "DOUBLE", "source": "center.x", "nullable": True},
                {"name": "y", "dtype": "DOUBLE", "source": "center.y", "nullable": True},
                {"name": "z", "dtype": "DOUBLE", "source": "center.z", "nullable": True},
                {"name": "x_min", "dtype": "DOUBLE", "source": "min.x", "nullable": True},
                {"name": "y_min", "dtype": "DOUBLE", "source": "min.y", "nullable": True},
                {"name": "z_min", "dtype": "DOUBLE", "source": "min.z", "nullable": True},
                {"name": "x_max", "dtype": "DOUBLE", "source": "max.x", "nullable": True},
                {"name": "y_max", "dtype": "DOUBLE", "source": "max.y", "nullable": True},
                {"name": "z_max", "dtype": "DOUBLE", "source": "max.z", "nullable": True},
                {"name": "payload_json", "dtype": "VARCHAR", "source": "_payload", "nullable": True},
            ],
        },
    ]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_sde_schema(
    source_root: str | Path | None = None,
    output_path: str | Path | None = None,
) -> dict:
    """Introspect SDE YAML files and write ``sde_schema.json``.

    Returns a summary dict with ``table_count``, ``output_path``, etc.
    """
    root = Path(source_root) if source_root else _DEFAULT_SDE_ROOT
    out = Path(output_path) if output_path else _DEFAULT_OUTPUT

    fsd_dir = root / "fsd"
    bsd_dir = root / "bsd"

    if not fsd_dir.exists():
        raise FileNotFoundError(f"SDE fsd directory not found: {fsd_dir}")

    tables: list[dict] = []

    # ── FSD files ──────────────────────────────────────────────────────────
    fsd_files = sorted(fsd_dir.glob("*.yaml"))
    for path in fsd_files:
        stem = path.stem
        logger.info("Introspecting fsd/%s.yaml", stem)
        data = _load_yaml(path)
        if data is None:
            continue
        table_def = _build_table_def("fsd", stem, f"fsd/{path.name}", data)
        tables.append(table_def)

    # ── BSD files ──────────────────────────────────────────────────────────
    if bsd_dir.exists():
        bsd_files = sorted(bsd_dir.glob("*.yaml"))
        for path in bsd_files:
            stem = path.stem
            logger.info("Introspecting bsd/%s.yaml", stem)
            data = _load_yaml(path)
            if data is None:
                continue
            table_def = _build_table_def("bsd", stem, f"bsd/{path.name}", data)
            tables.append(table_def)

    # ── Universe tables (static schema, custom handler) ────────────────────
    universe_dir = root / "universe"
    if universe_dir.exists():
        tables.extend(_universe_tables())

    # ── Write schema JSON ──────────────────────────────────────────────────
    schema = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_root": str(root),
        "table_count": len(tables),
        "tables": tables,
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(schema, fh, indent=2, ensure_ascii=False)

    logger.info("Wrote %d table definitions to %s", len(tables), out)

    return {
        "table_count": len(tables),
        "fsd_tables": sum(1 for t in tables if t["layer"] == "fsd"),
        "bsd_tables": sum(1 for t in tables if t["layer"] == "bsd"),
        "universe_tables": sum(1 for t in tables if t["layer"] == "universe"),
        "output_path": str(out),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = generate_sde_schema()
    print(json.dumps(result, indent=2))
