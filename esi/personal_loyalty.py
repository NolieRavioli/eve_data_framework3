# esi/personal_loyalty.py
import logging

from db.database import get_private_session
from db.models import LoyaltyPoint
from util.esi_rate_limiter import esi_get
from util.utils import get_token

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def fetch_loyalty(char_id: int, access_token: str) -> list:
    resp = esi_get(f"{ESI}/characters/{char_id}/loyalty/points/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_loyalty(owner_id: int, char_id: int, loyalty: list):
    db = get_private_session(owner_id)
    db.query(LoyaltyPoint).filter_by(character_id=char_id).delete()
    for lp in loyalty:
        db.add(LoyaltyPoint(
            character_id=char_id,
            corporation_id=lp["corporation_id"],
            lp_balance=lp.get("loyalty_points", 0),
        ))
    db.commit()
    db.close()


def fetch_all_loyalty(owner_id: int):
    for char_id, token_row in get_token(owner_id).items():
        try:
            loyalty = fetch_loyalty(char_id, token_row["access_token"])
            store_loyalty(owner_id, char_id, loyalty)
            logger.info(f"[loyalty] {len(loyalty)} corps for {char_id}")
        except Exception as e:
            logger.error(f"[loyalty] Failed for {char_id}: {e}")
