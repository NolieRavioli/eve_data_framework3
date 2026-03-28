# esi/corp_killmails_full.py
import logging

from db.database import get_private_session
from db.models import CorpKillmailRef
from util.esi_rate_limiter import esi_get
from util.utils import get_token
from esi._corp_helpers import get_corp_id_for_char, fetch_paginated

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def store_corp_killmails(owner_id: int, corp_id: int, killmails: list):
    db = get_private_session(owner_id)
    existing = {(r.killmail_id, r.corporation_id)
                for r in db.query(CorpKillmailRef.killmail_id, CorpKillmailRef.corporation_id)
                .filter_by(corporation_id=corp_id).all()}
    for km in killmails:
        key = (km["killmail_id"], corp_id)
        if key in existing:
            continue
        db.add(CorpKillmailRef(
            killmail_id=km["killmail_id"],
            corporation_id=corp_id,
            killmail_hash=km.get("killmail_hash", ""),
            is_victim=False,
            solar_system_id=None,
            killmail_time=None,
        ))
    db.commit()
    db.close()


def fetch_all_corp_killmails(owner_id: int):
    seen = set()
    for char_id, token_row in get_token(owner_id).items():
        corp_id = get_corp_id_for_char(owner_id, char_id)
        if not corp_id or corp_id in seen:
            continue
        seen.add(corp_id)
        try:
            killmails = fetch_paginated(
                f"{ESI}/corporations/{corp_id}/killmails/recent/",
                token_row["access_token"], esi_get)
            store_corp_killmails(owner_id, corp_id, killmails)
            logger.info(f"[corp_killmails] {len(killmails)} refs for corp {corp_id}")
        except Exception as e:
            logger.warning(f"[corp_killmails] Skipped corp {corp_id}: {e}")
