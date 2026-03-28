# esi/corp_standings_full.py
import logging

from db.database import get_private_session
from db.models import CorpStanding
from util.esi_rate_limiter import esi_get
from util.utils import get_token
from esi._corp_helpers import get_corp_id_for_char

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def fetch_standings(corp_id: int, access_token: str) -> list:
    resp = esi_get(f"{ESI}/corporations/{corp_id}/standings/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_standings(owner_id: int, corp_id: int, standings: list):
    db = get_private_session(owner_id)
    db.query(CorpStanding).filter_by(corporation_id=corp_id).delete()
    for s in standings:
        db.add(CorpStanding(
            corporation_id=corp_id,
            from_id=s["from_id"],
            from_type=s.get("from_type"),
            standing=s.get("standing", 0.0),
        ))
    db.commit()
    db.close()


def fetch_all_corp_standings(owner_id: int):
    seen = set()
    for char_id, token_row in get_token(owner_id).items():
        corp_id = get_corp_id_for_char(owner_id, char_id)
        if not corp_id or corp_id in seen:
            continue
        seen.add(corp_id)
        try:
            standings = fetch_standings(corp_id, token_row["access_token"])
            store_standings(owner_id, corp_id, standings)
            logger.info(f"[corp_standings] {len(standings)} for corp {corp_id}")
        except Exception as e:
            logger.warning(f"[corp_standings] Skipped corp {corp_id}: {e}")
