"""collectors/character/industry.py — industry jobs, mining, blueprints, colonies collectors.

Writes to the owner's per-entity DuckDB (`<owner_id>.duckdb`).
"""

from __future__ import annotations

import json
import logging

from core.db.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


# ─────────────────────────────────────────────────────────────────────────────
# DDL
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_industry_jobs (
            character_id        BIGINT NOT NULL,
            job_id              INTEGER NOT NULL,
            installer_id        BIGINT,
            facility_id         BIGINT,
            station_id          BIGINT,
            activity_id         INTEGER,
            blueprint_id        BIGINT,
            blueprint_type_id   INTEGER,
            blueprint_location_id BIGINT,
            output_location_id  BIGINT,
            runs                INTEGER,
            cost                DOUBLE,
            licensed_runs       INTEGER,
            probability         REAL,
            product_type_id     INTEGER,
            status              TEXT,
            duration            INTEGER,
            start_date          TIMESTAMP,
            end_date            TIMESTAMP,
            pause_date          TIMESTAMP,
            completed_date      TIMESTAMP,
            completed_character_id BIGINT,
            fetched_at          TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, job_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_mining (
            character_id    BIGINT NOT NULL,
            date            TIMESTAMP NOT NULL,
            solar_system_id INTEGER NOT NULL,
            type_id         INTEGER NOT NULL,
            quantity        BIGINT NOT NULL,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, date, solar_system_id, type_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_blueprints (
            character_id        BIGINT NOT NULL,
            item_id             BIGINT NOT NULL,
            location_id         BIGINT,
            location_flag       TEXT,
            type_id             INTEGER NOT NULL,
            quantity            INTEGER DEFAULT 1,
            time_efficiency     INTEGER DEFAULT 0,
            material_efficiency INTEGER DEFAULT 0,
            runs                INTEGER DEFAULT -1,
            fetched_at          TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, item_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_colonies (
            character_id    BIGINT NOT NULL,
            planet_id       INTEGER NOT NULL,
            planet_type     TEXT,
            solar_system_id INTEGER,
            owner_id        BIGINT,
            upgrade_level   INTEGER,
            num_pins        INTEGER,
            last_update     TIMESTAMP,
            pins_json       TEXT,
            routes_json     TEXT,
            links_json      TEXT,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, planet_id)
        )
    """)


# ─────────────────────────────────────────────────────────────────────────────
# Industry jobs
# ─────────────────────────────────────────────────────────────────────────────

def populate_industry(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/industry/jobs/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers, params={"include_completed": True})
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[industry.jobs] ESI %s for char %s", resp.status_code, character_id)
        return
    data = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for j in data:
            con.execute("""
                INSERT INTO character_industry_jobs
                    (character_id, job_id, installer_id, facility_id, station_id,
                     activity_id, blueprint_id, blueprint_type_id, blueprint_location_id,
                     output_location_id, runs, cost, licensed_runs, probability,
                     product_type_id, status, duration, start_date, end_date,
                     pause_date, completed_date, completed_character_id, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, job_id) DO UPDATE SET
                    status = excluded.status, end_date = excluded.end_date,
                    completed_date = excluded.completed_date, fetched_at = now()
            """, [character_id, j["job_id"], j.get("installer_id"), j.get("facility_id"),
                  j.get("station_id"), j.get("activity_id"), j.get("blueprint_id"),
                  j.get("blueprint_type_id"), j.get("blueprint_location_id"),
                  j.get("output_location_id"), j.get("runs"), j.get("cost"),
                  j.get("licensed_runs"), j.get("probability"), j.get("product_type_id"),
                  j.get("status"), j.get("duration"), j.get("start_date"),
                  j.get("end_date"), j.get("pause_date"), j.get("completed_date"),
                  j.get("completed_character_id")])
    finally:
        con.close()
    logger.info("[industry.jobs] %d jobs for char %s", len(data), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Mining ledger
# ─────────────────────────────────────────────────────────────────────────────

def populate_mining(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/mining/"
    headers = {"Authorization": f"Bearer {access_token}"}

    data = []
    resp = esi_get(url, headers=headers, params={"page": 1})
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[industry.mining] ESI %s for char %s", resp.status_code, character_id)
        return
    data.extend(resp.json())
    for page in range(2, int(resp.headers.get("X-Pages", 1)) + 1):
        r = esi_get(url, headers=headers, params={"page": page})
        if r.ok:
            data.extend(r.json())

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for m in data:
            con.execute("""
                INSERT INTO character_mining
                    (character_id, date, solar_system_id, type_id, quantity, fetched_at)
                VALUES (?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, date, solar_system_id, type_id) DO UPDATE SET
                    quantity = excluded.quantity, fetched_at = now()
            """, [character_id, m.get("date"), m["solar_system_id"],
                  m["type_id"], m.get("quantity", 0)])
    finally:
        con.close()
    logger.info("[industry.mining] %d entries for char %s", len(data), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Blueprints
# ─────────────────────────────────────────────────────────────────────────────

def populate_blueprints(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/blueprints/"
    headers = {"Authorization": f"Bearer {access_token}"}

    data = []
    resp = esi_get(url, headers=headers, params={"page": 1})
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[industry.blueprints] ESI %s for char %s", resp.status_code, character_id)
        return
    data.extend(resp.json())
    for page in range(2, int(resp.headers.get("X-Pages", 1)) + 1):
        r = esi_get(url, headers=headers, params={"page": page})
        if r.ok:
            data.extend(r.json())

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for bp in data:
            con.execute("""
                INSERT INTO character_blueprints
                    (character_id, item_id, location_id, location_flag, type_id,
                     quantity, time_efficiency, material_efficiency, runs, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, item_id) DO UPDATE SET
                    material_efficiency = excluded.material_efficiency,
                    time_efficiency = excluded.time_efficiency,
                    runs = excluded.runs, fetched_at = now()
            """, [character_id, bp["item_id"], bp.get("location_id"),
                  bp.get("location_flag"), bp["type_id"], bp.get("quantity", 1),
                  bp.get("time_efficiency", 0), bp.get("material_efficiency", 0),
                  bp.get("runs", -1)])
    finally:
        con.close()
    logger.info("[industry.blueprints] %d for char %s", len(data), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Planetary colonies (with inline layout enrichment)
# ─────────────────────────────────────────────────────────────────────────────

def populate_planets(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/planets/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[industry.planets] ESI %s for char %s", resp.status_code, character_id)
        return
    planets = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for p in planets:
            pid = p["planet_id"]
            pins_json = routes_json = links_json = None
            # Inline layout enrichment (bounded by planet count)
            layout_url = f"{ESI_BASE}/characters/{character_id}/planets/{pid}/"
            lr = esi_get(layout_url, headers=headers)
            if lr.ok:
                layout = lr.json()
                pins_json = json.dumps(layout.get("pins", []))
                routes_json = json.dumps(layout.get("routes", []))
                links_json = json.dumps(layout.get("links", []))
            con.execute("""
                INSERT INTO character_colonies
                    (character_id, planet_id, planet_type, solar_system_id, owner_id,
                     upgrade_level, num_pins, last_update,
                     pins_json, routes_json, links_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, planet_id) DO UPDATE SET
                    num_pins = excluded.num_pins, last_update = excluded.last_update,
                    pins_json = excluded.pins_json, routes_json = excluded.routes_json,
                    links_json = excluded.links_json, fetched_at = now()
            """, [character_id, pid, p.get("planet_type"), p.get("solar_system_id"),
                  p.get("owner_id"), p.get("upgrade_level"), p.get("num_pins"),
                  p.get("last_update"), pins_json, routes_json, links_json])
    finally:
        con.close()
    logger.info("[industry.planets] %d colonies for char %s", len(planets), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Scope → Collector registry
# ─────────────────────────────────────────────────────────────────────────────

SCOPE_COLLECTORS: list[tuple[str, str, object]] = [
    ("esi-industry.read_character_jobs.v1",   "industry",    populate_industry),
    ("esi-industry.read_character_mining.v1", "mining",      populate_mining),
    ("esi-characters.read_blueprints.v1",     "blueprints",  populate_blueprints),
    ("esi-planets.manage_planets.v1",         "colonies",    populate_planets),
]
NO_SCOPE_COLLECTORS: list[tuple[str, object]] = []
