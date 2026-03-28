# esi/personal_clones.py
import logging
from datetime import datetime

from db.database import get_private_session
from db.models import HomeLocation, JumpClone, ActiveImplant
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


def fetch_clones(char_id: int, access_token: str) -> dict:
    url = f"{ESI}/characters/{char_id}/clones/"
    resp = esi_get(url, headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def fetch_implants(char_id: int, access_token: str) -> list:
    url = f"{ESI}/characters/{char_id}/implants/"
    resp = esi_get(url, headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_clones(owner_id: int, char_id: int, data: dict, implants: list):
    db = get_private_session(owner_id)

    # Home location
    home = data.get("home_location", {})
    row = db.get(HomeLocation, char_id)
    if row is None:
        row = HomeLocation(character_id=char_id)
        db.add(row)
    row.location_id = home.get("location_id")
    row.location_type = home.get("location_type")

    # Jump clones – replace all
    db.query(JumpClone).filter_by(character_id=char_id).delete()
    for clone in data.get("jump_clones", []):
        db.add(JumpClone(
            jump_clone_id=clone["jump_clone_id"],
            character_id=char_id,
            location_id=clone.get("location_id"),
            location_type=clone.get("location_type"),
            clone_name=clone.get("name"),
            implants=clone.get("implants", []),
        ))

    # Active implants – replace all
    db.query(ActiveImplant).filter_by(character_id=char_id).delete()
    for type_id in implants:
        db.add(ActiveImplant(character_id=char_id, implant_type_id=type_id))

    db.commit()
    db.close()


def fetch_all_clones(owner_id: int):
    for char_id, token_row in get_token(owner_id).items():
        try:
            data = fetch_clones(char_id, token_row["access_token"])
            implants = fetch_implants(char_id, token_row["access_token"])
            store_clones(owner_id, char_id, data, implants)
            logger.info(f"[clones] Stored for {char_id}: "
                        f"{len(data.get('jump_clones', []))} clones, "
                        f"{len(implants)} implants")
        except Exception as e:
            logger.error(f"[clones] Failed for {char_id}: {e}")
