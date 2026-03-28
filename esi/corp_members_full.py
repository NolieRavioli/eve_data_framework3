# esi/corp_members_full.py
import logging

from db.database import get_private_session
from db.models import CorpMember
from util.esi_rate_limiter import esi_get
from util.utils import get_token
from esi._corp_helpers import get_corp_id_for_char, _dt

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def fetch_member_tracking(corp_id: int, access_token: str) -> list:
    resp = esi_get(f"{ESI}/corporations/{corp_id}/membertracking/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_corp_members(owner_id: int, corp_id: int, members: list):
    db = get_private_session(owner_id)
    db.query(CorpMember).filter_by(corporation_id=corp_id).delete()
    for m in members:
        db.add(CorpMember(
            character_id=m["character_id"],
            corporation_id=corp_id,
            base_id=m.get("base_id"),
            joined=_dt(m.get("start_date")),
            logoff_date=_dt(m.get("logoff_date")),
            logon_date=_dt(m.get("logon_date")),
            ship_type_id=m.get("ship_type_id"),
            start_date=_dt(m.get("start_date")),
            location_id=m.get("location_id"),
        ))
    db.commit()
    db.close()


def fetch_all_corp_members(owner_id: int):
    seen = set()
    for char_id, token_row in get_token(owner_id).items():
        corp_id = get_corp_id_for_char(owner_id, char_id)
        if not corp_id or corp_id in seen:
            continue
        seen.add(corp_id)
        try:
            members = fetch_member_tracking(corp_id, token_row["access_token"])
            store_corp_members(owner_id, corp_id, members)
            logger.info(f"[corp_members] {len(members)} for corp {corp_id}")
        except Exception as e:
            logger.warning(f"[corp_members] Skipped corp {corp_id}: {e}")
