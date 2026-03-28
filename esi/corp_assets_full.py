# esi/corp_assets_full.py
import logging

from db.database import get_private_session
from db.models import Asset
from util.esi_rate_limiter import esi_get
from util.utils import get_token
from esi._corp_helpers import get_corp_id_for_char, fetch_paginated

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"

# Corp assets are stored in the same Asset table, tagged by character_id=-corp_id
# so they don't collide with personal assets.
# Alternatively a CorpAsset model could be added; using negative corp_id is the simplest approach.


def store_corp_assets(owner_id: int, corp_id: int, assets: list):
    db = get_private_session(owner_id)
    # Use the existing Asset table; tag with negative corp id to distinguish from character assets
    db.query(Asset).filter(Asset.character_id == -corp_id).delete()
    for a in assets:
        db.add(Asset(
            item_id=a["item_id"],
            character_id=-corp_id,
            type_id=a["type_id"],
            location_id=a["location_id"],
            quantity=a.get("quantity", 1),
            location_flag=a.get("location_flag"),
            location_type=a.get("location_type"),
            is_blueprint_copy=a.get("is_blueprint_copy"),
        ))
    db.commit()
    db.close()


def fetch_all_corp_assets(owner_id: int):
    seen = set()
    for char_id, token_row in get_token(owner_id).items():
        corp_id = get_corp_id_for_char(owner_id, char_id)
        if not corp_id or corp_id in seen:
            continue
        seen.add(corp_id)
        try:
            assets = fetch_paginated(
                f"{ESI}/corporations/{corp_id}/assets/",
                token_row["access_token"], esi_get)
            store_corp_assets(owner_id, corp_id, assets)
            logger.info(f"[corp_assets] {len(assets)} assets for corp {corp_id}")
        except Exception as e:
            logger.warning(f"[corp_assets] Skipped corp {corp_id}: {e}")
