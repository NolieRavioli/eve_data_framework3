"""collectors/public_data/fw.py — Factional Warfare public data.

**Table ownership:** ``fw_stats``, ``fw_systems``, ``fw_wars``, ``fw_leaderboards``
"""

from __future__ import annotations

import logging

from core.db.public import connect as public_connect
from core.db.writer import db_executemany
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS fw_stats (
            faction_id                  INTEGER PRIMARY KEY,
            kills_last_week             INTEGER DEFAULT 0,
            kills_total                 INTEGER DEFAULT 0,
            kills_yesterday             INTEGER DEFAULT 0,
            pilots                      INTEGER DEFAULT 0,
            systems_controlled          INTEGER DEFAULT 0,
            victory_points_last_week    INTEGER DEFAULT 0,
            victory_points_total        INTEGER DEFAULT 0,
            victory_points_yesterday    INTEGER DEFAULT 0,
            fetched_at                  TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS fw_systems (
            solar_system_id             INTEGER PRIMARY KEY,
            contested                   TEXT,
            occupier_faction_id         INTEGER,
            owner_faction_id            INTEGER,
            victory_points              INTEGER DEFAULT 0,
            victory_points_threshold    INTEGER DEFAULT 0,
            fetched_at                  TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS fw_wars (
            against_id  INTEGER NOT NULL,
            faction_id  INTEGER NOT NULL,
            PRIMARY KEY (against_id, faction_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS fw_leaderboards (
            category    TEXT NOT NULL,
            timeframe   TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id   BIGINT NOT NULL,
            amount      INTEGER NOT NULL,
            fetched_at  TIMESTAMP DEFAULT now(),
            PRIMARY KEY (category, timeframe, entity_type, entity_id)
        )
    """)


def fetch_fw_data() -> None:
    """Fetch all factional warfare public data from ESI."""
    con = public_connect(read_only=False)
    try:
        ensure_tables(con)
    finally:
        con.close()

    # FW faction stats
    resp = esi_get(f"{ESI_BASE}/fw/stats/")
    if resp.ok:
        rows = []
        for s in resp.json():
            k = s.get("kills", {})
            vp = s.get("victory_points", {})
            rows.append((s["faction_id"], k.get("last_week", 0), k.get("total", 0),
                         k.get("yesterday", 0), s.get("pilots", 0),
                         s.get("systems_controlled", 0), vp.get("last_week", 0),
                         vp.get("total", 0), vp.get("yesterday", 0)))
        db_executemany("""
            INSERT INTO fw_stats
                (faction_id, kills_last_week, kills_total, kills_yesterday, pilots,
                 systems_controlled, victory_points_last_week, victory_points_total,
                 victory_points_yesterday, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, now())
            ON CONFLICT (faction_id) DO UPDATE SET
                kills_total = excluded.kills_total,
                victory_points_total = excluded.victory_points_total, fetched_at = now()
        """, rows)
        logger.info("[fw] %s faction stats updated", len(rows))

    # FW systems
    resp = esi_get(f"{ESI_BASE}/fw/systems/")
    if resp.ok:
        rows = [(s["solar_system_id"], s.get("contested"), s.get("occupier_faction_id"),
                 s.get("owner_faction_id"), s.get("victory_points", 0),
                 s.get("victory_points_threshold", 0))
                for s in resp.json()]
        db_executemany("""
            INSERT INTO fw_systems
                (solar_system_id, contested, occupier_faction_id, owner_faction_id,
                 victory_points, victory_points_threshold, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, now())
            ON CONFLICT (solar_system_id) DO UPDATE SET
                contested = excluded.contested,
                victory_points = excluded.victory_points, fetched_at = now()
        """, rows)
        logger.info("[fw] %s FW systems updated", len(rows))

    # FW wars
    resp = esi_get(f"{ESI_BASE}/fw/wars/")
    if resp.ok:
        rows = [(w["against_id"], w["faction_id"]) for w in resp.json()]
        con = public_connect(read_only=False)
        try:
            con.execute("DELETE FROM fw_wars")
            con.executemany("INSERT INTO fw_wars (against_id, faction_id) VALUES (?, ?)", rows)
        finally:
            con.close()
        logger.info("[fw] %s FW wars updated", len(rows))

    # FW leaderboards
    resp = esi_get(f"{ESI_BASE}/fw/leaderboards/")
    resp_corp = esi_get(f"{ESI_BASE}/fw/leaderboards/corporations/")
    resp_char = esi_get(f"{ESI_BASE}/fw/leaderboards/characters/")

    import json as _json
    leaderboard_rows = []
    for resp_obj, etype in [(resp, "faction"), (resp_corp, "corporation"), (resp_char, "character")]:
        if not resp_obj.ok:
            continue
        data = resp_obj.json()
        for category in ("kills", "victory_points"):
            cat_data = data.get(category, {})
            for timeframe in ("yesterday", "last_week", "total"):
                for entry in cat_data.get(timeframe, []):
                    eid = entry.get("alliance_id") or entry.get("corporation_id") or entry.get("character_id")
                    if eid:
                        leaderboard_rows.append((category, timeframe, etype, eid, entry.get("amount", 0)))

    if leaderboard_rows:
        db_executemany("""
            INSERT INTO fw_leaderboards
                (category, timeframe, entity_type, entity_id, amount, fetched_at)
            VALUES (?, ?, ?, ?, ?, now())
            ON CONFLICT (category, timeframe, entity_type, entity_id) DO UPDATE SET
                amount = excluded.amount, fetched_at = now()
        """, leaderboard_rows)
        logger.info("[fw] %s leaderboard entries updated", len(leaderboard_rows))
