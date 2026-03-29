import logging

from util import sde_store
from util.sde import startup_load_sde
from util.utils import CONFIG_PATH, ensure_dependencies, initialize_runtime_environment, load_config
from webUI.app import start_webUI

logger = logging.getLogger(__name__)


def main() -> None:
    settings = initialize_runtime_environment()
    ensure_dependencies(settings)

    logger.info("Initializing SDE warehouse...")
    cfg = load_config(CONFIG_PATH)
    startup_load_sde(cfg.get("SDE", {}))
    sde_store.ensure_public_database()

    logger.info("Starting EVE Data Framework WebUI...")
    start_webUI(settings)


if __name__ == "__main__":
    main()
