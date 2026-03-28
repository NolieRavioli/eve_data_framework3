# webUI/personal_routes.py
"""Personal data sync routes — all operations run as background tasks."""

import logging
from flask import Blueprint, redirect, url_for, session
from util import task_queue

from esi.personal_industry_jobs  import fetch_all_industry
from esi.personal_skills         import fetch_all_skills
from esi.personal_assets         import fetch_all_assets
from esi.personal_bookmarks      import update_personal_bookmarks
from esi.personal_wallet         import fetch_all_wallets
from esi.personal_attributes     import fetch_all_attributes
from esi.personal_clones         import fetch_all_clones
from esi.personal_contacts       import fetch_all_contacts
from esi.personal_contracts      import fetch_all_contracts
from esi.personal_mail           import fetch_all_mail
from esi.personal_calendar       import fetch_all_calendar
from esi.personal_notifications  import fetch_all_notifications
from esi.personal_standings      import fetch_all_standings
from esi.personal_fittings       import fetch_all_fittings
from esi.personal_location       import fetch_all_location
from esi.personal_planetary      import fetch_all_planetary
from esi.personal_fatigue        import fetch_all_fatigue
from esi.personal_loyalty        import fetch_all_loyalty
from esi.personal_medals         import fetch_all_medals
from esi.personal_mining         import fetch_all_mining
from esi.personal_orders         import fetch_all_orders
from esi.personal_killmails      import fetch_all_killmails

logger = logging.getLogger(__name__)
update_personal_bp = Blueprint('update_personal', __name__, url_prefix="/update_personal")


def _get_owner():
    owner_id = session.get("owner_id")
    if not owner_id:
        return None
    return owner_id


def _enqueue_and_go(label, fn, owner_id):
    task_id = task_queue.enqueue(label, fn, owner_id, owner_id=owner_id, queue="private")
    return redirect(url_for("tasks.task_progress", task_id=task_id))


@update_personal_bp.route("/assets")
def update_assets():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Personal Assets", fetch_all_assets, o)

@update_personal_bp.route("/industry")
def update_industry():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Personal Industry Jobs", fetch_all_industry, o)

@update_personal_bp.route("/wallet")
def update_wallet():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Personal Wallet", fetch_all_wallets, o)

@update_personal_bp.route("/skills")
def update_skills():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Personal Skills", fetch_all_skills, o)

@update_personal_bp.route("/bookmarks")
def update_bookmarks():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Personal Bookmarks", update_personal_bookmarks, o)

@update_personal_bp.route("/attributes")
def update_attributes():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Char Attributes", fetch_all_attributes, o)

@update_personal_bp.route("/clones")
def update_clones():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Clones & Implants", fetch_all_clones, o)

@update_personal_bp.route("/contacts")
def update_contacts():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Personal Contacts", fetch_all_contacts, o)

@update_personal_bp.route("/contracts")
def update_contracts():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Personal Contracts", fetch_all_contracts, o)

@update_personal_bp.route("/mail")
def update_mail():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Personal Mail", fetch_all_mail, o)

@update_personal_bp.route("/calendar")
def update_calendar():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Calendar Events", fetch_all_calendar, o)

@update_personal_bp.route("/notifications")
def update_notifications():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Notifications", fetch_all_notifications, o)

@update_personal_bp.route("/standings")
def update_standings():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Personal Standings", fetch_all_standings, o)

@update_personal_bp.route("/fittings")
def update_fittings():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Saved Fittings", fetch_all_fittings, o)

@update_personal_bp.route("/location")
def update_location():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Current Location", fetch_all_location, o)

@update_personal_bp.route("/planetary")
def update_planetary():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Planetary Interaction", fetch_all_planetary, o)

@update_personal_bp.route("/fatigue")
def update_fatigue():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Jump Fatigue", fetch_all_fatigue, o)

@update_personal_bp.route("/loyalty")
def update_loyalty():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Loyalty Points", fetch_all_loyalty, o)

@update_personal_bp.route("/medals")
def update_medals():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Medals", fetch_all_medals, o)

@update_personal_bp.route("/mining")
def update_mining():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Mining Ledger", fetch_all_mining, o)

@update_personal_bp.route("/orders")
def update_orders():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Personal Market Orders", fetch_all_orders, o)

@update_personal_bp.route("/killmails")
def update_killmails():
    o = _get_owner()
    if not o: return "Unauthorized", 401
    return _enqueue_and_go("Personal Killmails", fetch_all_killmails, o)
