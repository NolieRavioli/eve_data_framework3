# esi/personal_fittings.py
import logging

from db.database import get_private_session
from db.models import Fitting, FittingItem
from util.esi_rate_limiter import esi_get
from util.utils import get_token

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def fetch_fittings(char_id: int, access_token: str) -> list:
    resp = esi_get(f"{ESI}/characters/{char_id}/fittings/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_fittings(owner_id: int, char_id: int, fittings: list):
    db = get_private_session(owner_id)
    db.query(Fitting).filter_by(character_id=char_id).delete()
    db.query(FittingItem).filter_by(character_id=char_id).delete()
    for f in fittings:
        db.add(Fitting(
            fitting_id=f["fitting_id"],
            character_id=char_id,
            name=f.get("name"),
            ship_type_id=f.get("ship_type_id"),
            description=f.get("description"),
        ))
        for item in f.get("items", []):
            db.add(FittingItem(
                fitting_id=f["fitting_id"],
                flag=item.get("flag", ""),
                character_id=char_id,
                type_id=item["type_id"],
                quantity=item.get("quantity", 1),
            ))
    db.commit()
    db.close()


def fetch_all_fittings(owner_id: int):
    for char_id, token_row in get_token(owner_id).items():
        try:
            fittings = fetch_fittings(char_id, token_row["access_token"])
            store_fittings(owner_id, char_id, fittings)
            logger.info(f"[fittings] {len(fittings)} for {char_id}")
        except Exception as e:
            logger.error(f"[fittings] Failed for {char_id}: {e}")
