# esi/personal_calendar.py
import logging
from datetime import datetime

from db.database import get_private_session
from db.models import CalendarEvent
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


def fetch_calendar(char_id: int, access_token: str) -> list:
    resp = esi_get(f"{ESI}/characters/{char_id}/calendar/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_calendar(owner_id: int, char_id: int, events: list):
    db = get_private_session(owner_id)
    db.query(CalendarEvent).filter_by(character_id=char_id).delete()
    for ev in events:
        db.add(CalendarEvent(
            character_id=char_id,
            event_id=ev["event_id"],
            event_date=_dt(ev.get("event_date")),
            title=ev.get("title"),
            duration=ev.get("duration"),
            importance=ev.get("importance"),
            event_response=ev.get("event_response"),
            owner_id=ev.get("owner_id"),
            owner_name=ev.get("owner_name"),
            owner_type=ev.get("owner_type"),
        ))
    db.commit()
    db.close()


def fetch_all_calendar(owner_id: int):
    for char_id, token_row in get_token(owner_id).items():
        try:
            events = fetch_calendar(char_id, token_row["access_token"])
            store_calendar(owner_id, char_id, events)
            logger.info(f"[calendar] {len(events)} events for {char_id}")
        except Exception as e:
            logger.error(f"[calendar] Failed for {char_id}: {e}")
