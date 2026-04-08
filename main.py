import logging
import os
import time

from core.config import ensure_dependencies, get_sde_config, initialize_runtime_environment

logger = logging.getLogger(__name__)


def main() -> None:
    # If we were spawned by restart_process(), give the old process a moment
    # to fully exit and release the port / DuckDB file lock.
    if os.environ.pop("_EVE_RESTART_DELAY", None):
        time.sleep(1)

    # ── 1. Config → RAM (single load, cached forever) ─────────────────────
    settings = initialize_runtime_environment()
    ensure_dependencies(settings)

    # ── 2. Bus handler (zero-dep message infrastructure) ──────────────────
    from core.bus import install_bus_handler as _install_bus_handler
    _install_bus_handler()

    # ── 3. System lifecycle coordinator ───────────────────────────────────
    from core.system import get_lifecycle
    lifecycle = get_lifecycle()

    # ── 4. DB writer thread (registers with lifecycle) ────────────────────
    from core.db.writer import start_writer
    start_writer()

    # ── 5. Ensure public database exists (DDL only — fast, idempotent) ────
    from core.db import ensure_schema
    ensure_schema()

    # ── 6. Bootstrap: ensure ESI codegen + SDE warehouse are current ───────
    from core.system.bootstrap import bootstrap_all
    bootstrap_all(settings)

    # ── 7. Warm SDE in-memory caches ──────────────────────────────────────
    from core.db import warm_caches
    warm_caches(get_sde_config())

    # ── 8. Collector tables + ESI cache ───────────────────────────────────
    from core.db import initialize_collector_tables, seed_esi_cache
    initialize_collector_tables()
    seed_esi_cache()

    # ── 9. Scheduler engine (registers with lifecycle) ────────────────────
    from core.tasks.engine import get_engine
    from core.tasks.jobs import register_all_jobs
    scheduler = get_engine()
    register_all_jobs(scheduler)
    scheduler.start()

    # ── 10. Stats & process publishers (register with lifecycle) ──────────
    from core.db.stats import start_db_stats_publisher
    from core.bus.process_pub import start_process_publisher
    start_db_stats_publisher()
    start_process_publisher()

    # ── 11. Flask web server ──────────────────────────────────────────────
    logger.info("Starting EVE Data Framework WebUI...")
    from core.web.app import start_webUI
    start_webUI(settings)


if __name__ == "__main__":
    main()

