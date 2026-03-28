# esi/personal_fatigue.py
import logging
from datetime import datetime

from db.database import get_private_session
from db.models import JumpFatigue
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


def fetch_fatigue(char_id: int, access_token: str) -> dict:
    resp = esi_get(f"{ESI}/characters/{char_id}/fatigue/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_fatigue(owner_id: int, char_id: int, data: dict):
    db = get_private_session(owner_id)
    row = db.get(JumpFatigue, char_id)
    if row is None:
        row = JumpFatigue(character_id=char_id)
        db.add(row)
    row.jump_fatigue = _dt(data.get("jump_fatigue_expire_date"))
    row.last_jump_date = _dt(data.get("last_jump_date"))
    row.jump_fatigue_expire_date = _dt(data.get("jump_fatigue_expire_date"))
    db.commit()
    db.close()


def fetch_all_fatigue(owner_id: int):
    for char_id, token_row in get_token(owner_id).items():
        try:
            data = fetch_fatigue(char_id, token_row["access_token"])
            store_fatigue(owner_id, char_id, data)
            logger.info(f"[fatigue] Updated for {char_id}")
        except Exception as e:
            logger.error(f"[fatigue] Failed for {char_id}: {e}")
