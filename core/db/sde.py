"""DuckDB-backed SDE facade with YAML fallback.

The public helper surface stays stable for the rest of the app, but the primary
backend is the persisted `_publicData/public.duckdb` warehouse. When that file is
missing, helpers fall back to direct YAML reads from `_sde`.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml

from core.db import public as sde_store

logger = logging.getLogger(__name__)

_SECTION_DEFAULTS: dict[str, bool] = {
    "types": True,
    "groups": True,
    "categories": True,
    "market_groups": True,
    "universe": True,
    "blueprints": False,
    "type_materials": False,
    "type_dogma": False,
}

_startup_cfg: dict[str, bool] = dict(_SECTION_DEFAULTS)
_database_path: Path | None = None

_type_id_to_name: dict[int, str] | None = None
_name_to_type_id: dict[str, int] | None = None
_type_to_group: dict[int, int | None] | None = None
_type_to_market_group: dict[int, int | None] | None = None

_groups: dict[int, dict] | None = None
_categories: dict[int, str] | None = None

_market_flat: dict[int, dict] = {}
_market_tree: list[dict] | None = None

_system_id_to_region: dict[int, int | None] | None = None
_system_id_to_name: dict[int, str] | None = None
_system_id_to_security: dict[int, float | None] | None = None
_region_id_to_name: dict[int, str] | None = None

_blueprints: dict[int, dict] | None = None
_type_materials: dict[int, list[dict]] | None = None
_type_dogma: dict[int, dict] | None = None


def _yaml_loader():
    return getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def _sde_root() -> Path:
    return Path(os.getenv("SDE_PATH", "_sde"))


def _warehouse_path() -> Path:
    return _database_path or sde_store.get_database_path()


def _warehouse_ready() -> bool:
    return sde_store.warehouse_exists(_warehouse_path())


def _connect_ro():
    return sde_store.connect(_warehouse_path(), read_only=True)


def _query_rows(sql: str, params: list[Any] | None = None) -> list[dict]:
    from core.db.reader import query_rows
    return query_rows(sql, params, _warehouse_path())


def _query_one(sql: str, params: list[Any] | None = None) -> dict | None:
    from core.db.reader import query_one
    return query_one(sql, params, _warehouse_path())


def _load_yaml(rel_path: str) -> Any:
    path = _sde_root() / rel_path
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return yaml.load(handle, Loader=_yaml_loader())


def _warm_types() -> None:
    global _type_id_to_name, _name_to_type_id, _type_to_group, _type_to_market_group
    if _type_id_to_name is not None:
        return
    _type_id_to_name = {}
    _name_to_type_id = {}
    _type_to_group = {}
    _type_to_market_group = {}
    if _warehouse_ready():
        rows = _query_rows(
            "SELECT type_id, name_en, group_id, market_group_id FROM sde_types WHERE type_id IS NOT NULL"
        )
        for row in rows:
            type_id = int(row["type_id"])
            name = row.get("name_en")
            if name:
                _type_id_to_name[type_id] = name
                _name_to_type_id[name.lower()] = type_id
            _type_to_group[type_id] = row.get("group_id")
            _type_to_market_group[type_id] = row.get("market_group_id")
        return

    data = _load_yaml("fsd/types.yaml") or {}
    for type_id, props in data.items():
        tid = int(type_id)
        name = ((props.get("name") or {}).get("en") if isinstance(props.get("name"), dict) else None)
        if name:
            _type_id_to_name[tid] = name
            _name_to_type_id[name.lower()] = tid
        _type_to_group[tid] = props.get("groupID")
        _type_to_market_group[tid] = props.get("marketGroupID")


def _warm_groups() -> None:
    global _groups
    if _groups is not None:
        return
    _groups = {}
    if _warehouse_ready():
        rows = _query_rows("SELECT group_id, category_id, published, name_en FROM sde_groups")
        for row in rows:
            _groups[int(row["group_id"])] = {
                "name": row.get("name_en") or f"Group {row['group_id']}",
                "categoryID": row.get("category_id"),
                "published": row.get("published"),
            }
        return
    data = _load_yaml("fsd/groups.yaml") or {}
    for group_id, props in data.items():
        gid = int(group_id)
        _groups[gid] = {
            "name": ((props.get("name") or {}).get("en") if isinstance(props.get("name"), dict) else f"Group {gid}"),
            "categoryID": props.get("categoryID"),
            "published": props.get("published", False),
        }


def _warm_categories() -> None:
    global _categories
    if _categories is not None:
        return
    _categories = {}
    if _warehouse_ready():
        rows = _query_rows("SELECT category_id, name_en FROM sde_categories")
        for row in rows:
            _categories[int(row["category_id"])] = row.get("name_en") or f"Category {row['category_id']}"
        return
    data = _load_yaml("fsd/categories.yaml") or {}
    for category_id, props in data.items():
        cid = int(category_id)
        _categories[cid] = ((props.get("name") or {}).get("en") if isinstance(props.get("name"), dict) else f"Category {cid}")


def _warm_market_tree() -> None:
    global _market_flat, _market_tree
    if _market_tree is not None:
        return
    _market_flat = {}
    if _warehouse_ready():
        rows = _query_rows(
            """
            SELECT market_group_id, parent_group_id, name_en, description_en
            FROM sde_marketGroups
            ORDER BY market_group_id
            """
        )
        for row in rows:
            gid = int(row["market_group_id"])
            _market_flat[gid] = {
                "id": gid,
                "name": row.get("name_en") or f"Group {gid}",
                "description": row.get("description_en") or "",
                "parent": row.get("parent_group_id"),
                "children": [],
                "types": [],
            }
        type_rows = _query_rows("SELECT type_id, market_group_id FROM sde_types WHERE market_group_id IS NOT NULL")
        for row in type_rows:
            node = _market_flat.get(int(row["market_group_id"]))
            if node is not None:
                node["types"].append(int(row["type_id"]))
    else:
        data = _load_yaml("fsd/marketGroups.yaml") or {}
        for group_id, props in data.items():
            gid = int(group_id)
            _market_flat[gid] = {
                "id": gid,
                "name": ((props.get("nameID") or {}).get("en") if isinstance(props.get("nameID"), dict) else f"Unknown {gid}"),
                "description": ((props.get("descriptionID") or {}).get("en") if isinstance(props.get("descriptionID"), dict) else ""),
                "parent": props.get("parentGroupID"),
                "children": [],
                "types": [],
            }
        _warm_types()
        for type_id, market_group_id in (_type_to_market_group or {}).items():
            if market_group_id in _market_flat:
                _market_flat[market_group_id]["types"].append(type_id)

    for node in list(_market_flat.values()):
        parent = node.get("parent")
        if parent in _market_flat:
            _market_flat[parent]["children"].append(node)
    _market_tree = [node for node in _market_flat.values() if node.get("parent") not in _market_flat]


def _warm_universe() -> None:
    global _system_id_to_region, _system_id_to_name, _system_id_to_security, _region_id_to_name
    if _system_id_to_region is not None:
        return
    _system_id_to_region = {}
    _system_id_to_name = {}
    _system_id_to_security = {}
    _region_id_to_name = {}
    if _warehouse_ready():
        rows = _query_rows("SELECT system_id, region_id, system_name, security FROM sde_systems")
        for row in rows:
            system_id = int(row["system_id"])
            _system_id_to_region[system_id] = row.get("region_id")
            _system_id_to_name[system_id] = row.get("system_name") or f"SystemID {system_id}"
            _system_id_to_security[system_id] = row.get("security")
        region_rows = _query_rows("SELECT region_id, region_name FROM sde_regions")
        for row in region_rows:
            _region_id_to_name[int(row["region_id"])] = row.get("region_name") or f"RegionID {row['region_id']}"
        return

    for system_path in _sde_root().rglob("solarsystem.yaml"):
        with system_path.open("r", encoding="utf-8") as handle:
            data = yaml.load(handle, Loader=_yaml_loader()) or {}
        system_id = int(data.get("solarSystemID"))
        _system_id_to_name[system_id] = system_path.parent.name
        _system_id_to_security[system_id] = data.get("security")
        region_path = system_path.parent.parent.parent / "region.yaml"
        if region_path.exists():
            with region_path.open("r", encoding="utf-8") as handle:
                region = yaml.load(handle, Loader=_yaml_loader()) or {}
            region_id = region.get("regionID")
            _system_id_to_region[system_id] = region_id
            if region_id is not None:
                _region_id_to_name[int(region_id)] = region_path.parent.name


def _warm_blueprints() -> None:
    global _blueprints
    if _blueprints is not None:
        return
    _blueprints = {}
    if _warehouse_ready():
        rows = _query_rows(
            "SELECT blueprint_type_id, max_production_limit, activities_json FROM sde_blueprints"
        )
        for row in rows:
            bid = int(row["blueprint_type_id"])
            activities = json.loads(row.get("activities_json") or "{}")
            manufacturing = activities.get("manufacturing") or {}
            _blueprints[bid] = {
                "blueprintTypeID": bid,
                "maxProductionLimit": row.get("max_production_limit"),
                "materials": manufacturing.get("materials") or [],
                "products": manufacturing.get("products") or [],
                "time": manufacturing.get("time"),
                "activities": {k: v for k, v in activities.items() if k != "manufacturing"},
            }
        return

    data = _load_yaml("fsd/blueprints.yaml") or {}
    for blueprint_type_id, props in data.items():
        activities = props.get("activities") or {}
        manufacturing = activities.get("manufacturing") or {}
        _blueprints[int(blueprint_type_id)] = {
            "blueprintTypeID": int(blueprint_type_id),
            "maxProductionLimit": props.get("maxProductionLimit"),
            "materials": manufacturing.get("materials", []),
            "products": manufacturing.get("products", []),
            "time": manufacturing.get("time"),
            "activities": {key: value for key, value in activities.items() if key != "manufacturing"},
        }


def _warm_type_materials() -> None:
    global _type_materials
    if _type_materials is not None:
        return
    _type_materials = {}
    if _warehouse_ready():
        rows = _query_rows("SELECT type_id, materials_json FROM sde_typeMaterials")
        for row in rows:
            raw = row.get("materials_json")
            _type_materials[int(row["type_id"])] = json.loads(raw) if raw else []
        return
    data = _load_yaml("fsd/typeMaterials.yaml") or {}
    for type_id, props in data.items():
        _type_materials[int(type_id)] = props.get("materials", [])


def _warm_type_dogma() -> None:
    global _type_dogma
    if _type_dogma is not None:
        return
    _type_dogma = {}
    if _warehouse_ready():
        rows = _query_rows(
            "SELECT type_id, dogma_attributes_json, dogma_effects_json FROM sde_typeDogma"
        )
        for row in rows:
            attrs_raw = row.get("dogma_attributes_json")
            effects_raw = row.get("dogma_effects_json")
            attrs_list = json.loads(attrs_raw) if attrs_raw else []
            effects_list = json.loads(effects_raw) if effects_raw else []
            _type_dogma[int(row["type_id"])] = {
                "dogmaAttributes": {
                    str(a["attributeID"]): a.get("value")
                    for a in attrs_list
                    if "attributeID" in a
                },
                "dogmaEffects": [e["effectID"] for e in effects_list if "effectID" in e],
            }
        return
    data = _load_yaml("fsd/typeDogma.yaml") or {}
    for type_id, props in data.items():
        _type_dogma[int(type_id)] = {
            "dogmaAttributes": {str(item["attributeID"]): item.get("value") for item in props.get("dogmaAttributes", [])},
            "dogmaEffects": [item["effectID"] for item in props.get("dogmaEffects", [])],
        }


def startup_load_sde(cfg: dict | None = None) -> None:
    """Warm SDE in-memory caches from the DuckDB warehouse.

    **Does not download or build the SDE** — that responsibility now lives
    in ``main.py`` (explicit SDE readiness step before this is called).
    If the warehouse is missing when this runs, caches simply stay empty
    and will lazy-load on first access.
    """
    global _startup_cfg, _database_path
    cfg = cfg or {}
    _database_path = sde_store.get_database_path(cfg)
    _startup_cfg = {
        key: bool(cfg.get(f"load_{key}", default))
        for key, default in _SECTION_DEFAULTS.items()
    }

    if not _warehouse_ready():
        logger.warning("[SDE] No warehouse found at %s — caches will lazy-load on first access.", _warehouse_path())
        return

    logger.info("[SDE] Using warehouse at %s", _warehouse_path())
    try:
        sde_store.ensure_esi_registry_current(_warehouse_path())
    except Exception as exc:
        logger.warning("Failed to ensure the ESI registry is synced into DuckDB: %s", exc)

    warm = [key for key, enabled in _startup_cfg.items() if enabled]
    if warm:
        logger.info("[SDE] Warming caches: %s", ", ".join(warm))
    for key in warm:
        {
            "types": _warm_types,
            "groups": _warm_groups,
            "categories": _warm_categories,
            "market_groups": _warm_market_tree,
            "universe": _warm_universe,
            "blueprints": _warm_blueprints,
            "type_materials": _warm_type_materials,
            "type_dogma": _warm_type_dogma,
        }[key]()


def clear_caches() -> None:
    global _type_id_to_name, _name_to_type_id, _type_to_group, _type_to_market_group
    global _groups, _categories, _market_flat, _market_tree
    global _system_id_to_region, _system_id_to_name, _system_id_to_security, _region_id_to_name
    global _blueprints, _type_materials, _type_dogma
    _type_id_to_name = None
    _name_to_type_id = None
    _type_to_group = None
    _type_to_market_group = None
    _groups = None
    _categories = None
    _market_flat = {}
    _market_tree = None
    _system_id_to_region = None
    _system_id_to_name = None
    _system_id_to_security = None
    _region_id_to_name = None
    _blueprints = None
    _type_materials = None
    _type_dogma = None


def refresh_all_caches() -> None:
    clear_caches()
    startup_load_sde({f"load_{key}": value for key, value in _startup_cfg.items()})


def name_from_type_id(type_id: int) -> str:
    if _type_id_to_name is not None:
        return _type_id_to_name.get(type_id, f"Unknown TypeID {type_id}")
    if _warehouse_ready():
        row = _query_one("SELECT name_en FROM sde_types WHERE type_id = ?", [type_id])
        return (row or {}).get("name_en") or f"Unknown TypeID {type_id}"
    _warm_types()
    return (_type_id_to_name or {}).get(type_id, f"Unknown TypeID {type_id}")


def type_id_from_name(name: str) -> int | None:
    normalized = name.lower()
    if _name_to_type_id is not None:
        return _name_to_type_id.get(normalized)
    if _warehouse_ready():
        row = _query_one("SELECT type_id FROM sde_types WHERE lower(name_en) = ?", [normalized])
        return int(row["type_id"]) if row and row.get("type_id") is not None else None
    _warm_types()
    return (_name_to_type_id or {}).get(normalized)


def suggest_type_names(prefix: str, limit: int = 10) -> list[str]:
    normalized = prefix.strip().lower()
    if not normalized:
        return []
    if _name_to_type_id is not None:
        matches = [name for name in _name_to_type_id if name.startswith(normalized)]
        return [(_type_id_to_name or {}).get(_name_to_type_id[name], name) for name in matches[:limit]]
    if _warehouse_ready():
        rows = _query_rows(
            "SELECT name_en FROM sde_types WHERE lower(name_en) LIKE ? ORDER BY name_en LIMIT ?",
            [normalized + "%", limit],
        )
        return [row["name_en"] for row in rows if row.get("name_en")]
    _warm_types()
    return suggest_type_names(prefix, limit=limit)


def group_id_from_type_id(type_id: int) -> int | None:
    if _type_to_group is not None:
        return _type_to_group.get(type_id)
    if _warehouse_ready():
        row = _query_one("SELECT group_id FROM sde_types WHERE type_id = ?", [type_id])
        return row.get("group_id") if row else None
    _warm_types()
    return (_type_to_group or {}).get(type_id)


def market_group_from_type_id(type_id: int) -> int | None:
    if _type_to_market_group is not None:
        return _type_to_market_group.get(type_id)
    if _warehouse_ready():
        row = _query_one("SELECT market_group_id FROM sde_types WHERE type_id = ?", [type_id])
        return row.get("market_group_id") if row else None
    _warm_types()
    return (_type_to_market_group or {}).get(type_id)


def group_info(group_id: int) -> dict | None:
    _warm_groups()
    return (_groups or {}).get(group_id)


def group_name(group_id: int) -> str:
    info = group_info(group_id)
    return info["name"] if info else f"GroupID {group_id}"


def category_id_from_group(group_id: int) -> int | None:
    info = group_info(group_id)
    return info["categoryID"] if info else None


def category_id_from_type(type_id: int) -> int | None:
    group_id = group_id_from_type_id(type_id)
    return category_id_from_group(group_id) if group_id is not None else None


def category_name(category_id: int) -> str:
    _warm_categories()
    return (_categories or {}).get(category_id, f"CategoryID {category_id}")


def load_market_tree() -> list:
    _warm_market_tree()
    return _market_tree or []


def get_flat_market_map() -> dict[int, str]:
    _warm_market_tree()
    return {group_id: node["name"] for group_id, node in _market_flat.items()}


def get_types_in_group(group_id: int) -> list[int]:
    _warm_market_tree()
    results: list[int] = []
    def _walk(node_id: int) -> None:
        node = _market_flat.get(node_id)
        if not node:
            return
        results.extend(node.get("types", []))
        for child in node.get("children", []):
            _walk(child["id"])
    _walk(group_id)
    return results


def resolve_type_ids(raw_query: str) -> set[int]:
    values: set[int] = set()
    for token in raw_query.split(","):
        value = token.strip()
        if not value:
            continue
        if value.isdigit():
            values.add(int(value))
            continue
        type_id = type_id_from_name(value)
        if type_id is not None:
            values.add(type_id)
    return values


def region_id_from_system_id(system_id: int) -> int | None:
    _warm_universe()
    return (_system_id_to_region or {}).get(system_id)


def system_name_from_id(system_id: int) -> str:
    _warm_universe()
    return (_system_id_to_name or {}).get(system_id, f"SystemID {system_id}")


def security_from_system_id(system_id: int) -> float | None:
    _warm_universe()
    return (_system_id_to_security or {}).get(system_id)


def region_name_from_id(region_id: int) -> str:
    _warm_universe()
    return (_region_id_to_name or {}).get(region_id, f"RegionID {region_id}")


def blueprint_for_type(blueprint_type_id: int) -> dict | None:
    if _blueprints is not None:
        return _blueprints.get(blueprint_type_id)
    if _warehouse_ready():
        _warm_blueprints()
        return (_blueprints or {}).get(blueprint_type_id)
    _warm_blueprints()
    return (_blueprints or {}).get(blueprint_type_id)


def reprocess_materials(type_id: int) -> list[dict]:
    if _type_materials is not None:
        return _type_materials.get(type_id, [])
    if _warehouse_ready():
        rows = _query_rows(
            "SELECT material_type_id, quantity FROM sde_typeMaterials WHERE type_id = ? ORDER BY material_type_id",
            [type_id],
        )
        return [{"materialTypeID": row["material_type_id"], "quantity": row["quantity"]} for row in rows]
    _warm_type_materials()
    return (_type_materials or {}).get(type_id, [])


def dogma_attributes(type_id: int) -> dict[str, float]:
    if _type_dogma is not None:
        return (_type_dogma.get(type_id) or {}).get("dogmaAttributes", {})
    if _warehouse_ready():
        rows = _query_rows(
            "SELECT attribute_id, value FROM sde_typeDogmaAttributes WHERE type_id = ? ORDER BY attribute_id",
            [type_id],
        )
        return {str(int(row["attribute_id"])): row["value"] for row in rows if row.get("attribute_id") is not None}
    _warm_type_dogma()
    return (_type_dogma.get(type_id) or {}).get("dogmaAttributes", {})


def dogma_effects(type_id: int) -> list[int]:
    if _type_dogma is not None:
        return (_type_dogma.get(type_id) or {}).get("dogmaEffects", [])
    if _warehouse_ready():
        rows = _query_rows(
            "SELECT effect_id FROM sde_typeDogmaEffects WHERE type_id = ? ORDER BY effect_id",
            [type_id],
        )
        return [int(row["effect_id"]) for row in rows if row.get("effect_id") is not None]
    _warm_type_dogma()
    return (_type_dogma.get(type_id) or {}).get("dogmaEffects", [])


def load_types_data() -> None:
    _warm_types()


def _load_system_to_region_map() -> None:
    _warm_universe()


def build_universe_table() -> None:
    logger.info("build_universe_table() is deprecated; universe data now lives in the DuckDB SDE warehouse.")
