# util/sde.py
"""EVE SDE (Static Data Export) loader.

All data structures are loaded once at process startup via startup_load_sde().
Each section can be individually enabled/disabled in config.yaml under the
'SDE' key.  Lookup helpers return sensible defaults when a section was not
loaded so the rest of the app degrades gracefully instead of crashing.

Progress is printed to stdout using \\r line-overwrite with space-padding so
shorter status messages fully erase longer previous ones.
"""

import os
import re
import time
import logging
import threading
import yaml

from db.database import get_public_session
from db.models import SolarSystem, Stargate

logger = logging.getLogger(__name__)

# -- Paths --------------------------------------------------------------------
BASE_SDE_PATH        = os.getenv("SDE_PATH", "_sde")
TYPES_YAML_PATH      = os.path.join(BASE_SDE_PATH, "fsd", "types.yaml")
MARKET_GROUPS_PATH   = os.path.join(BASE_SDE_PATH, "fsd", "marketGroups.yaml")
GROUPS_YAML_PATH     = os.path.join(BASE_SDE_PATH, "fsd", "groups.yaml")
CATEGORIES_YAML_PATH = os.path.join(BASE_SDE_PATH, "fsd", "categories.yaml")
BLUEPRINTS_YAML_PATH = os.path.join(BASE_SDE_PATH, "fsd", "blueprints.yaml")
TYPE_MATERIALS_PATH  = os.path.join(BASE_SDE_PATH, "fsd", "typeMaterials.yaml")
TYPE_DOGMA_PATH      = os.path.join(BASE_SDE_PATH, "fsd", "typeDogma.yaml")
UNIVERSE_PATH        = os.path.join(BASE_SDE_PATH, "universe")

# -- Console ------------------------------------------------------------------
_COL = 90   # total line width; shorter lines are right-padded with spaces

# -- Disabled-section registry ------------------------------------------------
# Populated by startup_load_sde() so lazy-load helpers know to skip them.
_disabled_sections: set[str] = set()

# -- Caches -------------------------------------------------------------------
_type_id_to_name:      dict | None = None   # typeID  -> "Name"
_name_to_type_id:      dict | None = None   # "name lower" -> typeID
_type_to_group:        dict | None = None   # typeID  -> groupID
_type_to_market_group: dict | None = None   # typeID  -> marketGroupID

_groups:     dict | None = None             # groupID -> {name, categoryID, published}
_categories: dict | None = None             # categoryID -> name

_market_flat: dict       = {}               # marketGroupID -> node dict
_market_tree: list | None = None            # top-level nodes

_system_id_to_region:   dict | None = None  # solarSystemID -> regionID
_system_id_to_name:     dict | None = None  # solarSystemID -> "Name"
_system_id_to_security: dict | None = None  # solarSystemID -> float
_region_id_to_name:     dict | None = None  # regionID -> "Name"

_blueprints:     dict | None = None         # blueprintTypeID -> {materials, products, time}
_type_materials: dict | None = None         # typeID -> [{materialTypeID, quantity}]
_type_dogma:     dict | None = None         # typeID -> {dogmaAttributes, dogmaEffects}


# ---------------------------------------------------------------------------
# Progress printer
# ---------------------------------------------------------------------------

def _pp(label: str, current: int, total: int, t0: float, final: bool = False) -> None:
    """Write a single \\r-overwriting progress line.

    final=True ends with \\n so the completed line stays visible.
    Pads each line to _COL characters so shorter lines fully erase longer ones.
    """
    elapsed = time.time() - t0
    pct = current / total * 100.0 if total > 0 else 0.0
    rate = current / elapsed if elapsed > 0 else 0.0

    if final:
        time_s = f"done {elapsed:5.1f}s"
    elif current > 0 and total > 0:
        remaining = elapsed * (total - current) / current
        time_s = f"ETA  {remaining:5.1f}s"
    else:
        time_s = "ETA      --"

    msg = (
        f"  {label:<24}"
        f"  {current:>7,}/{total:<7,}"
        f"  {pct:5.1f}%"
        f"  {time_s}"
        f"  {rate:>10,.0f}/s"
    )
    end = "\n" if final else ""
    print(f"\r{msg:<{_COL}}", end=end, flush=True)


def _divider() -> None:
    print("  " + "-" * (_COL - 2))


def _file_read(label: str, path: str) -> None:
    """Print a one-line 'reading file' status (overwritten by first progress tick)."""
    msg = f"  {label:<24}  reading {os.path.basename(path)} ..."
    print(f"\r{msg:<{_COL}}", end="", flush=True)


def _pp_parse(label: str, pos: int, total: int, t0: float) -> None:
    """\\r progress line during YAML parse phase — shows MB read vs total MB."""
    elapsed = time.time() - t0
    pct = pos / total * 100.0 if total > 0 else 0.0
    pos_mb = pos / 1_048_576
    tot_mb = total / 1_048_576
    rate = (pos / elapsed / 1_048_576) if elapsed > 0 else 0.0
    if pos > 0 and total > 0:
        remaining = elapsed * (total - pos) / pos
        time_s = f"ETA  {remaining:5.1f}s"
    else:
        time_s = "ETA      --"
    msg = (
        f"  {label:<24}"
        f"  {pos_mb:5.1f}/{tot_mb:<5.1f} MB"
        f"  {pct:5.1f}%"
        f"  {time_s}"
        f"  {rate:7.2f} MB/s"
    )
    print(f"\r{msg:<{_COL}}", end="", flush=True)


def _yaml_load_tracked(label: str, path: str, t0: float, verbose: bool) -> dict:
    """Load a YAML file with a background thread showing byte-read progress.

    PyYAML reads the stream in 4096-byte chunks via stream.read().  A thin
    file wrapper tracks tell() after each read so the monitor thread can
    display MB-level progress every 150 ms.  The caller's t0 is shared so
    the final _pp() call shows wall-clock time spanning both parse + iterate.
    """
    size = os.path.getsize(path)
    _pos = [0]
    _done = [False]

    class _TF:
        """Thin file wrapper that updates _pos after every read."""
        def __init__(self, fh):
            self._fh = fh
        def read(self, n=-1):
            data = self._fh.read(n)
            _pos[0] = self._fh.tell()
            return data
        def readline(self):
            line = self._fh.readline()
            _pos[0] = self._fh.tell()
            return line
        def __iter__(self):
            return self
        def __next__(self):
            line = self._fh.readline()
            if not line:
                raise StopIteration
            _pos[0] = self._fh.tell()
            return line

    def _monitor():
        while not _done[0]:
            _pp_parse(label, _pos[0], size, t0)
            time.sleep(0.15)

    mon = None
    if verbose:
        _pp_parse(label, 0, size, t0)
        mon = threading.Thread(target=_monitor, daemon=True)
        mon.start()

    try:
        with open(path, "rb") as fh:
            data = yaml.safe_load(_TF(fh)) or {}
    finally:
        _done[0] = True
        if mon is not None:
            mon.join(timeout=0.5)

    return data


# ---------------------------------------------------------------------------
# Section loaders  (internal; called with verbose=True from startup_load_sde)
# ---------------------------------------------------------------------------

def _load_types(verbose: bool = True) -> None:
    global _type_id_to_name, _name_to_type_id, _type_to_group, _type_to_market_group
    if _type_id_to_name is not None:
        return

    _type_id_to_name = {}
    _name_to_type_id = {}
    _type_to_group = {}
    _type_to_market_group = {}

    if not os.path.exists(TYPES_YAML_PATH):
        logger.error("types.yaml not found at %s", TYPES_YAML_PATH)
        return

    t0 = time.time()
    data = _yaml_load_tracked("types", TYPES_YAML_PATH, t0, verbose)
    total = len(data)
    t0_iter = time.time()
    for i, (tid_str, props) in enumerate(data.items()):
        if verbose and i % 2000 == 0:
            _pp("types", i, total, t0_iter)
        try:
            tid = int(tid_str)
        except ValueError:
            continue
        name = props.get("name", {}).get("en")
        if name:
            _type_id_to_name[tid] = name
            _name_to_type_id[name.lower()] = tid
        gid = props.get("groupID")
        if gid is not None:
            _type_to_group[tid] = int(gid)
        mgid = props.get("marketGroupID")
        if mgid is not None:
            _type_to_market_group[tid] = int(mgid)

    if verbose:
        _pp("types", total, total, t0, final=True)


def _load_groups(verbose: bool = True) -> None:
    global _groups
    if _groups is not None:
        return

    _groups = {}
    if not os.path.exists(GROUPS_YAML_PATH):
        logger.warning("groups.yaml not found at %s", GROUPS_YAML_PATH)
        return

    t0 = time.time()
    if verbose:
        _file_read("groups", GROUPS_YAML_PATH)
    with open(GROUPS_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    total = len(data)
    for i, (gid_str, props) in enumerate(data.items()):
        if verbose and i % 200 == 0:
            _pp("groups", i, total, t0)
        try:
            gid = int(gid_str)
        except ValueError:
            continue
        _groups[gid] = {
            "name":       props.get("name", {}).get("en", f"Group {gid}"),
            "categoryID": props.get("categoryID"),
            "published":  props.get("published", False),
        }

    if verbose:
        _pp("groups", total, total, t0, final=True)


def _load_categories(verbose: bool = True) -> None:
    global _categories
    if _categories is not None:
        return

    _categories = {}
    if not os.path.exists(CATEGORIES_YAML_PATH):
        logger.warning("categories.yaml not found at %s", CATEGORIES_YAML_PATH)
        return

    t0 = time.time()
    if verbose:
        _file_read("categories", CATEGORIES_YAML_PATH)
    with open(CATEGORIES_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    total = len(data)
    for i, (cid_str, props) in enumerate(data.items()):
        if verbose and i % 20 == 0:
            _pp("categories", i, total, t0)
        try:
            cid = int(cid_str)
        except ValueError:
            continue
        _categories[cid] = props.get("name", {}).get("en", f"Category {cid}")

    if verbose:
        _pp("categories", total, total, t0, final=True)


def _load_market_groups(verbose: bool = True) -> None:
    global _market_flat, _market_tree
    if _market_tree is not None:
        return

    _market_flat = {}
    if not os.path.exists(MARKET_GROUPS_PATH):
        logger.error("marketGroups.yaml not found at %s", MARKET_GROUPS_PATH)
        _market_tree = []
        return

    t0 = time.time()
    if verbose:
        _file_read("market_groups", MARKET_GROUPS_PATH)
    with open(MARKET_GROUPS_PATH, "r", encoding="utf-8") as f:
        raw_groups = yaml.safe_load(f) or {}
    total_steps = len(raw_groups) * 2   # pass-1 + pass-3 estimate

    # Pass 1: build flat map
    for i, (gid_str, info) in enumerate(raw_groups.items()):
        if verbose and i % 150 == 0:
            _pp("market_groups", i, total_steps, t0)
        try:
            gid = int(gid_str)
        except ValueError:
            continue
        _market_flat[gid] = {
            "id":          gid,
            "name":        info.get("nameID", {}).get("en", f"Unknown {gid}"),
            "description": info.get("descriptionID", {}).get("en", ""),
            "parent":      info.get("parentGroupID"),
            "children":    [],
            "types":       [],
        }

    # Pass 2: attach types (reuse already-loaded _type_to_market_group when available)
    if _type_to_market_group is not None:
        for tid, mgid in _type_to_market_group.items():
            node = _market_flat.get(mgid)
            if node is not None:
                node["types"].append(tid)
    elif os.path.exists(TYPES_YAML_PATH):
        if verbose:
            msg = f"  {'market_groups':<24}  scanning types for marketGroupID ..."
            print(f"\r{msg:<{_COL}}", end="", flush=True)
        with open(TYPES_YAML_PATH, "r", encoding="utf-8") as f:
            all_types = yaml.safe_load(f) or {}
        for tid_str, props in all_types.items():
            try:
                tid = int(tid_str)
            except ValueError:
                continue
            mgid = props.get("marketGroupID")
            if mgid:
                node = _market_flat.get(int(mgid))
                if node is not None:
                    node["types"].append(tid)

    # Pass 3: wire children
    n = len(raw_groups)
    for i, grp in enumerate(_market_flat.values()):
        if verbose and i % 150 == 0:
            _pp("market_groups", n + i, total_steps, t0)
        parent = grp["parent"]
        if parent is not None:
            parent_node = _market_flat.get(parent)
            if parent_node is not None:
                parent_node["children"].append(grp)

    _market_tree = [g for g in _market_flat.values() if g["parent"] is None]

    if verbose:
        _pp("market_groups", total_steps, total_steps, t0, final=True)


# Regex patterns for fast universe file scanning (avoids full YAML parse)
_RE_REGION_ID = re.compile(r"^regionID:\s+(\d+)", re.MULTILINE)
_RE_SYS_ID    = re.compile(r"^solarSystemID:\s+(\d+)", re.MULTILINE)
_RE_SECURITY  = re.compile(r"^security:\s+([-\d.eE+]+)", re.MULTILINE)


def _load_universe(verbose: bool = True) -> None:
    global _system_id_to_region, _system_id_to_name, _system_id_to_security, _region_id_to_name
    if _system_id_to_region is not None:
        return

    _system_id_to_region   = {}
    _system_id_to_name     = {}
    _system_id_to_security = {}
    _region_id_to_name     = {}

    if not os.path.exists(UNIVERSE_PATH):
        logger.warning("Universe path not found: %s", UNIVERSE_PATH)
        return

    if verbose:
        msg = f"  {'universe':<24}  scanning directory tree ..."
        print(f"\r{msg:<{_COL}}", end="", flush=True)

    # Single os.walk to collect region.yaml and solarsystem.yaml paths
    region_files: list[tuple[str, str]] = []   # (dir, path)
    ss_files:     list[tuple[str, str]] = []   # (dir, path)

    for root, _dirs, files in os.walk(UNIVERSE_PATH):
        if "region.yaml" in files:
            region_files.append((root, os.path.join(root, "region.yaml")))
        if "solarsystem.yaml" in files:
            ss_files.append((root, os.path.join(root, "solarsystem.yaml")))

    # Phase 1: build region-dir -> regionID map (few hundred files, fast)
    region_dir_to_id: dict[str, int] = {}
    for rdir, rpath in region_files:
        try:
            txt = open(rpath, "r", encoding="utf-8").read()
            m = _RE_REGION_ID.search(txt)
            if m:
                rid = int(m.group(1))
                region_dir_to_id[os.path.normpath(rdir)] = rid
                _region_id_to_name[rid] = os.path.basename(rdir)
        except Exception:
            pass

    # Phase 2: read each solarsystem.yaml with live progress
    total = len(ss_files)
    t0 = time.time()

    for done, (sdir, sspath) in enumerate(ss_files):
        if verbose and done % 100 == 0:
            _pp("universe", done, total, t0)
        try:
            txt = open(sspath, "r", encoding="utf-8").read()
            m_id = _RE_SYS_ID.search(txt)
            if not m_id:
                continue
            sid = int(m_id.group(1))
            _system_id_to_name[sid] = os.path.basename(sdir)
            m_sec = _RE_SECURITY.search(txt)
            if m_sec:
                _system_id_to_security[sid] = float(m_sec.group(1))
            # Region is 2 levels up: system_dir -> constellation_dir -> region_dir
            region_dir = os.path.normpath(os.path.dirname(sdir))
            rid = region_dir_to_id.get(region_dir)
            if rid is not None:
                _system_id_to_region[sid] = rid
        except Exception as exc:
            logger.debug("Error reading %s: %s", sspath, exc)

    if verbose:
        _pp("universe", total, total, t0, final=True)


def _load_blueprints(verbose: bool = True) -> None:
    global _blueprints
    if _blueprints is not None:
        return

    _blueprints = {}
    if not os.path.exists(BLUEPRINTS_YAML_PATH):
        logger.warning("blueprints.yaml not found at %s", BLUEPRINTS_YAML_PATH)
        return

    t0 = time.time()
    data = _yaml_load_tracked("blueprints", BLUEPRINTS_YAML_PATH, t0, verbose)
    total = len(data)
    t0_iter = time.time()
    for i, (bp_id_str, bp) in enumerate(data.items()):
        if verbose and i % 200 == 0:
            _pp("blueprints", i, total, t0_iter)
        try:
            bp_id = int(bp_id_str)
        except ValueError:
            continue
        acts = bp.get("activities", {})
        mfg  = acts.get("manufacturing", {})
        _blueprints[bp_id] = {
            "blueprintTypeID":    bp_id,
            "maxProductionLimit": bp.get("maxProductionLimit"),
            "materials":          mfg.get("materials", []),
            "products":           mfg.get("products", []),
            "time":               mfg.get("time"),
            "activities":         {k: v for k, v in acts.items() if k != "manufacturing"},
        }

    if verbose:
        _pp("blueprints", total, total, t0, final=True)


def _load_type_materials(verbose: bool = True) -> None:
    global _type_materials
    if _type_materials is not None:
        return

    _type_materials = {}
    if not os.path.exists(TYPE_MATERIALS_PATH):
        logger.warning("typeMaterials.yaml not found at %s", TYPE_MATERIALS_PATH)
        return

    t0 = time.time()
    data = _yaml_load_tracked("type_materials", TYPE_MATERIALS_PATH, t0, verbose)
    total = len(data)
    t0_iter = time.time()
    for i, (tid_str, entry) in enumerate(data.items()):
        if verbose and i % 500 == 0:
            _pp("type_materials", i, total, t0_iter)
        try:
            tid = int(tid_str)
        except ValueError:
            continue
        _type_materials[tid] = entry.get("materials", [])

    if verbose:
        _pp("type_materials", total, total, t0, final=True)


def _load_type_dogma(verbose: bool = True) -> None:
    global _type_dogma
    if _type_dogma is not None:
        return

    _type_dogma = {}
    if not os.path.exists(TYPE_DOGMA_PATH):
        logger.warning("typeDogma.yaml not found at %s", TYPE_DOGMA_PATH)
        return

    t0 = time.time()
    data = _yaml_load_tracked("type_dogma", TYPE_DOGMA_PATH, t0, verbose)
    total = len(data)
    t0_iter = time.time()
    for i, (tid_str, entry) in enumerate(data.items()):
        if verbose and i % 1000 == 0:
            _pp("type_dogma", i, total, t0_iter)
        try:
            tid = int(tid_str)
        except ValueError:
            continue
        _type_dogma[tid] = {
            "dogmaAttributes": {
                str(a["attributeID"]): a.get("value")
                for a in entry.get("dogmaAttributes", [])
            },
            "dogmaEffects": [
                e["effectID"] for e in entry.get("dogmaEffects", [])
            ],
        }

    if verbose:
        _pp("type_dogma", total, total, t0, final=True)


# ---------------------------------------------------------------------------
# Master startup loader
# ---------------------------------------------------------------------------

# Map of section key -> (loader_fn, description)
_SECTION_LOADERS: dict[str, tuple] = {
    "types":          (_load_types,          "type ID <-> name maps"),
    "groups":         (_load_groups,         "item group hierarchy"),
    "categories":     (_load_categories,     "item categories"),
    "market_groups":  (_load_market_groups,  "market group tree"),
    "universe":       (_load_universe,       "solar-system -> region map"),
    "blueprints":     (_load_blueprints,     "manufacturing blueprints"),
    "type_materials": (_load_type_materials, "reprocessing materials"),
    "type_dogma":     (_load_type_dogma,     "item dogma attributes"),
}

# Default on/off for each section (overridden in config.yaml -> SDE)
_SECTION_DEFAULTS: dict[str, bool] = {
    "types":          True,
    "groups":         True,
    "categories":     True,
    "market_groups":  True,
    "universe":       True,
    "blueprints":     False,
    "type_materials": False,
    "type_dogma":     False,
}


def startup_load_sde(cfg: dict | None = None) -> None:
    """Load all enabled SDE sections at process startup with live console progress.

    cfg is the dict from config.yaml under the \'SDE\' key (may be None / empty).
    Call this once from main.py before starting Flask.
    """
    global _disabled_sections
    cfg = cfg or {}

    # Resolve per-section enabled/disabled
    sections: dict[str, bool] = {
        key: bool(cfg.get(f"load_{key}", default))
        for key, default in _SECTION_DEFAULTS.items()
    }

    enabled  = [k for k, v in sections.items() if v]
    disabled = [k for k, v in sections.items() if not v]
    _disabled_sections = set(disabled)

    # Header
    print()
    _divider()
    print(f"  EVE SDE Startup Load  --  path: {os.path.abspath(BASE_SDE_PATH)}")
    print(f"  Enabled  : {', '.join(enabled) if enabled else '(none)'}")
    if disabled:
        print(f"  Disabled : {', '.join(disabled)}  (edit SDE section in config.yaml to change)")
    _divider()
    print(
        f"  {'Section':<24}  {'files':>17}  {'  pct':>7}"
        f"  {'time':>11}  {'rate':>12}"
    )
    _divider()

    if not enabled:
        print("  (no sections enabled -- SDE data will lazy-load on first use)")
        _divider()
        print()
        return

    master_t0 = time.time()
    loaded_counts: dict[str, int] = {}

    for key in _SECTION_LOADERS:
        if key not in enabled:
            continue
        loader_fn, _ = _SECTION_LOADERS[key]
        loader_fn(verbose=True)
        loaded_counts[key] = _count_cache(key)

    # Footer
    total_elapsed = time.time() - master_t0
    _divider()
    print(f"  SDE load complete -- {len(enabled)} section(s) -- {total_elapsed:.1f}s total")
    summary_parts = [f"{count:,} {key.replace('_', ' ')}" for key, count in loaded_counts.items() if count]
    if summary_parts:
        line = "  Loaded: "
        for part in summary_parts:
            candidate = line + part + ", "
            if len(candidate) > _COL - 2:
                print(line.rstrip(", "))
                line = "    " + part + ", "
            else:
                line = candidate
        print(line.rstrip(", "))
    _divider()
    print()


def _count_cache(key: str) -> int:
    """Return the number of items in a named cache."""
    m = {
        "types":          _type_id_to_name,
        "groups":         _groups,
        "categories":     _categories,
        "market_groups":  _market_flat,
        "universe":       _system_id_to_region,
        "blueprints":     _blueprints,
        "type_materials": _type_materials,
        "type_dogma":     _type_dogma,
    }
    cache = m.get(key)
    return len(cache) if cache else 0


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

def clear_caches() -> None:
    """Reset all in-memory SDE caches."""
    global _type_id_to_name, _name_to_type_id, _type_to_group, _type_to_market_group
    global _groups, _categories
    global _market_flat, _market_tree
    global _system_id_to_region, _system_id_to_name, _system_id_to_security, _region_id_to_name
    global _blueprints, _type_materials, _type_dogma
    _type_id_to_name = _name_to_type_id = _type_to_group = _type_to_market_group = None
    _groups = _categories = None
    _market_flat = {}
    _market_tree = None
    _system_id_to_region = _system_id_to_name = _system_id_to_security = _region_id_to_name = None
    _blueprints = _type_materials = _type_dogma = None
    logger.info("SDE caches cleared.")


def refresh_all_caches() -> None:
    """Force a full reload of all previously-enabled SDE sections."""
    prev_disabled = set(_disabled_sections)
    clear_caches()
    enabled = [k for k in _SECTION_DEFAULTS if k not in prev_disabled]
    cfg = {f"load_{k}": (k in enabled) for k in _SECTION_DEFAULTS}
    startup_load_sde(cfg)


# ---------------------------------------------------------------------------
# Public lookup helpers -- all fail-safe when a section is disabled
# ---------------------------------------------------------------------------

def _lazy(section: str, loader_fn) -> bool:
    """Return True if the section is available (loading lazily when needed).

    If the section was explicitly disabled in startup_load_sde(), returns False
    immediately without touching disk.
    """
    if section in _disabled_sections:
        return False
    loader_fn(verbose=False)
    return True


# Types

def name_from_type_id(type_id: int) -> str:
    if not _lazy("types", _load_types):
        return f"TypeID {type_id}"
    return _type_id_to_name.get(type_id, f"Unknown TypeID {type_id}")


def type_id_from_name(name: str) -> int | None:
    if not _lazy("types", _load_types):
        return None
    return _name_to_type_id.get(name.lower())


def group_id_from_type_id(type_id: int) -> int | None:
    if not _lazy("types", _load_types):
        return None
    return _type_to_group.get(type_id)


def market_group_from_type_id(type_id: int) -> int | None:
    if not _lazy("types", _load_types):
        return None
    return _type_to_market_group.get(type_id)


# Groups

def group_info(group_id: int) -> dict | None:
    """Return {name, categoryID, published} for a groupID, or None."""
    if not _lazy("groups", _load_groups):
        return None
    return _groups.get(group_id)


def group_name(group_id: int) -> str:
    info = group_info(group_id)
    return info["name"] if info else f"GroupID {group_id}"


def category_id_from_group(group_id: int) -> int | None:
    info = group_info(group_id)
    return info["categoryID"] if info else None


def category_id_from_type(type_id: int) -> int | None:
    gid = group_id_from_type_id(type_id)
    if gid is None:
        return None
    return category_id_from_group(gid)


# Categories

def category_name(category_id: int) -> str:
    if not _lazy("categories", _load_categories):
        return f"CategoryID {category_id}"
    return _categories.get(category_id, f"CategoryID {category_id}")


# Market groups

def load_market_tree() -> list:
    """Return (and lazily load) the market-group tree.  Back-compat entry point."""
    if not _lazy("market_groups", _load_market_groups):
        return []
    return _market_tree or []


def get_flat_market_map() -> dict[int, str]:
    """Return {marketGroupID: name} flat dict."""
    if not _lazy("market_groups", _load_market_groups):
        return {}
    return {gid: grp["name"] for gid, grp in _market_flat.items()}


def get_types_in_group(group_id: int) -> list[int]:
    """Return all typeIDs in a market-group (recursive through children)."""
    if not _lazy("market_groups", _load_market_groups):
        return []
    result: list[int] = []

    def _recurse(gid: int) -> None:
        grp = _market_flat.get(gid)
        if not grp:
            return
        result.extend(grp["types"])
        for child in grp["children"]:
            _recurse(child["id"])

    _recurse(group_id)
    return result


def resolve_type_ids(raw_query: str) -> set[int]:
    """Parse a comma-separated string of names/IDs into a set of typeIDs."""
    if not _lazy("types", _load_types):
        return set()
    ids: set[int] = set()
    for token in raw_query.split(","):
        tok = token.strip()
        if not tok:
            continue
        if tok.isdigit():
            ids.add(int(tok))
        else:
            tid = _name_to_type_id.get(tok.lower())
            if tid:
                ids.add(tid)
    return ids


# Universe

def region_id_from_system_id(system_id: int) -> int | None:
    if not _lazy("universe", _load_universe):
        return None
    return _system_id_to_region.get(system_id)


def system_name_from_id(system_id: int) -> str:
    if not _lazy("universe", _load_universe):
        return f"SystemID {system_id}"
    return _system_id_to_name.get(system_id, f"SystemID {system_id}")


def security_from_system_id(system_id: int) -> float | None:
    if not _lazy("universe", _load_universe):
        return None
    return _system_id_to_security.get(system_id)


def region_name_from_id(region_id: int) -> str:
    if not _lazy("universe", _load_universe):
        return f"RegionID {region_id}"
    return _region_id_to_name.get(region_id, f"RegionID {region_id}")


# Blueprints

def blueprint_for_type(blueprint_type_id: int) -> dict | None:
    """Return manufacturing data for a blueprintTypeID, or None."""
    if not _lazy("blueprints", _load_blueprints):
        return None
    return _blueprints.get(blueprint_type_id)


# Type materials

def reprocess_materials(type_id: int) -> list[dict]:
    """Return [{materialTypeID, quantity}] for the given typeID."""
    if not _lazy("type_materials", _load_type_materials):
        return []
    return _type_materials.get(type_id, [])


# Type dogma

def dogma_attributes(type_id: int) -> dict[str, float]:
    """Return {attributeID: value} dict for typeID."""
    if not _lazy("type_dogma", _load_type_dogma):
        return {}
    entry = _type_dogma.get(type_id, {})
    return entry.get("dogmaAttributes", {})


def dogma_effects(type_id: int) -> list[int]:
    """Return list of effectIDs for typeID."""
    if not _lazy("type_dogma", _load_type_dogma):
        return []
    entry = _type_dogma.get(type_id, {})
    return entry.get("dogmaEffects", [])


# ---------------------------------------------------------------------------
# Back-compat shims
# ---------------------------------------------------------------------------

def load_types_data() -> None:
    """Backward-compatible entry point kept for older callers."""
    if "types" not in _disabled_sections:
        _load_types(verbose=False)


def _load_system_to_region_map() -> None:
    """Backward-compatible internal call -- delegates to _load_universe()."""
    _load_universe(verbose=False)


# ---------------------------------------------------------------------------
# Universe DB table builder  (separate from the in-memory cache)
# ---------------------------------------------------------------------------

def build_universe_table() -> None:
    """Walk the SDE universe folder and upsert SolarSystem + Stargate DB rows.

    Uses the in-memory universe cache if already loaded.
    Note: current SDE uses solarsystem.yaml (not solarsystem.staticdata.yaml).
    """
    session = get_public_session()
    logger.info("Starting build_universe_table()")

    _load_universe(verbose=False)   # ensure cache is live

    stargate_map: dict[int, tuple[int, int]] = {}

    for root, _dirs, files in os.walk(UNIVERSE_PATH):
        if "solarsystem.yaml" not in files:
            continue
        path = os.path.join(root, "solarsystem.yaml")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            continue

        sid = data.get("solarSystemID")
        if sid is None:
            continue
        sid = int(sid)

        name     = _system_id_to_name.get(sid, os.path.basename(root))
        rid      = _system_id_to_region.get(sid)
        security = data.get("security", 0.0)
        planets  = data.get("planets", [])
        if isinstance(planets, list):
            n_planets = len(planets)
            n_moons   = sum(len(p.get("moons", [])) for p in planets if isinstance(p, dict))
        else:
            n_planets = 0
            n_moons   = 0
        gates = data.get("stargates", {}) or {}

        session.merge(SolarSystem(
            system_id        = sid,
            system_name      = name,
            constellation_id = data.get("constellationID"),
            region_id        = rid,
            planets          = n_planets,
            moons            = n_moons,
            stargates        = len(gates),
            security         = security,
        ))

        for gstr, ginfo in (gates.items() if isinstance(gates, dict) else []):
            gid  = int(gstr)
            dest = int(ginfo.get("destination", 0))
            pos  = ginfo.get("position", [0.0, 0.0, 0.0])
            typ  = ginfo.get("typeID")
            gate = Stargate(
                stargate_id           = gid,
                system_id             = sid,
                destination_gate_id   = dest,
                destination_system_id = None,
                type_id               = typ,
                position              = pos,
            )
            session.merge(gate)
            stargate_map[gid] = (sid, dest)

            if dest in stargate_map:
                other_sid, _ = stargate_map[dest]
                existing = session.get(Stargate, dest)
                if existing:
                    existing.destination_system_id = sid
                    session.merge(existing)
                gate.destination_system_id = other_sid
                session.merge(gate)

    session.commit()
    session.close()
    logger.info("build_universe_table() complete")
