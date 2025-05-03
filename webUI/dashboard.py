# webUI/dashboard.py

from flask import Blueprint, render_template, session
import logging
from db.database import get_public_session, get_private_session
from db.models import WalletTransaction, Asset, Character
from analysis.job_slots import analyze_slots
from util.sde import name_from_type_id
from util.utils import get_portrait

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route("/")
def home():
    """Landing page (dashboard if logged in, basic page if not)."""
    wallet_txns   = []
    assets        = []
    linked_toons  = {}
    slot_status  = []
    char_id       = None
    owner_id      = None
    logged_in     = False

    if "character_id" in session and "owner_id" in session:
        char_id   = session["character_id"]
        owner_id  = session["owner_id"]
        print(get_portrait(owner_id))
        logged_in = True

        logger.info(f"Loading dashboard for character {char_id}, owner {owner_id}")

        # --- PRIVATE DB: fetch this character’s assets & txns ---
        priv_db = get_private_session(owner_id)
        for char in priv_db.query(Character).all():
            linked_toons[char.name] = char.character_id
        wallet_txns = (
            priv_db
            .query(WalletTransaction)
            .filter_by(character_id=char_id)
            .limit(10)
            .all()
        )
        assets = (
            priv_db
            .query(Asset)
            .filter_by(character_id=char_id)
            .limit(50)
            .all()
        )
        priv_db.close()

        # If you want to run your slot analyzer:
        slot_status = analyze_slots(owner_id)

    return render_template(
        "dashboard.html",
        wallet_txns=wallet_txns,
        assets=assets,
        logged_in=logged_in,
        char_id=char_id,
        owner_id=owner_id,
        linked_toons=linked_toons,
        slot_status=slot_status,
        name_from_id=name_from_type_id
    )
