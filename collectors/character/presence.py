"""collectors/character/presence.py — character location, online status, and current ship.

Registered scheduler job: ``character_presence_refresh`` (interval 5 min, **starts disabled**).

This job is high-frequency and should only be enabled by the operator deliberately.
"""

from __future__ import annotations

import logging

import core.io.public as db
from core.auth.tokens import pick_token, fresh_token
from core.io.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"

REQUIRED_SCOPES = {
    "location": "esi-location.read_location.v1",
    "online": "esi-location.read_online.v1",
    "ship": "esi-location.read_ship_type.v1",
}


def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_presence (
            character_id            BIGINT PRIMARY KEY,
            -- location
            solar_system_id         INTEGER,
            station_id              BIGINT,
            structure_id            BIGINT,
            -- online
            is_online               BOOLEAN DEFAULT FALSE,
            last_login              TIMESTAMP,
            last_logout             TIMESTAMP,
            logins                  INTEGER,
            -- ship
            ship_type_id            INTEGER,
            ship_item_id            BIGINT,
            ship_name               TEXT,
            fetched_at              TIMESTAMP DEFAULT now()
        )
    """)


def _fetch_location(character_id: int, headers: dict) -> dict:
    url = f"{ESI_BASE}/characters/{character_id}/location/"
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        return {}
    return resp.json()


def _fetch_online(character_id: int, headers: dict) -> dict:
    url = f"{ESI_BASE}/characters/{character_id}/online/"
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        return {}
    return resp.json()


def _fetch_ship(character_id: int, headers: dict) -> dict:
    url = f"{ESI_BASE}/characters/{character_id}/ship/"
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        return {}
    return resp.json()


def fetch_presence(owner_id: int, character_id: int, access_token: str) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}
    loc = _fetch_location(character_id, headers)
    online = _fetch_online(character_id, headers)
    ship = _fetch_ship(character_id, headers)

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        con.execute("""
            INSERT INTO character_presence
                (character_id, solar_system_id, station_id, structure_id,
                 is_online, last_login, last_logout, logins,
                 ship_type_id, ship_item_id, ship_name, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
            ON CONFLICT (character_id) DO UPDATE SET
                solar_system_id = excluded.solar_system_id,
                station_id      = excluded.station_id,
                structure_id    = excluded.structure_id,
                is_online       = excluded.is_online,
                last_login      = excluded.last_login,
                last_logout     = excluded.last_logout,
                logins          = excluded.logins,
                ship_type_id    = excluded.ship_type_id,
                ship_item_id    = excluded.ship_item_id,
                ship_name       = excluded.ship_name,
                fetched_at      = now()
        """, [character_id,
              loc.get("solar_system_id"), loc.get("station_id"), loc.get("structure_id"),
              online.get("online", False), online.get("last_login"),
              online.get("last_logout"), online.get("logins"),
              ship.get("ship_type_id"), ship.get("ship_item_id"), ship.get("ship_name")])
    finally:
        con.close()
    logger.debug("[presence] updated for char %s", character_id)


def run_presence_refresh() -> None:
    """Public entry point — called by the scheduler (starts disabled)."""
    con = db.connect()
    try:
        rows = con.execute("SELECT DISTINCT owner_id FROM auth_users").fetchall()
        owner_ids = [r[0] for r in rows]
    finally:
        con.close()

    for owner_id in owner_ids:
        try:
            char_id, token_data = pick_token(owner_id)
            char_id, token_data = fresh_token(owner_id, char_id, token_data)
        except Exception:
            logger.warning("[presence] no token for owner %s", owner_id)
            continue

        scopes = set((token_data.get("scopes") or "").split())
        # Run if at least location scope is present
        if REQUIRED_SCOPES["location"] not in scopes:
            continue

        try:
            fetch_presence(owner_id, char_id, token_data["access_token"])
        except Exception:
            logger.exception("[presence] failed for owner %s char %s", owner_id, char_id)
