# applications/dashboard/routes.py
"""Dashboard blueprint — character overview & per-character data views."""

from __future__ import annotations

import logging

from flask import Blueprint, abort, redirect, render_template, session, url_for

from applications._api import base_ctx, require_role
from applications._api import char_data, db, sde, esi_registry

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__, template_folder="templates", static_folder="static")

# ── WebSocket: live character events (sub-phase 5d) ───────────────────────────
from core.bus.websocket import register_websock


def _dashboard_ws_topics(**kwargs):
    """Return bus topics for the current session's owner."""
    owner_id = session.get("owner_id")
    if not owner_id:
        return []
    return [
        f"character/{owner_id}/training",
        f"character/{owner_id}/wallet",
        f"character/{owner_id}/notifications",
    ]


register_websock(
    "/dashboard/ws",
    _dashboard_ws_topics,
    access_level="user",
    required_role="dashboard",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _owner_or_redirect():
    """Return owner_id from session, or redirect to login."""
    owner_id = session.get("owner_id")
    if not owner_id or owner_id <= 0:
        session.clear()
        return None
    return owner_id


def _load_character(owner_id: int, character_id: int) -> dict:
    """Load character or abort 404. Also returns scopes set."""
    char = char_data.get_character(owner_id, character_id)
    if not char:
        abort(404)
    return char


def _character_ctx(owner_id: int, character_id: int, active_tab: str) -> dict:
    """Common context for all character sub-routes."""
    char = _load_character(owner_id, character_id)
    scopes = set(char_data.get_scopes(owner_id, character_id))
    return {
        **base_ctx("dashboard"),
        "owner_id": owner_id,
        "character": char,
        "character_id": character_id,
        "scopes": scopes,
        "active_tab": active_tab,
    }


# ---------------------------------------------------------------------------
# Dashboard index — character card grid
# ---------------------------------------------------------------------------

@dashboard_bp.route("/", strict_slashes=False)
@require_role("dashboard")
def home():
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    try:
        char_exists = char_data.get_character(owner_id, owner_id) is not None
    except Exception:
        char_exists = False
    if not char_exists:
        session.clear()
        return redirect(url_for("auth.login"))

    characters = char_data.get_characters(owner_id)
    esi_status = esi_registry.get_status()

    # Aggregate stats across characters
    total_isk = 0.0
    total_sp = 0
    for c in characters:
        cid = c["character_id"]
        try:
            bal = db.private_query(owner_id, "SELECT balance FROM character_wallet WHERE character_id = :cid ORDER BY rowid DESC LIMIT 1", {"cid": cid})
            if bal:
                total_isk += bal[0].get("balance", 0) or 0
        except Exception:
            pass
        try:
            sp = db.private_query(owner_id, "SELECT total_sp FROM character_skills WHERE character_id = :cid LIMIT 1", {"cid": cid})
            if sp:
                total_sp += sp[0].get("total_sp", 0) or 0
        except Exception:
            pass

    return render_template(
        "dashboard_index.html",
        **base_ctx("dashboard"),
        owner_id=owner_id,
        characters=characters,
        esi_status=esi_status,
        total_isk=total_isk,
        total_sp=total_sp,
    )


# ---------------------------------------------------------------------------
# Character sheet
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>")
@require_role("dashboard")
def character(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "overview")
    return render_template("dashboard_character.html", **ctx)


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/skills")
@require_role("dashboard")
def skills(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "skills")
    try:
        rows = db.private_query(owner_id, "SELECT * FROM character_skills WHERE character_id = :cid", {"cid": character_id})
    except Exception:
        rows = []
    ctx["skills"] = rows
    return render_template("dashboard_skills.html", **ctx)


# ---------------------------------------------------------------------------
# Wallet
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/wallet")
@require_role("dashboard")
def wallet(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "wallet")
    try:
        journal = db.private_query(owner_id, "SELECT * FROM character_wallet WHERE character_id = :cid ORDER BY date DESC LIMIT 200", {"cid": character_id})
    except Exception:
        journal = []
    ctx["journal"] = journal
    return render_template("dashboard_wallet.html", **ctx)


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/assets")
@require_role("dashboard")
def assets(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "assets")
    try:
        rows = db.private_query(owner_id, "SELECT * FROM character_assets WHERE character_id = :cid", {"cid": character_id})
    except Exception:
        rows = []

    # Enrich with SDE names
    for r in rows:
        tid = r.get("type_id")
        if tid:
            r["type_name"] = sde.name_from_type_id(tid) or f"Type {tid}"
    ctx["assets"] = rows
    return render_template("dashboard_assets.html", **ctx)


# ---------------------------------------------------------------------------
# Mail
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/mail")
@require_role("dashboard")
def mail(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "mail")
    try:
        rows = db.private_query(owner_id, "SELECT * FROM character_mail WHERE character_id = :cid ORDER BY timestamp DESC LIMIT 50", {"cid": character_id})
    except Exception:
        rows = []
    ctx["mail"] = rows
    return render_template("dashboard_mail.html", **ctx)


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/contracts")
@require_role("dashboard")
def contracts(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "contracts")
    try:
        rows = db.private_query(owner_id, "SELECT * FROM character_contracts WHERE character_id = :cid ORDER BY date_issued DESC", {"cid": character_id})
    except Exception:
        rows = []
    ctx["contracts"] = rows
    return render_template("dashboard_contracts.html", **ctx)


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/calendar")
@require_role("dashboard")
def calendar(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "calendar")
    try:
        rows = db.private_query(owner_id, "SELECT * FROM character_calendar WHERE character_id = :cid ORDER BY event_date DESC", {"cid": character_id})
    except Exception:
        rows = []
    ctx["calendar_events"] = rows
    return render_template("dashboard_calendar.html", **ctx)


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/contacts")
@require_role("dashboard")
def contacts(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "contacts")
    try:
        rows = db.private_query(owner_id, "SELECT * FROM character_contacts WHERE character_id = :cid ORDER BY standing DESC", {"cid": character_id})
    except Exception:
        rows = []
    ctx["contacts"] = rows
    return render_template("dashboard_contacts.html", **ctx)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/notifications")
@require_role("dashboard")
def notifications(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "notifications")
    try:
        rows = db.private_query(owner_id, "SELECT * FROM character_notifications WHERE character_id = :cid ORDER BY timestamp DESC LIMIT 50", {"cid": character_id})
    except Exception:
        rows = []
    ctx["notifications"] = rows
    return render_template("dashboard_notifications.html", **ctx)


# ---------------------------------------------------------------------------
# Industry
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/industry")
@require_role("dashboard")
def industry(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "industry")
    try:
        rows = db.private_query(owner_id, "SELECT * FROM character_industry WHERE character_id = :cid ORDER BY start_date DESC", {"cid": character_id})
    except Exception:
        rows = []
    for r in rows:
        tid = r.get("blueprint_type_id")
        if tid:
            r["blueprint_name"] = sde.name_from_type_id(tid) or f"Type {tid}"
    ctx["jobs"] = rows
    return render_template("dashboard_industry.html", **ctx)


# ---------------------------------------------------------------------------
# Market (personal orders)
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/market")
@require_role("dashboard")
def market(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "market")
    try:
        rows = db.private_query(owner_id, "SELECT * FROM character_orders WHERE character_id = :cid ORDER BY issued DESC", {"cid": character_id})
    except Exception:
        rows = []
    for r in rows:
        tid = r.get("type_id")
        if tid:
            r["type_name"] = sde.name_from_type_id(tid) or f"Type {tid}"
    ctx["orders"] = rows
    return render_template("dashboard_market.html", **ctx)


# ---------------------------------------------------------------------------
# Blueprints
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/blueprints")
@require_role("dashboard")
def blueprints(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "blueprints")
    try:
        rows = db.private_query(owner_id, "SELECT * FROM character_blueprints WHERE character_id = :cid", {"cid": character_id})
    except Exception:
        rows = []
    for r in rows:
        tid = r.get("type_id")
        if tid:
            r["type_name"] = sde.name_from_type_id(tid) or f"Type {tid}"
    ctx["blueprints"] = rows
    return render_template("dashboard_blueprints.html", **ctx)


# ---------------------------------------------------------------------------
# PI (Planetary Interaction)
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/pi")
@require_role("dashboard")
def pi(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "pi")
    try:
        rows = db.private_query(owner_id, "SELECT * FROM character_planets WHERE character_id = :cid", {"cid": character_id})
    except Exception:
        rows = []
    ctx["planets"] = rows
    return render_template("dashboard_pi.html", **ctx)


# ---------------------------------------------------------------------------
# Mining
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/mining")
@require_role("dashboard")
def mining(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "mining")
    try:
        rows = db.private_query(owner_id, "SELECT * FROM character_mining WHERE character_id = :cid ORDER BY date DESC", {"cid": character_id})
    except Exception:
        rows = []
    for r in rows:
        tid = r.get("type_id")
        if tid:
            r["type_name"] = sde.name_from_type_id(tid) or f"Type {tid}"
    ctx["mining"] = rows
    return render_template("dashboard_mining.html", **ctx)


# ---------------------------------------------------------------------------
# Loyalty Points
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/loyalty")
@require_role("dashboard")
def loyalty(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "loyalty")
    try:
        rows = db.private_query(owner_id, "SELECT * FROM character_loyalty WHERE character_id = :cid ORDER BY loyalty_points DESC", {"cid": character_id})
    except Exception:
        rows = []
    ctx["loyalty"] = rows
    return render_template("dashboard_loyalty.html", **ctx)


# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/research")
@require_role("dashboard")
def research(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "research")
    try:
        rows = db.private_query(owner_id, "SELECT * FROM character_research WHERE character_id = :cid", {"cid": character_id})
    except Exception:
        rows = []
    ctx["research"] = rows
    return render_template("dashboard_research.html", **ctx)


# ---------------------------------------------------------------------------
# Fittings
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/fittings")
@require_role("dashboard")
def fittings(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "fittings")
    try:
        rows = db.private_query(owner_id, "SELECT * FROM character_fittings WHERE character_id = :cid", {"cid": character_id})
    except Exception:
        rows = []
    for r in rows:
        tid = r.get("ship_type_id")
        if tid:
            r["ship_name"] = sde.name_from_type_id(tid) or f"Type {tid}"
    ctx["fittings"] = rows
    return render_template("dashboard_fittings.html", **ctx)


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/standings")
@require_role("dashboard")
def standings(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "standings")
    try:
        rows = db.private_query(owner_id, "SELECT * FROM character_standings WHERE character_id = :cid ORDER BY standing DESC", {"cid": character_id})
    except Exception:
        rows = []
    ctx["standings"] = rows
    return render_template("dashboard_standings.html", **ctx)


# ---------------------------------------------------------------------------
# Killmails
# ---------------------------------------------------------------------------

@dashboard_bp.route("/character/<int:character_id>/killmails")
@require_role("dashboard")
def killmails(character_id):
    owner_id = _owner_or_redirect()
    if not owner_id:
        return redirect(url_for("auth.login"))

    ctx = _character_ctx(owner_id, character_id, "killmails")
    try:
        rows = db.private_query(owner_id, "SELECT * FROM character_killmails WHERE character_id = :cid ORDER BY killmail_time DESC LIMIT 50", {"cid": character_id})
    except Exception:
        rows = []
    ctx["killmails"] = rows
    return render_template("dashboard_killmails.html", **ctx)
