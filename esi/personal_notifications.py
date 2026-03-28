# esi/personal_notifications.py
import logging
from datetime import datetime

from db.database import get_private_session
from db.models import Notification
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


def fetch_notifications(char_id: int, access_token: str) -> list:
    resp = esi_get(f"{ESI}/characters/{char_id}/notifications/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_notifications(owner_id: int, char_id: int, notifications: list):
    db = get_private_session(owner_id)
    existing_ids = {row.notification_id
                    for row in db.query(Notification.notification_id)
                    .filter_by(character_id=char_id).all()}
    for n in notifications:
        if n["notification_id"] in existing_ids:
            continue
        db.add(Notification(
            notification_id=n["notification_id"],
            character_id=char_id,
            sender_id=n.get("sender_id"),
            sender_type=n.get("sender_type"),
            timestamp=_dt(n.get("timestamp")),
            notification_type=n.get("type"),
            is_read=n.get("is_read"),
            text=n.get("text"),
        ))
    db.commit()
    db.close()


def fetch_all_notifications(owner_id: int):
    for char_id, token_row in get_token(owner_id).items():
        try:
            notifications = fetch_notifications(char_id, token_row["access_token"])
            store_notifications(owner_id, char_id, notifications)
            logger.info(f"[notifications] {len(notifications)} for {char_id}")
        except Exception as e:
            logger.error(f"[notifications] Failed for {char_id}: {e}")
