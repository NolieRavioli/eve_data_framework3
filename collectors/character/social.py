"""collectors/character/social.py — standings, fittings, medals, titles, corp history, FW stats.

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
        CREATE TABLE IF NOT EXISTS character_standings (
            character_id    BIGINT NOT NULL,
            from_id         BIGINT NOT NULL,
            from_type       TEXT NOT NULL,
            standing        REAL NOT NULL,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, from_id, from_type)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_fittings (
            character_id    BIGINT NOT NULL,
            fitting_id      BIGINT NOT NULL,
            name            TEXT,
            description     TEXT,
            ship_type_id    INTEGER,
            items_json      TEXT,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, fitting_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_medals (
            character_id    BIGINT NOT NULL,
            medal_id        INTEGER NOT NULL,
            corporation_id  BIGINT NOT NULL,
            title           TEXT,
            description     TEXT,
            date            TIMESTAMP,
            issuer_id       BIGINT,
            reason          TEXT,
            status          TEXT,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, medal_id, corporation_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_titles (
            character_id    BIGINT NOT NULL,
            title_id        INTEGER NOT NULL,
            name            TEXT,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, title_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_corporation_history (
            character_id    BIGINT NOT NULL,
            record_id       INTEGER NOT NULL,
            corporation_id  BIGINT NOT NULL,
            start_date      TIMESTAMP NOT NULL,
            is_deleted      BOOLEAN DEFAULT FALSE,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, record_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_fw_stats (
            character_id                BIGINT PRIMARY KEY,
            current_rank                INTEGER,
            highest_rank                INTEGER,
            enlisted_on                 TIMESTAMP,
            faction_id                  INTEGER,
            kills_last_week             INTEGER DEFAULT 0,
            kills_total                 INTEGER DEFAULT 0,
            kills_yesterday             INTEGER DEFAULT 0,
            victory_points_last_week    INTEGER DEFAULT 0,
            victory_points_total        INTEGER DEFAULT 0,
            victory_points_yesterday    INTEGER DEFAULT 0,
            fetched_at                  TIMESTAMP DEFAULT now()
        )
    """)


# ─────────────────────────────────────────────────────────────────────────────
# Standings
# ─────────────────────────────────────────────────────────────────────────────

def populate_standings(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/standings/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[social.standings] ESI %s for char %s", resp.status_code, character_id)
        return
    data = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for s in data:
            con.execute("""
                INSERT INTO character_standings
                    (character_id, from_id, from_type, standing, fetched_at)
                VALUES (?, ?, ?, ?, now())
                ON CONFLICT (character_id, from_id, from_type) DO UPDATE SET
                    standing = excluded.standing, fetched_at = now()
            """, [character_id, s["from_id"], s.get("from_type", ""), s.get("standing", 0)])
    finally:
        con.close()
    logger.info("[social.standings] %d for char %s", len(data), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Fittings
# ─────────────────────────────────────────────────────────────────────────────

def populate_fittings(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/fittings/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[social.fittings] ESI %s for char %s", resp.status_code, character_id)
        return
    data = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for f in data:
            con.execute("""
                INSERT INTO character_fittings
                    (character_id, fitting_id, name, description, ship_type_id, items_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, fitting_id) DO UPDATE SET
                    name = excluded.name, description = excluded.description,
                    items_json = excluded.items_json, fetched_at = now()
            """, [character_id, f["fitting_id"], f.get("name"), f.get("description"),
                  f.get("ship_type_id"), json.dumps(f.get("items", []))])
    finally:
        con.close()
    logger.info("[social.fittings] %d for char %s", len(data), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Medals
# ─────────────────────────────────────────────────────────────────────────────

def populate_medals(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/medals/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[social.medals] ESI %s for char %s", resp.status_code, character_id)
        return
    data = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for m in data:
            con.execute("""
                INSERT INTO character_medals
                    (character_id, medal_id, corporation_id, title, description,
                     date, issuer_id, reason, status, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, medal_id, corporation_id) DO UPDATE SET
                    status = excluded.status, fetched_at = now()
            """, [character_id, m["medal_id"], m.get("corporation_id"), m.get("title"),
                  m.get("description"), m.get("date"), m.get("issuer_id"),
                  m.get("reason"), m.get("status")])
    finally:
        con.close()
    logger.info("[social.medals] %d for char %s", len(data), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Titles
# ─────────────────────────────────────────────────────────────────────────────

def populate_titles(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/titles/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[social.titles] ESI %s for char %s", resp.status_code, character_id)
        return
    data = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for t in data:
            con.execute("""
                INSERT INTO character_titles (character_id, title_id, name, fetched_at)
                VALUES (?, ?, ?, now())
                ON CONFLICT (character_id, title_id) DO UPDATE SET
                    name = excluded.name, fetched_at = now()
            """, [character_id, t["title_id"], t.get("name")])
    finally:
        con.close()
    logger.info("[social.titles] %d for char %s", len(data), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Corporation history (public endpoint, no scope)
# ─────────────────────────────────────────────────────────────────────────────

def populate_corporation_history(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/corporationhistory/"
    resp = esi_get(url)  # Public endpoint — no auth header needed
    if not resp.ok:
        logger.warning("[social.corp_history] ESI %s for char %s", resp.status_code, character_id)
        return
    data = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for h in data:
            con.execute("""
                INSERT INTO character_corporation_history
                    (character_id, record_id, corporation_id, start_date, is_deleted, fetched_at)
                VALUES (?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, record_id) DO UPDATE SET
                    is_deleted = excluded.is_deleted, fetched_at = now()
            """, [character_id, h["record_id"], h["corporation_id"],
                  h.get("start_date"), h.get("is_deleted", False)])
    finally:
        con.close()
    logger.info("[social.corp_history] %d records for char %s", len(data), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Faction Warfare stats
# ─────────────────────────────────────────────────────────────────────────────

def populate_fw_stats(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/fw/stats/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code in (403, 404):
            return  # character not in FW
        logger.warning("[social.fw_stats] ESI %s for char %s", resp.status_code, character_id)
        return
    d = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        kills = d.get("kills", {})
        vp = d.get("victory_points", {})
        con.execute("""
            INSERT INTO character_fw_stats
                (character_id, current_rank, highest_rank, enlisted_on, faction_id,
                 kills_last_week, kills_total, kills_yesterday,
                 victory_points_last_week, victory_points_total, victory_points_yesterday, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
            ON CONFLICT (character_id) DO UPDATE SET
                current_rank = excluded.current_rank, kills_total = excluded.kills_total,
                victory_points_total = excluded.victory_points_total, fetched_at = now()
        """, [character_id, d.get("current_rank"), d.get("highest_rank"),
              d.get("enlisted_on"), d.get("faction_id"),
              kills.get("last_week", 0), kills.get("total", 0), kills.get("yesterday", 0),
              vp.get("last_week", 0), vp.get("total", 0), vp.get("yesterday", 0)])
    finally:
        con.close()
    logger.info("[social.fw_stats] updated for char %s", character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Scope → Collector registry
# ─────────────────────────────────────────────────────────────────────────────

# corp history is public (no scope) — called unconditionally
populate_corporation_history._no_scope = True  # marker used by extended.py

SCOPE_COLLECTORS: list[tuple[str, str, object]] = [
    ("esi-characters.read_standings.v1",   "standings",        populate_standings),
    ("esi-fittings.read_fittings.v1",      "fittings",         populate_fittings),
    ("esi-characters.read_medals.v1",      "medals",           populate_medals),
    ("esi-characters.read_titles.v1",      "titles",           populate_titles),
    ("esi-corporations.read_fw_stats.v1",  "fw_stats",         populate_fw_stats),
]

# Always-run (no scope required):
NO_SCOPE_COLLECTORS: list[tuple[str, object]] = [
    ("corporation_history", populate_corporation_history),
]
