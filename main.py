# main.py

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ======================= startup block =============================

# Auto-install
import subprocess
import sys
try:
    import sqlalchemy
    import ruamel.yaml
    import flask
    import cryptography
    import requests_oauthlib
    import jwt
    import yaml
except ImportError:
    logger.warning("Missing dependencies. Installing from requirements.txt...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

# load envs
from util.utils import load_config
load_config()

# =========================== main ==============================
from db.database import initialize_public_database
from webUI.app import start_webUI

if __name__ == "__main__":
    logger.info("Initializing databases...")
    initialize_public_database()

    logger.info("Starting EVE Data Framework WebUI...")
    start_webUI()
