# esi/personal_medals.py
import logging
from datetime import datetime

from db.database import get_private_session
from db.models import Medal
from util.esi_rate_limiter import esi_get
from util.utils import get_token

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def _dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def fetch_medals(char_id: int, access_token: str) -> list:
    resp = esi_get(f"{ESI}/characters/{char_id}/medals/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_medals(owner_id: int, char_id: int, medals: list):
    db = get_private_session(owner_id)
    db.query(Medal).filter_by(character_id=char_id).delete()
    for m in medals:
        db.add(Medal(
            medal_id=m["medal_id"],
            character_id=char_id,
            corporation_id=m.get("corporation_id"),
            title=m.get("title"),
            description=m.get("description"),
            date=_dt(m.get("date")),
            issued_by=m.get("issuer_id"),
            reason=m.get("reason"),
            status=m.get("status"),
        ))
    db.commit()
    db.close()


def fetch_all_medals(owner_id: int):
    for char_id, token_row in get_token(owner_id).items():
        try:
            medals = fetch_medals(char_id, token_row["access_token"])
            store_medals(owner_id, char_id, medals)
            logger.info(f"[medals] {len(medals)} for {char_id}")
        except Exception as e:
            logger.error(f"[medals] Failed for {char_id}: {e}")
