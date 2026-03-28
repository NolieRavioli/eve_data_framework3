# esi/corp_mining_full.py
import logging

from db.database import get_private_session
from db.models import CorpMining
from util.esi_rate_limiter import esi_get
from util.utils import get_token
from esi._corp_helpers import get_corp_id_for_char, fetch_paginated

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def fetch_observer_ledger(corp_id: int, observer_id: int, access_token: str) -> list:
    return fetch_paginated(
        f"{ESI}/corporations/{corp_id}/mining/observers/{observer_id}/",
        access_token, esi_get)


def store_corp_mining(owner_id: int, corp_id: int, observers: list, access_token: str):
    db = get_private_session(owner_id)
    db.query(CorpMining).filter_by(corporation_id=corp_id).delete()
    for obs in observers:
        observer_id = obs["observer_id"]
        observer_type = obs.get("observer_type")
        try:
            records = fetch_observer_ledger(corp_id, observer_id, access_token)
        except Exception as e:
            logger.warning(f"[corp_mining] observer {observer_id} failed: {e}")
            continue
        for r in records:
            db.add(CorpMining(
                corporation_id=corp_id,
                observer_id=observer_id,
                observed_character_id=r.get("character_id", 0),
                type_id=r.get("type_id", 0),
                last_updated=r.get("last_updated", ""),
                quantity=r.get("quantity", 0),
                observer_type=observer_type,
            ))
    db.commit()
    db.close()


def fetch_all_corp_mining(owner_id: int):
    seen = set()
    for char_id, token_row in get_token(owner_id).items():
        corp_id = get_corp_id_for_char(owner_id, char_id)
        if not corp_id or corp_id in seen:
            continue
        seen.add(corp_id)
        try:
            observers = fetch_paginated(
                f"{ESI}/corporations/{corp_id}/mining/observers/",
                token_row["access_token"], esi_get)
            store_corp_mining(owner_id, corp_id, observers, token_row["access_token"])
            logger.info(f"[corp_mining] {len(observers)} observers for corp {corp_id}")
        except Exception as e:
            logger.warning(f"[corp_mining] Skipped corp {corp_id}: {e}")
