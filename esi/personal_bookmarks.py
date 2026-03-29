# fetchers/private/personal_bookmarks.py

import logging
from datetime import datetime

from db.database import get_private_session
from db.models import PersonalBookmark
from util.esi_rate_limiter import esi_get
from util.utils import get_token

logger = logging.getLogger(__name__)

ESI = "https://esi.evetech.net/latest"
INSERT_BATCH_SIZE = 500


def fetch_bookmarks(char_id: int, access_token: str) -> list:
    """Fetch personal bookmarks for a character."""
    url = f"{ESI}/characters/{char_id}/bookmarks/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers, timeout=30)
    if resp.status_code == 404:
        logger.info("[fetch_bookmarks] character %s has no bookmarks (404)", char_id)
        return []
    resp.raise_for_status()
    bookmarks = resp.json()
    logger.info(
        "[fetch_bookmarks] character %s received %s bookmarks",
        char_id,
        f"{len(bookmarks):,}",
    )
    return bookmarks


def store_bookmarks(owner_id: int, char_id: int, bookmarks: list) -> None:
    """Store personal bookmarks for a character into their owner's private DB."""
    db = get_private_session(owner_id)
    try:
        logger.info(
            "[store_bookmarks] Replacing bookmarks for character %s with %s row(s)",
            char_id,
            f"{len(bookmarks):,}",
        )
        db.query(PersonalBookmark).filter_by(character_id=char_id).delete()

        rows = [
            {
                "bookmark_id": bm["bookmark_id"],
                "character_id": char_id,
                "folder_id": bm.get("folder_id"),
                "location_id": bm.get("location_id"),
                "item_id": bm.get("item_id"),
                "label": bm.get("label", ""),
                "created": datetime.fromisoformat(bm["created"].replace("Z", "+00:00")),
                "coordinates": bm.get("coordinates"),
                "notes": bm.get("notes", ""),
            }
            for bm in bookmarks
        ]

        inserted = 0
        for start in range(0, len(rows), INSERT_BATCH_SIZE):
            batch = rows[start:start + INSERT_BATCH_SIZE]
            db.bulk_insert_mappings(PersonalBookmark, batch)
            inserted += len(batch)
            logger.info(
                "[store_bookmarks] character %s inserted %s/%s bookmarks",
                char_id,
                f"{inserted:,}",
                f"{len(rows):,}",
            )

        db.commit()
        logger.info("[store_bookmarks] Commit complete for character %s", char_id)
    finally:
        db.close()


def update_personal_bookmarks(owner_id: int) -> None:
    """Fetch and store bookmarks for all characters owned by the given owner."""
    tokens = get_token(owner_id)

    for char_id, token_row in tokens.items():
        try:
            logger.info("[update_personal_bookmarks] Fetching bookmarks for character %s", char_id)
            bookmarks = fetch_bookmarks(char_id, token_row["access_token"])
            store_bookmarks(owner_id, char_id, bookmarks)
            logger.info(
                "[update_personal_bookmarks] Stored %s bookmarks for %s",
                len(bookmarks),
                char_id,
            )
        except Exception as exc:
            logger.error("[update_personal_bookmarks] Error updating bookmarks for %s: %s", char_id, exc)
