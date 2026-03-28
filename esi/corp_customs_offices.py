# esi/corp_customs_offices.py
import logging

from db.database import get_private_session
from db.models import CorpCustomsOffice
from util.esi_rate_limiter import esi_get
from util.utils import get_token
from esi._corp_helpers import get_corp_id_for_char, fetch_paginated

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def store_customs_offices(owner_id: int, corp_id: int, offices: list):
    db = get_private_session(owner_id)
    db.query(CorpCustomsOffice).filter_by(corporation_id=corp_id).delete()
    for o in offices:
        db.add(CorpCustomsOffice(
            item_id=o["office_id"],
            corporation_id=corp_id,
            solar_system_id=o.get("solar_system_id"),
            allowed_access=o.get("allowed_access"),
            reinforce_exit_end=o.get("reinforce_exit_end"),
            reinforce_exit_start=o.get("reinforce_exit_start"),
            standing_level=o.get("standing_level"),
            tax_rates=o.get("tax_rates"),
        ))
    db.commit()
    db.close()


def fetch_all_corp_customs_offices(owner_id: int):
    seen = set()
    for char_id, token_row in get_token(owner_id).items():
        corp_id = get_corp_id_for_char(owner_id, char_id)
        if not corp_id or corp_id in seen:
            continue
        seen.add(corp_id)
        try:
            offices = fetch_paginated(
                f"{ESI}/corporations/{corp_id}/customs_offices/",
                token_row["access_token"], esi_get)
            store_customs_offices(owner_id, corp_id, offices)
            logger.info(f"[corp_customs_offices] {len(offices)} for corp {corp_id}")
        except Exception as e:
            logger.warning(f"[corp_customs_offices] Skipped corp {corp_id}: {e}")
