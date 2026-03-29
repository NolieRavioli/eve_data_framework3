# esi/personal_location.py
"""Snapshot of current character location / online status / ship — point-in-time only."""
import logging

from db.database import get_private_session
from db.models import HomeLocation
from util.esi_rate_limiter import esi_get
from util.utils import get_token

logger = logging.getLogger(__name__)
ESI = "https://esi.evetech.net/latest"

# We reuse HomeLocation to store the "last known location" snapshot.
# If you want a history table, add one to models.py.


def fetch_location(char_id: int, access_token: str) -> dict:
    resp = esi_get(f"{ESI}/characters/{char_id}/location/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_location(owner_id: int, char_id: int, location: dict):
    """Update home_location row with last-seen location (solar_system acts as location_id here)."""
    db = get_private_session(owner_id)
    row = db.get(HomeLocation, char_id)
    if row is None:
        row = HomeLocation(character_id=char_id)
        db.add(row)
    row.location_id = location.get("structure_id") or location.get("station_id") or location.get("solar_system_id")
    row.location_type = "structure" if location.get("structure_id") else (
        "station" if location.get("station_id") else "solar_system"
    )
    db.commit()
    db.close()


def fetch_all_location(owner_id: int):
    for char_id, token_row in get_token(owner_id).items():
        try:
            location = fetch_location(char_id, token_row["access_token"])
            store_location(owner_id, char_id, location)
            logger.info(f"[location] Updated for {char_id}")
        except Exception as e:
            logger.error(f"[location] Failed for {char_id}: {e}")
