# webUI/update_public_routes.py

from flask import Blueprint, redirect, url_for
import logging

# Public fetchers
from esi.public.market_structure import fetch_all_structure_markets, update_structure_market
from analysis.structures import discover_all_structures
from esi.public.market_contracts import fetch_all_public_contracts as fetch_all_contracts
from esi.public.market_station import fetch_all_market_data
from esi.public.static_data import update_sde

# ─────── Setup ────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)
update_public_bp = Blueprint('update_public', __name__, url_prefix="/update_public")

# ─────── Routes ───────────────────────────────────────────────────────────────

@update_public_bp.route("/structures")
def update_public_structures():
    """Discover all structures from all owners and store them."""
    discover_all_structures()
    logger.info("[UpdatePublic] Structure discovery complete.")
    return redirect(url_for("dashboard.home"))

@update_public_bp.route("/structure_markets")
def update_public_structure_markets():
    """Update market orders from discovered structures (all owners)."""
    fetch_all_structure_markets()
    logger.info("[UpdatePublic] Structure market update complete.")
    return redirect(url_for("dashboard.home"))

@update_public_bp.route("/contracts")
def update_public_contracts():
    """Update public contracts across all regions."""
    fetch_all_contracts()
    logger.info("[UpdatePublic] Public contracts fetch complete.")
    return redirect(url_for("dashboard.home"))

@update_public_bp.route("/market")
def update_public_market():
    """Update public market orders across all regions."""
    fetch_all_market_data()
    logger.info("[UpdatePublic] Public market data fetch complete.")
    return redirect(url_for("dashboard.home"))

@update_public_bp.route("/sde")
def update_public_sde():
    """Download and update the Static Data Export (SDE)."""
    update_sde()
    logger.info("[UpdatePublic] Static Data Export update complete.")
    return redirect(url_for("dashboard.home"))
