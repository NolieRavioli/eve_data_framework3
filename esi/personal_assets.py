# fetchers/private/personal_assets.py

import logging
import requests

from util.utils import get_token
from db.database import get_private_session
from db.models import Asset
from util.esi_rate_limiter import esi_get

logger = logging.getLogger(__name__)

ESI = "https://esi.evetech.net/latest"
INSERT_BATCH_SIZE = 1000

# ──────── Fetching ─────────────────────────────────────────────────────────────

def fetch_assets(char_id: int, access_token: str) -> list:
    """Fetch all assets for a character using ESI."""
    assets = []
    page = 1
    headers = {"Authorization": f"Bearer {access_token}"}
    total_pages = None

    while True:
        url = f"{ESI}/characters/{char_id}/assets/"
        resp = esi_get(url, headers=headers, params={"page": page})
        resp.raise_for_status()

        data = resp.json()
        assets.extend(data)

        if "x-pages" in resp.headers:
            total_pages = int(resp.headers["x-pages"])
            logger.info(
                "[fetch_assets] character %s page %s/%s (%s assets accumulated)",
                char_id,
                page,
                total_pages,
                f"{len(assets):,}",
            )
            if page >= total_pages:
                break
            page += 1
        else:
            logger.info(
                "[fetch_assets] character %s page %s/%s (%s assets accumulated)",
                char_id,
                page,
                total_pages or 1,
                f"{len(assets):,}",
            )
            break

    return assets

# ──────── Storage ───────────────────────────────────────────────────────────────

def store_assets(owner_id: int, char_id: int, assets: list):
    """Store assets into owner's private database."""
    db = get_private_session(owner_id)

    try:
        logger.info(
            "[store_assets] Clearing existing assets for character %s before writing %s rows",
            char_id,
            f"{len(assets):,}",
        )
        db.query(Asset).filter_by(character_id=char_id).delete()

        rows = [
            {
                "item_id": asset["item_id"],
                "character_id": char_id,
                "type_id": asset["type_id"],
                "location_id": asset["location_id"],
                "quantity": asset.get("quantity", 1),
                "location_type": asset.get("location_type"),
                "location_flag": asset.get("location_flag"),
                "is_blueprint_copy": asset.get("is_blueprint_copy"),
            }
            for asset in assets
        ]

        inserted = 0
        for start in range(0, len(rows), INSERT_BATCH_SIZE):
            batch = rows[start:start + INSERT_BATCH_SIZE]
            db.bulk_insert_mappings(Asset, batch)
            inserted += len(batch)
            logger.info(
                "[store_assets] character %s inserted %s/%s assets",
                char_id,
                f"{inserted:,}",
                f"{len(rows):,}",
            )

        db.commit()
        logger.info("[store_assets] Commit complete for character %s", char_id)
    finally:
        db.close()

# ──────── Orchestrator ───────────────────────────────────────────────────────────

def fetch_all_assets(owner_id: int):
    """Fetch and store assets for all characters owned by this owner."""
    tokens = get_token(owner_id)

    for char_id, token_row in tokens.items():
        logger.info(f"[fetch_all_assets] Fetching assets for character {char_id}")
        try:
            assets = fetch_assets(char_id, token_row["access_token"])
            store_assets(owner_id, char_id, assets)
            logger.info(f"[fetch_all_assets] Stored {len(assets)} assets for {char_id}")
        except requests.HTTPError as e:
            logger.error(f"[fetch_all_assets] Failed fetching assets for {char_id}: {e}")
        except Exception as e:
            logger.error(f"[fetch_all_assets] Unexpected failure for {char_id}: {e}")
            raise
