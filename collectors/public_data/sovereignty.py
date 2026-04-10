"""collectors/public_data/sovereignty.py — Sovereignty campaigns, map, and structures.

**Table ownership:** ``sovereignty_campaigns``, ``sovereignty_map``, ``sovereignty_structures``
"""

from __future__ import annotations

import json
import logging

from core.io.public import connect as public_connect
from core.io.writer import db_executemany
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS sovereignty_campaigns (
            campaign_id         INTEGER PRIMARY KEY,
            solar_system_id     INTEGER NOT NULL,
            constellation_id    INTEGER,
            structure_id        BIGINT NOT NULL,
            event_type          TEXT,
            start_time          TIMESTAMP,
            defender_id         BIGINT,
            defender_score      REAL,
            attackers_score     REAL,
            participants_json   TEXT,
            fetched_at          TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS sovereignty_map (
            system_id       INTEGER PRIMARY KEY,
            alliance_id     BIGINT,
            corporation_id  BIGINT,
            faction_id      INTEGER,
            fetched_at      TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS sovereignty_structures (
            structure_id                    BIGINT PRIMARY KEY,
            alliance_id                     BIGINT,
            solar_system_id                 INTEGER NOT NULL,
            type_id                         INTEGER NOT NULL,
            vulnerability_occupancy_level   REAL,
            vulnerable_start_time           TIMESTAMP,
            vulnerable_end_time             TIMESTAMP,
            fetched_at                      TIMESTAMP DEFAULT now()
        )
    """)


def fetch_sovereignty() -> None:
    """Fetch sovereignty campaigns, map, and structures from ESI."""
    con = public_connect(read_only=False)
    try:
        ensure_tables(con)
    finally:
        con.close()

    # Campaigns
    resp = esi_get(f"{ESI_BASE}/sovereignty/campaigns/")
    if resp.ok:
        rows = [(c["campaign_id"], c["solar_system_id"], c.get("constellation_id"),
                 c["structure_id"], c.get("event_type"), c.get("start_time"),
                 c.get("defender_id"), c.get("defender_score"), c.get("attackers_score"),
                 json.dumps(c.get("participants")) if c.get("participants") else None)
                for c in resp.json()]
        db_executemany("""
            INSERT INTO sovereignty_campaigns
                (campaign_id, solar_system_id, constellation_id, structure_id, event_type,
                 start_time, defender_id, defender_score, attackers_score,
                 participants_json, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
            ON CONFLICT (campaign_id) DO UPDATE SET
                defender_score = excluded.defender_score,
                attackers_score = excluded.attackers_score, fetched_at = now()
        """, rows)
        logger.info("[sovereignty] %s campaigns updated", len(rows))

    # Map
    resp = esi_get(f"{ESI_BASE}/sovereignty/map/")
    if resp.ok:
        rows = [(s["system_id"], s.get("alliance_id"), s.get("corporation_id"), s.get("faction_id"))
                for s in resp.json()]
        db_executemany("""
            INSERT INTO sovereignty_map
                (system_id, alliance_id, corporation_id, faction_id, fetched_at)
            VALUES (?, ?, ?, ?, now())
            ON CONFLICT (system_id) DO UPDATE SET
                alliance_id = excluded.alliance_id,
                corporation_id = excluded.corporation_id,
                faction_id = excluded.faction_id, fetched_at = now()
        """, rows)
        logger.info("[sovereignty] %s map systems updated", len(rows))

    # Structures
    resp = esi_get(f"{ESI_BASE}/sovereignty/structures/")
    if resp.ok:
        rows = [(s["structure_id"], s.get("alliance_id"), s["solar_system_id"], s["type_id"],
                 s.get("vulnerability_occupancy_level"), s.get("vulnerable_start_time"),
                 s.get("vulnerable_end_time"))
                for s in resp.json()]
        db_executemany("""
            INSERT INTO sovereignty_structures
                (structure_id, alliance_id, solar_system_id, type_id,
                 vulnerability_occupancy_level, vulnerable_start_time,
                 vulnerable_end_time, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, now())
            ON CONFLICT (structure_id) DO UPDATE SET
                alliance_id = excluded.alliance_id,
                vulnerability_occupancy_level = excluded.vulnerability_occupancy_level,
                fetched_at = now()
        """, rows)
        logger.info("[sovereignty] %s structures updated", len(rows))
