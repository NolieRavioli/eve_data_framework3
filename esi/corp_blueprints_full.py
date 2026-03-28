# esi/corp_blueprints_full.py
import logging

from db.database import get_private_session
from db.models import CorpBlueprint
from util.esi_rate_limiter import esi_get
from util.utils import get_token
from esi._corp_helpers import get_corp_id_for_char, fetch_paginated

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def store_corp_blueprints(owner_id: int, corp_id: int, blueprints: list):
    db = get_private_session(owner_id)
    db.query(CorpBlueprint).filter_by(corporation_id=corp_id).delete()
    for bp in blueprints:
        db.add(CorpBlueprint(
            item_id=bp["item_id"],
            corporation_id=corp_id,
            type_id=bp.get("type_id"),
            location_id=bp.get("location_id", 0),
            location_flag=bp.get("location_flag", ""),
            material_efficiency=bp.get("material_efficiency", 0),
            time_efficiency=bp.get("time_efficiency", 0),
            runs=bp.get("runs", -1),
            quantity=bp.get("quantity", 1),
        ))
    db.commit()
    db.close()


def fetch_all_corp_blueprints(owner_id: int):
    seen = set()
    for char_id, token_row in get_token(owner_id).items():
        corp_id = get_corp_id_for_char(owner_id, char_id)
        if not corp_id or corp_id in seen:
            continue
        seen.add(corp_id)
        try:
            bps = fetch_paginated(
                f"{ESI}/corporations/{corp_id}/blueprints/",
                token_row["access_token"], esi_get)
            store_corp_blueprints(owner_id, corp_id, bps)
            logger.info(f"[corp_blueprints] {len(bps)} for corp {corp_id}")
        except Exception as e:
            logger.warning(f"[corp_blueprints] Skipped corp {corp_id}: {e}")
