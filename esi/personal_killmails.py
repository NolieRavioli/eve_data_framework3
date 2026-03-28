# esi/personal_killmails.py
import logging
from datetime import datetime

from db.database import get_private_session
from db.models import KillmailRef
from util.esi_rate_limiter import esi_get
from util.utils import get_token

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def _dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def fetch_killmails(char_id: int, access_token: str) -> list:
    results, page = [], 1
    headers = {"Authorization": f"Bearer {access_token}"}
    while True:
        resp = esi_get(f"{ESI}/characters/{char_id}/killmails/recent/",
                       headers=headers, params={"page": page})
        resp.raise_for_status()
        data = resp.json()
        results.extend(data)
        if page >= int(resp.headers.get("x-pages", 1)):
            break
        page += 1
    return results


def store_killmails(owner_id: int, char_id: int, killmails: list):
    db = get_private_session(owner_id)
    existing = {r.killmail_id for r in
                db.query(KillmailRef.killmail_id).filter_by(character_id=char_id).all()}
    for km in killmails:
        kid = km["killmail_id"]
        if kid in existing:
            continue
        db.add(KillmailRef(
            killmail_id=kid,
            character_id=char_id,
            killmail_hash=km.get("killmail_hash", ""),
            is_victim=False,   # character feed only returns kills by default; see ESI docs
            solar_system_id=None,
            killmail_time=None,
        ))
    db.commit()
    db.close()


def fetch_all_killmails(owner_id: int):
    for char_id, token_row in get_token(owner_id).items():
        try:
            killmails = fetch_killmails(char_id, token_row["access_token"])
            store_killmails(owner_id, char_id, killmails)
            logger.info(f"[killmails] {len(killmails)} refs for {char_id}")
        except Exception as e:
            logger.error(f"[killmails] Failed for {char_id}: {e}")
