"""Public database initialization — ensures DuckDB schema and private data dirs exist.

This package owns all persistent data storage:
  public.py        — DuckDB connections, schema, and write helpers
  private.py       — per-owner SQLite (ORM via SQLAlchemy)
  sde.py           — in-memory SDE cache backed by DuckDB (moved from core/sde/)
  market_buffer.py — ephemeral in-process buffer for market order writes
  writer.py        — serialized DuckDB write thread
  reader.py        — thread-safe read helpers
  stats.py         — DB usage metrics
"""

import logging
import os

from core.db.reader import (
    query_rows,
    query_one,
    query_scalar,
    table_count,
    get_db_file_stats,
)
from core.db.stats import (
    get_table_stats,
    get_write_rate_stats,
    optimization_hints,
    table_optimization_hints,
)

__all__ = [
    "ensure_data_dirs",
    "ensure_public_database",
    "initialize_private_database",
    "ensure_schema",
    "warm_caches",
    "initialize_collector_tables",
    "seed_esi_cache",
    "query_rows",
    "query_one",
    "query_scalar",
    "table_count",
    "get_db_file_stats",
    "get_table_stats",
    "get_write_rate_stats",
    "optimization_hints",
    "table_optimization_hints",
]

logger = logging.getLogger(__name__)


# Role renames: old_name → new_name.  Applied once at startup.
_ROLE_RENAMES = {
    "queue": "tasks",
    "db": "database",
}


# Auth table renames: old_name → new_name.  Applied once at startup.
_AUTH_TABLE_RENAMES = {
    "users":       "auth_users",
    "site_admins": "auth_siteAdmins",
    "user_roles":  "auth_userRoles",
}


def _migrate_renamed_auth_tables() -> None:
    """Rename legacy auth tables to auth_* prefix. Idempotent."""
    from core.db.public import connect
    con = connect()
    try:
        existing = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        for old, new in _AUTH_TABLE_RENAMES.items():
            if old in existing and new not in existing:
                con.execute(f'ALTER TABLE "{old}" RENAME TO "{new}"')
                logger.info("Renamed auth table %r -> %r", old, new)
    except Exception as exc:
        logger.debug("Auth table migration skipped: %s", exc)
    finally:
        con.close()


def _migrate_renamed_roles() -> None:
    """Rename legacy role values in auth_userRoles. Idempotent."""
    from core.db.public import connect
    con = connect()
    try:
        for old, new in _ROLE_RENAMES.items():
            changed = con.execute(
                "UPDATE auth_userRoles SET role_name = ? WHERE role_name = ?",
                [new, old],
            ).rowcount
            if changed:
                logger.info("Migrated %d user role(s): %r -> %r", changed, old, new)
    except Exception as exc:
        # Table may not exist yet on a fresh install — that's fine.
        logger.debug("Role migration skipped: %s", exc)
    finally:
        con.close()


def ensure_data_dirs() -> None:
    """Create _publicData/ and _privateData/ if missing."""
    os.makedirs(os.getenv("PUBLIC_DATA_FOLDER", "_publicData"), exist_ok=True)
    os.makedirs(os.getenv("EVE_PRIVATE_DATABASE_FOLDER", "_privateData/"), exist_ok=True)


def ensure_public_database(database_file=None):
    """Create / migrate the DuckDB operational schema (fast — idempotent)."""
    from core.db import public
    return public.ensure_public_database(database_file)


def initialize_private_database(owner_id: int):
    """Create per-owner SQLite with WAL mode, PRAGMA settings."""
    from core.db.private import initialize_private_database as _init
    return _init(owner_id)


def ensure_schema() -> None:
    """Create / migrate the DuckDB operational schema (fast — idempotent)."""
    logger.info("Ensuring public DuckDB schema...")
    _migrate_renamed_auth_tables()
    ensure_public_database()
    _migrate_renamed_roles()
    logger.info("Public DuckDB schema ready.")


def warm_caches(sde_cfg: dict | None = None) -> None:
    """Load SDE dimension data into the in-memory lookup caches."""
    from core.db.sde import startup_load_sde
    logger.info("Warming SDE in-memory caches...")
    startup_load_sde(sde_cfg or {})
    logger.info("SDE caches warm.")


def initialize_analysis_tables(con) -> None:
    """Call every collector's ensure_tables (and ensure_columns where applicable).

    Each import is guarded individually so an import error in one collector
    never prevents the others from running.  All DDL is idempotent.

    This is called once at startup so that the DB browser always shows the
    full table set even before any data collection has run.
    """
    collectors = [
        # (module_path, has_ensure_columns)
        ("collectors.market.regions",      True),
        ("collectors.market.structures",   True),
        ("collectors.structures.discover", True),
    ]

    for module_path, has_columns in collectors:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            mod.ensure_tables(con)
            if has_columns:
                try:
                    mod.ensure_columns(con)
                except Exception as col_exc:
                    logger.debug("[DB init] ensure_columns skipped for %s: %s", module_path, col_exc)
            logger.debug("[DB init] Tables ready: %s", module_path)
        except Exception as exc:
            logger.warning("[DB init] Could not initialize tables for %s: %s", module_path, exc)


def initialize_collector_tables() -> None:
    """Ensure every collector's DDL tables exist in DuckDB.

    Opens a connection, calls initialize_analysis_tables, and checkpoints.
    """
    from core.db import public
    con = public.connect()
    try:
        initialize_analysis_tables(con)
        con.execute("CHECKPOINT")
    finally:
        con.close()


def seed_esi_cache() -> None:
    """Initialise ESI cache tables and seed route specs from generated DDL."""
    from core.db import public
    con = public.connect()
    try:
        try:
            import core.esi.cache as esi_cache
            esi_cache.ensure_tables(con)
            count = esi_cache.seed_route_specs(con)
            if count:
                logger.info("ESI cache: seeded %d route spec rows.", count)
        except Exception as exc:
            logger.warning("ESI cache init skipped (%s). Run 'python build.py' to generate cache_ddl.py.", exc)
        con.execute("CHECKPOINT")
    finally:
        con.close()


def initialize_all(sde_cfg: dict | None = None) -> dict:
    """Run the full public initialization sequence (schema → caches → collector tables → ESI cache).

    Returns the current warehouse status dict.

    .. deprecated::
        Prefer calling ``ensure_schema()``, ``warm_caches()``,
        ``initialize_collector_tables()``, and ``seed_esi_cache()``
        individually for a deterministic startup sequence.
    """
    from core.db import public
    ensure_schema()
    warm_caches(sde_cfg)
    initialize_collector_tables()
    seed_esi_cache()
    return public.get_warehouse_status()
