"""Public database initialization — ensures DuckDB schema and private data dirs exist."""

import logging
import os

logger = logging.getLogger(__name__)


def ensure_data_dirs() -> None:
    """Create _publicData/ and _privateData/ if missing."""
    os.makedirs(os.getenv("PUBLIC_DATA_FOLDER", "_publicData"), exist_ok=True)
    os.makedirs(os.getenv("EVE_PRIVATE_DATABASE_FOLDER", "_privateData/"), exist_ok=True)


def ensure_public_database(database_file=None):
    """Create / migrate the DuckDB operational schema (fast — idempotent)."""
    from core.db import publicDB
    return publicDB.ensure_public_database(database_file)


def initialize_private_database(owner_id: int):
    """Create per-owner SQLite with WAL mode, PRAGMA settings."""
    from core.db.privateDB import initialize_private_database as _init
    return _init(owner_id)


def ensure_schema() -> None:
    """Create / migrate the DuckDB operational schema (fast — idempotent)."""
    logger.info("Ensuring public DuckDB schema...")
    ensure_public_database()
    logger.info("Public DuckDB schema ready.")


def warm_caches(sde_cfg: dict | None = None) -> None:
    """Load SDE dimension data into the in-memory lookup caches."""
    from core.sde import startup_load_sde
    logger.info("Warming SDE in-memory caches...")
    startup_load_sde(sde_cfg or {})
    logger.info("SDE caches warm.")


def initialize_all(sde_cfg: dict | None = None) -> dict:
    """Run the full public initialization sequence (schema then caches).

    Returns the current warehouse status dict.
    """
    from core.db import publicDB
    ensure_schema()
    warm_caches(sde_cfg)
    return publicDB.get_warehouse_status()
