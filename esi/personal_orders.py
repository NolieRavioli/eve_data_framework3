# esi/personal_orders.py
import logging
from datetime import datetime

from db.database import get_private_session
from db.models import CharacterMarketOrder
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


def _row_from(o: dict, char_id: int, is_history: bool) -> CharacterMarketOrder:
    return CharacterMarketOrder(
        order_id=o["order_id"],
        character_id=char_id,
        type_id=o.get("type_id"),
        location_id=o.get("location_id"),
        region_id=o.get("region_id"),
        is_buy_order=o.get("is_buy_order", False),
        issued=_dt(o.get("issued")),
        duration=o.get("duration", 0),
        price=o.get("price", 0.0),
        volume_remain=o.get("volume_remain", 0),
        volume_total=o.get("volume_total", 0),
        min_volume=o.get("min_volume"),
        escrow=o.get("escrow"),
        is_corporation=o.get("is_corporation"),
        state=o.get("state"),
        is_history=is_history,
    )


def fetch_active_orders(char_id: int, access_token: str) -> list:
    resp = esi_get(f"{ESI}/characters/{char_id}/orders/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def fetch_order_history(char_id: int, access_token: str) -> list:
    results, page = [], 1
    headers = {"Authorization": f"Bearer {access_token}"}
    while True:
        resp = esi_get(f"{ESI}/characters/{char_id}/orders/history/",
                       headers=headers, params={"page": page})
        resp.raise_for_status()
        data = resp.json()
        results.extend(data)
        if page >= int(resp.headers.get("x-pages", 1)):
            break
        page += 1
    return results


def store_orders(owner_id: int, char_id: int, active: list, history: list):
    db = get_private_session(owner_id)
    db.query(CharacterMarketOrder).filter_by(character_id=char_id).delete()
    for o in active:
        db.add(_row_from(o, char_id, False))
    for o in history:
        db.add(_row_from(o, char_id, True))
    db.commit()
    db.close()


def fetch_all_orders(owner_id: int):
    for char_id, token_row in get_token(owner_id).items():
        try:
            active = fetch_active_orders(char_id, token_row["access_token"])
            history = fetch_order_history(char_id, token_row["access_token"])
            store_orders(owner_id, char_id, active, history)
            logger.info(f"[orders] {len(active)} active, {len(history)} history for {char_id}")
        except Exception as e:
            logger.error(f"[orders] Failed for {char_id}: {e}")
