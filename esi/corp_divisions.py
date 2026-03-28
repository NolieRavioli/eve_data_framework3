# esi/corp_divisions.py
import logging

from db.database import get_private_session
from db.models import CorpDivision
from util.esi_rate_limiter import esi_get
from util.utils import get_token
from esi._corp_helpers import get_corp_id_for_char

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def fetch_divisions(corp_id: int, access_token: str) -> dict:
    resp = esi_get(f"{ESI}/corporations/{corp_id}/divisions/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_divisions(owner_id: int, corp_id: int, data: dict):
    db = get_private_session(owner_id)
    db.query(CorpDivision).filter_by(corporation_id=corp_id).delete()
    for div in data.get("hangar", []):
        db.add(CorpDivision(
            corporation_id=corp_id,
            division_number=div.get("division", 0),
            division_type="hangar",
            name=div.get("name"),
        ))
    for div in data.get("wallet", []):
        db.add(CorpDivision(
            corporation_id=corp_id,
            division_number=div.get("division", 0),
            division_type="wallet",
            name=div.get("name"),
        ))
    db.commit()
    db.close()


def fetch_all_corp_divisions(owner_id: int):
    seen = set()
    for char_id, token_row in get_token(owner_id).items():
        corp_id = get_corp_id_for_char(owner_id, char_id)
        if not corp_id or corp_id in seen:
            continue
        seen.add(corp_id)
        try:
            data = fetch_divisions(corp_id, token_row["access_token"])
            store_divisions(owner_id, corp_id, data)
            logger.info(f"[corp_divisions] Stored for corp {corp_id}")
        except Exception as e:
            logger.warning(f"[corp_divisions] Skipped corp {corp_id}: {e}")
