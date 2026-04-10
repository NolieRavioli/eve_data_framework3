"""collectors/corp/assets.py — corp_assets and corp_blueprints."""

from __future__ import annotations

import logging

from core.io.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_assets (
            item_id             BIGINT PRIMARY KEY,
            type_id             INTEGER NOT NULL,
            location_id         BIGINT NOT NULL,
            location_type       TEXT,
            location_flag       TEXT,
            quantity            INTEGER NOT NULL DEFAULT 1,
            is_singleton        BOOLEAN DEFAULT FALSE,
            is_blueprint_copy   BOOLEAN,
            name                TEXT,
            position_x          DOUBLE,
            position_y          DOUBLE,
            position_z          DOUBLE,
            fetched_at          TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_blueprints (
            item_id             BIGINT PRIMARY KEY,
            location_id         BIGINT NOT NULL,
            location_flag       TEXT,
            type_id             INTEGER NOT NULL,
            quantity            INTEGER DEFAULT 1,
            time_efficiency     INTEGER DEFAULT 0,
            material_efficiency INTEGER DEFAULT 0,
            runs                INTEGER DEFAULT -1,
            fetched_at          TIMESTAMP DEFAULT now()
        )
    """)


def _paginate(url: str, headers: dict) -> list:
    resp = esi_get(url, params={"page": 1}, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return []
        logger.warning("[corp.assets] ESI %s for %s", resp.status_code, url)
        return []
    data = resp.json()
    total = int(resp.headers.get("X-Pages", 1))
    for page in range(2, total + 1):
        r = esi_get(url, params={"page": page}, headers=headers)
        if r.ok:
            data.extend(r.json())
    return data


def fetch_corp_assets(corporation_id: int, character_id: int, access_token: str) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}
    assets = _paginate(f"{ESI_BASE}/corporations/{corporation_id}/assets/", headers)
    blueprints = _paginate(f"{ESI_BASE}/corporations/{corporation_id}/blueprints/", headers)

    con = connect_entity(corporation_id)
    try:
        _ensure_tables(con)
        if assets:
            con.execute("DELETE FROM corp_assets")
            con.executemany("""
                INSERT INTO corp_assets
                    (item_id, type_id, location_id, location_type, location_flag,
                     quantity, is_singleton, is_blueprint_copy, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, now())
            """, [(a["item_id"], a["type_id"], a["location_id"], a.get("location_type"),
                   a.get("location_flag"), a.get("quantity", 1), a.get("is_singleton", False),
                   a.get("is_blueprint_copy")) for a in assets])

        if blueprints:
            con.execute("DELETE FROM corp_blueprints")
            con.executemany("""
                INSERT INTO corp_blueprints
                    (item_id, location_id, location_flag, type_id, quantity,
                     time_efficiency, material_efficiency, runs, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, now())
            """, [(b["item_id"], b["location_id"], b.get("location_flag"), b["type_id"],
                   b.get("quantity", 1), b.get("time_efficiency", 0),
                   b.get("material_efficiency", 0), b.get("runs", -1)) for b in blueprints])
    finally:
        con.close()
    logger.info("[corp.assets] %d assets, %d blueprints for corp %s",
                len(assets), len(blueprints), corporation_id)


def run_for_all_corps() -> None:
    from collectors.corp import get_corp_token_map
    token_map = get_corp_token_map()
    for corp_id, (char_id, access_token) in token_map.items():
        try:
            fetch_corp_assets(corp_id, char_id, access_token)
        except Exception:
            logger.exception("[corp.assets] failed for corp %s", corp_id)
