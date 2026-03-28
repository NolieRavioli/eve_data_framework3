# esi/personal_attributes.py
import logging
from datetime import datetime

from db.database import get_private_session
from db.models import CharacterAttributes
from util.esi_rate_limiter import esi_get
from util.utils import get_token

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def fetch_attributes(char_id: int, access_token: str) -> dict:
    url = f"{ESI}/characters/{char_id}/attributes/"
    resp = esi_get(url, headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_attributes(owner_id: int, char_id: int, data: dict):
    db = get_private_session(owner_id)
    row = db.get(CharacterAttributes, char_id)
    if row is None:
        row = CharacterAttributes(character_id=char_id)
        db.add(row)
    row.perception = data.get("perception")
    row.memory = data.get("memory")
    row.willpower = data.get("willpower")
    row.intelligence = data.get("intelligence")
    row.charisma = data.get("charisma")
    row.bonus_remaps = data.get("bonus_remaps")
    row.last_remap_date = _parse_dt(data.get("last_remap_date"))
    row.accrued_remap_cooldown_date = _parse_dt(data.get("accrued_remap_cooldown_date"))
    db.commit()
    db.close()


def fetch_all_attributes(owner_id: int):
    for char_id, token_row in get_token(owner_id).items():
        try:
            data = fetch_attributes(char_id, token_row["access_token"])
            store_attributes(owner_id, char_id, data)
            logger.info(f"[attributes] Stored for {char_id}")
        except Exception as e:
            logger.error(f"[attributes] Failed for {char_id}: {e}")
