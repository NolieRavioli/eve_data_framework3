# esi/personal_planetary.py
import logging
from datetime import datetime

from db.database import get_private_session
from db.models import PlanetaryColony, PlanetaryPin, PlanetaryRoute
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


def fetch_colonies(char_id: int, access_token: str) -> list:
    resp = esi_get(f"{ESI}/characters/{char_id}/planets/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def fetch_colony_detail(char_id: int, planet_id: int, access_token: str) -> dict:
    resp = esi_get(f"{ESI}/characters/{char_id}/planets/{planet_id}/",
                   headers={"Authorization": f"Bearer {access_token}"})
    resp.raise_for_status()
    return resp.json()


def store_planetary(owner_id: int, char_id: int, colonies: list, access_token: str):
    db = get_private_session(owner_id)
    db.query(PlanetaryColony).filter_by(character_id=char_id).delete()
    db.query(PlanetaryPin).filter_by(character_id=char_id).delete()
    db.query(PlanetaryRoute).filter_by(character_id=char_id).delete()

    for colony in colonies:
        planet_id = colony["planet_id"]
        db.add(PlanetaryColony(
            character_id=char_id,
            planet_id=planet_id,
            planet_type=colony.get("planet_type"),
            solar_system_id=colony.get("solar_system_id"),
            last_update=_dt(colony.get("last_update")),
            num_pins=colony.get("num_pins"),
            upgrade_level=colony.get("upgrade_level"),
        ))
        try:
            detail = fetch_colony_detail(char_id, planet_id, access_token)
        except Exception as de:
            logger.warning(f"[planetary] Could not fetch detail for planet {planet_id}: {de}")
            continue

        for pin in detail.get("pins", []):
            db.add(PlanetaryPin(
                pin_id=pin["pin_id"],
                character_id=char_id,
                planet_id=planet_id,
                type_id=pin.get("type_id", 0),
                latitude=pin.get("latitude"),
                longitude=pin.get("longitude"),
                install_time=_dt(pin.get("install_time")),
                expiry_time=_dt(pin.get("expiry_time")),
                last_cycle_start=_dt(pin.get("last_cycle_start")),
                contents=pin.get("contents"),
                extractor_details=pin.get("extractor_details"),
                factory_details=pin.get("factory_details"),
            ))

        for route in detail.get("routes", []):
            db.add(PlanetaryRoute(
                route_id=route["route_id"],
                character_id=char_id,
                planet_id=planet_id,
                destination_pin_id=route["destination_pin_id"],
                source_pin_id=route["source_pin_id"],
                content_type_id=route.get("content_type_id", 0),
                quantity=route.get("quantity", 0),
                waypoints=route.get("waypoints"),
            ))

    db.commit()
    db.close()


def fetch_all_planetary(owner_id: int):
    for char_id, token_row in get_token(owner_id).items():
        try:
            colonies = fetch_colonies(char_id, token_row["access_token"])
            store_planetary(owner_id, char_id, colonies, token_row["access_token"])
            logger.info(f"[planetary] {len(colonies)} colonies for {char_id}")
        except Exception as e:
            logger.error(f"[planetary] Failed for {char_id}: {e}")
