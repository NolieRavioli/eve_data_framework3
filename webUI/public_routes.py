# webUI/public_routes.py
"""Public/SDE sync routes — all operations run as background tasks."""

import logging
from flask import Blueprint, redirect, session, url_for
from util import task_queue

from esi.public.market_structure import fetch_all_structure_markets
from analysis.structures         import discover_all_structures
from esi.public.market_contracts import fetch_all_public_contracts
from esi.public.market_station   import fetch_all_market_data
from esi.public.static_data      import update_sde

logger = logging.getLogger(__name__)
update_public_bp = Blueprint('update_public', __name__, url_prefix="/update_public")


def _get_owner():
    owner_id = session.get("owner_id")
    if not owner_id:
        return None
    return owner_id


def _enqueue_and_go(label, fn, owner_id):
    task_id = task_queue.enqueue(label, fn, owner_id=owner_id, queue="public")
    return redirect(url_for("tasks.task_progress", task_id=task_id))


@update_public_bp.route("/structures")
def update_public_structures():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Discover Structures", discover_all_structures, o)

@update_public_bp.route("/structure_markets")
def update_public_structure_markets():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Structure Market Refresh", fetch_all_structure_markets, o)

@update_public_bp.route("/contracts")
def update_public_contracts():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Public Contracts", fetch_all_public_contracts, o)

@update_public_bp.route("/market")
def update_public_market():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Station Market Orders", fetch_all_market_data, o)

@update_public_bp.route("/sde")
def update_public_sde():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("SDE Refresh", update_sde, o)
