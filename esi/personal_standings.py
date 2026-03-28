# esi/personal_standings.py
import logging

from db.database import get_private_session
from db.models import CharacterStanding
from util.esi_rate_limiter import esi_get
from util.utils import get_token

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def fetch_standings(char_id: int, access_token: str) -> list:
    resp = esi_get(f"{ESI}/characters/{char_id}/standings/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_standings(owner_id: int, char_id: int, standings: list):
    db = get_private_session(owner_id)
    db.query(CharacterStanding).filter_by(character_id=char_id).delete()
    for s in standings:
        db.add(CharacterStanding(
            character_id=char_id,
            from_id=s["from_id"],
            from_type=s.get("from_type"),
            standing=s.get("standing", 0.0),
        ))
    db.commit()
    db.close()


def fetch_all_standings(owner_id: int):
    for char_id, token_row in get_token(owner_id).items():
        try:
            standings = fetch_standings(char_id, token_row["access_token"])
            store_standings(owner_id, char_id, standings)
            logger.info(f"[standings] {len(standings)} for {char_id}")
        except Exception as e:
            logger.error(f"[standings] Failed for {char_id}: {e}")
