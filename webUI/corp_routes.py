# webUI/corp_routes.py
"""Corporation data sync routes — all operations run as background tasks."""

import logging
from flask import Blueprint, redirect, url_for, session
from util import task_queue

from esi.corp_info              import fetch_all_corp_info
from esi.corp_assets_full       import fetch_all_corp_assets
from esi.corp_blueprints_full   import fetch_all_corp_blueprints
from esi.corp_contacts_full     import fetch_all_corp_contacts
from esi.corp_contracts_full    import fetch_all_corp_contracts
from esi.corp_customs_offices   import fetch_all_corp_customs_offices
from esi.corp_divisions         import fetch_all_corp_divisions
from esi.corp_industry_full     import fetch_all_corp_industry
from esi.corp_killmails_full    import fetch_all_corp_killmails
from esi.corp_members_full      import fetch_all_corp_members
from esi.corp_mining_full       import fetch_all_corp_mining
from esi.corp_orders_full       import fetch_all_corp_orders
from esi.corp_roles_full        import fetch_all_corp_roles
from esi.corp_standings_full    import fetch_all_corp_standings
from esi.corp_structures_full   import fetch_all_corp_structures
from esi.corp_wallet_full       import fetch_all_corp_wallet

logger = logging.getLogger(__name__)
update_corp_bp = Blueprint("update_corp", __name__, url_prefix="/update_corp")


def _get_owner():
    owner_id = session.get("owner_id")
    if not owner_id:
        return None
    return owner_id


def _enqueue_and_go(label, fn, owner_id):
    task_id = task_queue.enqueue(label, fn, owner_id, owner_id=owner_id, queue="private")
    return redirect(url_for("tasks.task_progress", task_id=task_id))


@update_corp_bp.route("/info")
def update_corp_info():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Corp Info", fetch_all_corp_info, o)

@update_corp_bp.route("/assets")
def update_corp_assets():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Corp Assets", fetch_all_corp_assets, o)

@update_corp_bp.route("/blueprints")
def update_corp_blueprints():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Corp Blueprints", fetch_all_corp_blueprints, o)

@update_corp_bp.route("/contacts")
def update_corp_contacts():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Corp Contacts", fetch_all_corp_contacts, o)

@update_corp_bp.route("/contracts")
def update_corp_contracts():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Corp Contracts", fetch_all_corp_contracts, o)

@update_corp_bp.route("/customs_offices")
def update_corp_customs_offices():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Customs Offices", fetch_all_corp_customs_offices, o)

@update_corp_bp.route("/divisions")
def update_corp_divisions():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Corp Divisions", fetch_all_corp_divisions, o)

@update_corp_bp.route("/industry")
def update_corp_industry():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Corp Industry", fetch_all_corp_industry, o)

@update_corp_bp.route("/killmails")
def update_corp_killmails():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Corp Killmails", fetch_all_corp_killmails, o)

@update_corp_bp.route("/members")
def update_corp_members():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Corp Members", fetch_all_corp_members, o)

@update_corp_bp.route("/mining")
def update_corp_mining():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Corp Mining", fetch_all_corp_mining, o)

@update_corp_bp.route("/orders")
def update_corp_orders():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Corp Market Orders", fetch_all_corp_orders, o)

@update_corp_bp.route("/roles")
def update_corp_roles():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Corp Roles", fetch_all_corp_roles, o)

@update_corp_bp.route("/standings")
def update_corp_standings():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Corp Standings", fetch_all_corp_standings, o)

@update_corp_bp.route("/structures")
def update_corp_structures():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Corp Structures", fetch_all_corp_structures, o)

@update_corp_bp.route("/wallet")
def update_corp_wallet():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Corp Wallet", fetch_all_corp_wallet, o)
