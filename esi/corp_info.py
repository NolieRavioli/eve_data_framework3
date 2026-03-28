# esi/corp_info.py
"""Fetch and store basic corporation info."""
import logging
from datetime import datetime

from db.database import get_private_session
from db.models import CorpInfo
from util.esi_rate_limiter import esi_get
from util.utils import get_token

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def fetch_corp_info(corp_id: int, access_token: str) -> dict:
    resp = esi_get(f"{ESI}/corporations/{corp_id}/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_corp_info(owner_id: int, corp_id: int, data: dict):
    db = get_private_session(owner_id)
    row = db.get(CorpInfo, corp_id)
    if row is None:
        row = CorpInfo(corporation_id=corp_id)
        db.add(row)
    row.alliance_id = data.get("alliance_id")
    row.ceo_id = data.get("ceo_id")
    row.creator_id = data.get("creator_id")
    row.date_founded = data.get("date_founded")
    row.description = data.get("description")
    row.home_station_id = data.get("home_station_id")
    row.member_count = data.get("member_count")
    row.name = data.get("name")
    row.shares = data.get("shares")
    row.tax_rate = data.get("tax_rate")
    row.ticker = data.get("ticker")
    row.war_eligible = data.get("war_eligible")
    row.last_seen = datetime.utcnow()
    db.commit()
    db.close()


def fetch_all_corp_info(owner_id: int):
    seen = set()
    for char_id, token_row in get_token(owner_id).items():
        try:
            db = get_private_session(owner_id)
            from db.models import Character
            char = db.get(Character, char_id)
            corp_id = char.corporation_id if char else None
            db.close()
            if not corp_id or corp_id in seen:
                continue
            seen.add(corp_id)
            data = fetch_corp_info(corp_id, token_row["access_token"])
            store_corp_info(owner_id, corp_id, data)
            logger.info(f"[corp_info] Stored for corp {corp_id}")
        except Exception as e:
            logger.error(f"[corp_info] Failed for char {char_id}: {e}")
