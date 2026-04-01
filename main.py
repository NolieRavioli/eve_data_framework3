import atexit
import logging

from config import CONFIG_PATH, ensure_dependencies, initialize_runtime_environment, load_config
from core.db import initialize_all
from core.queue.writer import start_writer, stop_writer
from core.web.app import start_webUI

logger = logging.getLogger(__name__)


def main() -> None:
    settings = initialize_runtime_environment()
    ensure_dependencies(settings)

    cfg = load_config(CONFIG_PATH)
    initialize_all(cfg.get("SDE", {}))

    # Start the serialized DuckDB write channel before Flask handles requests.
    start_writer()
    atexit.register(stop_writer)

    logger.info("Starting EVE Data Framework WebUI...")
    start_webUI(settings)


if __name__ == "__main__":
    main()

