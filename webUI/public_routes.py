# webUI/update_public_routes.py

from contextlib import contextmanager
import io
import logging

from flask import Blueprint, render_template, request, url_for

# Public fetchers
from esi.public.market_structure import fetch_all_structure_markets
from analysis.structures import discover_all_structures
from esi.public.market_contracts import fetch_all_public_contracts as fetch_all_contracts
from esi.public.market_station import fetch_all_market_data
from esi.public.static_data import update_sde

# ─────── Setup ────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)
update_public_bp = Blueprint('update_public', __name__, url_prefix="/update_public")


@contextmanager
def _capture_console_logs(level=logging.INFO):
    """Temporarily capture log output into a buffer for display."""

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    try:
        yield stream
    finally:
        root_logger.removeHandler(handler)
        handler.flush()


def _run_with_console_template(title: str, func):
    """Execute `func`, capture logs, and render the console output template."""

    redirect_url = request.referrer or url_for("dashboard.home")
    success = True

    with _capture_console_logs() as buffer:
        try:
            func()
            logger.info("[%s] Task complete.", title)
        except Exception:
            success = False
            logger.exception("[%s] Task failed.", title)

    logs = [line for line in buffer.getvalue().splitlines() if line.strip()]
    return render_template(
        "console_printout.html",
        title=title,
        logs=logs,
        redirect_url=redirect_url,
        success=success,
    )


# ─────── Routes ───────────────────────────────────────────────────────────────


@update_public_bp.route("/structures")
def update_public_structures():
    """Discover all structures from all owners and store them."""

    return _run_with_console_template(
        "UpdatePublic:Structures",
        discover_all_structures,
    )


@update_public_bp.route("/structure_markets")
def update_public_structure_markets():
    """Update market orders from discovered structures (all owners)."""

    return _run_with_console_template(
        "UpdatePublic:StructureMarkets",
        fetch_all_structure_markets,
    )


@update_public_bp.route("/contracts")
def update_public_contracts():
    """Update public contracts across all regions."""

    return _run_with_console_template(
        "UpdatePublic:Contracts",
        fetch_all_contracts,
    )


@update_public_bp.route("/market")
def update_public_market():
    """Update public market orders across all regions."""

    return _run_with_console_template(
        "UpdatePublic:Market",
        fetch_all_market_data,
    )


@update_public_bp.route("/sde")
def update_public_sde():
    """Download and update the Static Data Export (SDE)."""

    return _run_with_console_template(
        "UpdatePublic:SDE",
        update_sde,
    )
