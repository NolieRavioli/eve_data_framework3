# esi/personal_mining.py
import logging

from db.database import get_private_session
from db.models import MiningLedger
from util.esi_rate_limiter import esi_get
from util.utils import get_token

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def fetch_mining(char_id: int, access_token: str) -> list:
    results, page = [], 1
    headers = {"Authorization": f"Bearer {access_token}"}
    while True:
        resp = esi_get(f"{ESI}/characters/{char_id}/mining/",
                       headers=headers, params={"page": page})
        resp.raise_for_status()
        data = resp.json()
        results.extend(data)
        if page >= int(resp.headers.get("x-pages", 1)):
            break
        page += 1
    return results


def store_mining(owner_id: int, char_id: int, records: list):
    db = get_private_session(owner_id)
    db.query(MiningLedger).filter_by(character_id=char_id).delete()
    for r in records:
        db.add(MiningLedger(
            character_id=char_id,
            date=r.get("date", ""),
            solar_system_id=r.get("solar_system_id", 0),
            type_id=r.get("type_id", 0),
            quantity=r.get("quantity", 0),
        ))
    db.commit()
    db.close()


def fetch_all_mining(owner_id: int):
    for char_id, token_row in get_token(owner_id).items():
        try:
            records = fetch_mining(char_id, token_row["access_token"])
            store_mining(owner_id, char_id, records)
            logger.info(f"[mining] {len(records)} records for {char_id}")
        except Exception as e:
            logger.error(f"[mining] Failed for {char_id}: {e}")
