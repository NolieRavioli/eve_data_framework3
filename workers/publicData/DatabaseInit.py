# workers/publicData/DatabaseInit.py
"""Public database initialization worker.

Ensures the operational DuckDB schema exists and warms the in-memory SDE
caches.  Two usage patterns are supported:

**Synchronous startup** (blocking, completes before Flask serves requests)::

    from workers.publicData.DatabaseInit import initialize_all
    initialize_all(cfg.get("SDE", {}))

**Runtime re-initialization** (via the background task queue)::

    from workers.publicData.DatabaseInit import initialize_all
    from tasks.task_queue import enqueue
    task_id = enqueue("Re-init public DB", initialize_all, owner_id=0, queue="public")
"""

import logging

logger = logging.getLogger(__name__)


def ensure_schema() -> None:
    """Create / migrate the DuckDB operational schema (fast — idempotent)."""
    from db import sde_store
    logger.info("Ensuring public DuckDB schema...")
    sde_store.ensure_public_database()
    logger.info("Public DuckDB schema ready.")


def warm_caches(sde_cfg: dict | None = None) -> None:
    """Load SDE dimension data into the in-memory lookup caches."""
    from sde import startup_load_sde
    logger.info("Warming SDE in-memory caches...")
    startup_load_sde(sde_cfg or {})
    logger.info("SDE caches warm.")


def initialize_all(sde_cfg: dict | None = None) -> dict:
    """Run the full public initialization sequence (schema then caches).

    Returns the current warehouse status dict from :func:`sde_store.get_warehouse_status`.
    """
    from db import sde_store
    ensure_schema()
    warm_caches(sde_cfg)
    return sde_store.get_warehouse_status()
