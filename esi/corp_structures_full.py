# esi/corp_structures_full.py
import logging

from db.database import get_private_session
from db.models import CorpStructure
from util.esi_rate_limiter import esi_get
from util.utils import get_token
from esi._corp_helpers import get_corp_id_for_char, fetch_paginated, _dt

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def store_corp_structures(owner_id: int, corp_id: int, structures: list):
    db = get_private_session(owner_id)
    from datetime import datetime
    db.query(CorpStructure).filter_by(corporation_id=corp_id).delete()
    for s in structures:
        db.add(CorpStructure(
            structure_id=s["structure_id"],
            corporation_id=corp_id,
            solar_system_id=s.get("system_id"),
            type_id=s.get("type_id"),
            name=s.get("name"),
            profile_id=s.get("profile_id"),
            state=s.get("state"),
            state_timer_end=_dt(s.get("state_timer_end")),
            state_timer_start=_dt(s.get("state_timer_start")),
            unanchors_at=_dt(s.get("unanchors_at")),
            services=s.get("services"),
            fuel_expires=_dt(s.get("fuel_expires")),
            next_reinforce_hour=s.get("next_reinforce_hour"),
            last_seen=datetime.utcnow(),
        ))
    db.commit()
    db.close()


def fetch_all_corp_structures(owner_id: int):
    seen = set()
    for char_id, token_row in get_token(owner_id).items():
        corp_id = get_corp_id_for_char(owner_id, char_id)
        if not corp_id or corp_id in seen:
            continue
        seen.add(corp_id)
        try:
            structures = fetch_paginated(
                f"{ESI}/corporations/{corp_id}/structures/",
                token_row["access_token"], esi_get)
            store_corp_structures(owner_id, corp_id, structures)
            logger.info(f"[corp_structures] {len(structures)} for corp {corp_id}")
        except Exception as e:
            logger.warning(f"[corp_structures] Skipped corp {corp_id}: {e}")
