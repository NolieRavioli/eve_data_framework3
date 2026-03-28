# esi/corp_orders_full.py
import logging

from db.database import get_private_session
from db.models import CorpMarketOrder
from util.esi_rate_limiter import esi_get
from util.utils import get_token
from esi._corp_helpers import get_corp_id_for_char, fetch_paginated, _dt

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"


def _row(o: dict, corp_id: int, is_history: bool) -> CorpMarketOrder:
    return CorpMarketOrder(
        order_id=o["order_id"],
        corporation_id=corp_id,
        type_id=o.get("type_id"),
        location_id=o.get("location_id", 0),
        region_id=o.get("region_id"),
        is_buy_order=o.get("is_buy_order", False),
        issued=_dt(o.get("issued")),
        duration=o.get("duration", 0),
        price=o.get("price", 0.0),
        volume_remain=o.get("volume_remain", 0),
        volume_total=o.get("volume_total", 0),
        min_volume=o.get("min_volume"),
        escrow=o.get("escrow"),
        wallet_division=o.get("wallet_division"),
        state=o.get("state"),
        is_history=is_history,
    )


def fetch_all_corp_orders(owner_id: int):
    seen = set()
    for char_id, token_row in get_token(owner_id).items():
        corp_id = get_corp_id_for_char(owner_id, char_id)
        if not corp_id or corp_id in seen:
            continue
        seen.add(corp_id)
        try:
            active = fetch_paginated(
                f"{ESI}/corporations/{corp_id}/orders/",
                token_row["access_token"], esi_get)
            history = fetch_paginated(
                f"{ESI}/corporations/{corp_id}/orders/history/",
                token_row["access_token"], esi_get)
            db = get_private_session(owner_id)
            db.query(CorpMarketOrder).filter_by(corporation_id=corp_id).delete()
            for o in active:
                db.add(_row(o, corp_id, False))
            for o in history:
                db.add(_row(o, corp_id, True))
            db.commit()
            db.close()
            logger.info(f"[corp_orders] {len(active)} active, {len(history)} history for corp {corp_id}")
        except Exception as e:
            logger.warning(f"[corp_orders] Skipped corp {corp_id}: {e}")
