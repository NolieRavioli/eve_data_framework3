# webUI/update_personal_routes.py

import logging

from flask import Blueprint, redirect, url_for, session

# Private fetchers
from esi.personal_assets import fetch_all_assets
from esi.personal_blueprints import fetch_all_blueprints
from esi.personal_industry_jobs import fetch_all_industry
from esi.personal_bookmarks import update_personal_bookmarks
from esi.personal_skills import fetch_all_skills
from esi.personal_wallet import (
    fetch_all_balance as fetch_wallet_balances,
    fetch_all_journals as fetch_wallet_journals,
    fetch_all_transactions as fetch_wallet_transactions,
    fetch_all_wallets,
)


# ──────── Setup ──────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)
update_personal_bp = Blueprint('update_personal', __name__, url_prefix="/update_personal")

# ──────── Private Data Update Endpoints ───────────────────────────────────────

@update_personal_bp.route("/assets")
def update_assets():
    """Trigger a refresh of personal assets."""

    owner_id = session.get("owner_id")
    if not owner_id:
        return "Unauthorized", 401
    fetch_all_assets(owner_id)
    logger.info(f"[UpdatePersonal] Fetched assets for owner {owner_id}")
    return redirect(url_for("dashboard.home"))

@update_personal_bp.route("/industry")
def update_industry():
    """Trigger a refresh of personal industry jobs."""

    owner_id = session.get("owner_id")
    if not owner_id:
        return "Unauthorized", 401
    fetch_all_industry(owner_id)
    logger.info(f"[UpdatePersonal] Fetched industry jobs for owner {owner_id}")
    return redirect(url_for("dashboard.home"))

@update_personal_bp.route("/wallet")
def update_wallet():
    """Trigger a refresh of personal wallet transactions."""
    owner_id = session.get("owner_id")
    if not owner_id:
        return "Unauthorized", 401
    fetch_all_wallets(owner_id)
    logger.info(f"[UpdatePersonal] Fetched wallet transactions for owner {owner_id}")
    return redirect(url_for("dashboard.home"))


@update_personal_bp.route("/wallet/transactions")
def update_wallet_transactions():
    """Refresh only wallet transactions for linked characters."""

    owner_id = session.get("owner_id")
    if not owner_id:
        return "Unauthorized", 401

    fetch_wallet_transactions(owner_id)
    logger.info(
        f"[UpdatePersonal] Fetched wallet transactions for owner {owner_id}"
    )
    return redirect(url_for("dashboard.home"))


@update_personal_bp.route("/wallet/journal")
def update_wallet_journal():
    """Refresh only wallet journal entries for linked characters."""

    owner_id = session.get("owner_id")
    if not owner_id:
        return "Unauthorized", 401

    fetch_wallet_journals(owner_id)
    logger.info(f"[UpdatePersonal] Fetched wallet journal for owner {owner_id}")
    return redirect(url_for("dashboard.home"))


@update_personal_bp.route("/wallet/balance")
def update_wallet_balance():
    """Refresh wallet balances for linked characters."""

    owner_id = session.get("owner_id")
    if not owner_id:
        return "Unauthorized", 401

    fetch_wallet_balances(owner_id)
    logger.info(f"[UpdatePersonal] Fetched wallet balance for owner {owner_id}")
    return redirect(url_for("dashboard.home"))

@update_personal_bp.route("/skills")
def update_skills():
    """Trigger a refresh of personal skills."""
    owner_id = session.get("owner_id")
    if not owner_id:
        return "Unauthorized", 401
    fetch_all_skills(owner_id)
    logger.info(f"[UpdatePersonal] Fetched skills for owner {owner_id}")
    return redirect(url_for("dashboard.home"))

@update_personal_bp.route("/bookmarks")
def update_bookmarks():
    """Trigger a refresh of personal bookmarks."""
    owner_id = session.get("owner_id")
    if not owner_id:
        return "Unauthorized", 401
    update_personal_bookmarks(owner_id)
    logger.info(f"[UpdatePersonal] Fetched bookmarks for owner {owner_id}")
    return redirect(url_for("dashboard.home"))


@update_personal_bp.route("/blueprints")
def update_blueprints():
    """Trigger a refresh of personal blueprints."""

    owner_id = session.get("owner_id")
    if not owner_id:
        return "Unauthorized", 401

    fetch_all_blueprints(owner_id)
    logger.info(f"[UpdatePersonal] Fetched blueprints for owner {owner_id}")
    return redirect(url_for("dashboard.home"))
