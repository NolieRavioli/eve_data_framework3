# main.py

import logging

from db.database import initialize_public_database
from util.utils import ensure_dependencies, initialize_runtime_environment, load_config, CONFIG_PATH
from util.data_collection_queue import get_collection_queue
from util.sde import startup_load_sde
from webUI.app import start_webUI

logger = logging.getLogger(__name__)


def main() -> None:
    """Entry point that prepares runtime, validates deps, then launches Flask."""

    settings = initialize_runtime_environment()
    ensure_dependencies(settings)

    logger.info("Initializing databases...")
    initialize_public_database()

    # Initialize the DuckDB-backed SDE facade and optionally warm the hot caches.
    # config.yaml -> SDE section controls warm-cache behavior, not warehouse contents.
    cfg = load_config(CONFIG_PATH)
    startup_load_sde(cfg.get("SDE", {}))

    logger.info("Starting background data collection queue...")
    get_collection_queue()  # starts the daemon thread

    logger.info("Starting EVE Data Framework WebUI...")
    start_webUI(settings)


if __name__ == "__main__":
    main()
