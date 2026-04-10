"""collectors/public_data/universe_extras.py — Incursions, wars, server status,
freelance jobs, and insurance prices.

**Table ownership:** ``incursions``, ``wars``, ``server_status``,
                     ``freelance_jobs``, ``insurance_prices``
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
        CREATE TABLE IF NOT EXISTS incursions (
            constellation_id            INTEGER PRIMARY KEY,
            faction_id                  INTEGER NOT NULL,
            has_boss                    BOOLEAN DEFAULT FALSE,
            infested_solar_systems      INTEGER[],
            influence                   REAL DEFAULT 0,
            staging_solar_system_id     INTEGER,
            state                       TEXT,
            type                        TEXT,
            fetched_at                  TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS wars (
            war_id          INTEGER PRIMARY KEY,
            aggressor_id    BIGINT,
            aggressor_type  TEXT,
            defender_id     BIGINT,
            defender_type   TEXT,
            declared        TIMESTAMP,
            started         TIMESTAMP,
            finished        TIMESTAMP,
            retracted       TIMESTAMP,
            mutual          BOOLEAN DEFAULT FALSE,
            open_for_allies BOOLEAN DEFAULT FALSE,
            allies_json     TEXT,
            killmails_json  TEXT,
            fetched_at      TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS server_status (
            id              INTEGER DEFAULT 1 PRIMARY KEY,
            checked_at      TIMESTAMP,
            start_time      TIMESTAMP,
            players         INTEGER DEFAULT 0,
            server_version  TEXT,
            vip             BOOLEAN DEFAULT FALSE
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS freelance_jobs (
            job_id          TEXT PRIMARY KEY,
            status          TEXT,
            details_json    TEXT,
            fetched_at      TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS insurance_prices (
            type_id     INTEGER NOT NULL,
            level       TEXT NOT NULL,
            cost        DOUBLE NOT NULL,
            payout      DOUBLE NOT NULL,
            fetched_at  TIMESTAMP DEFAULT now(),
            PRIMARY KEY (type_id, level)
        )
    """)


def fetch_universe_extras() -> None:
    """Fetch incursions, wars (ID list), server status, freelance jobs, and insurance prices."""
    con = public_connect(read_only=False)
    try:
        ensure_tables(con)
    finally:
        con.close()

    # Incursions
    resp = esi_get(f"{ESI_BASE}/incursions/")
    if resp.ok:
        rows = [(i["constellation_id"], i["faction_id"], i.get("has_boss", False),
                 i.get("infested_solar_systems", []), i.get("influence", 0),
                 i.get("staging_solar_system_id"), i.get("state"), i.get("type"))
                for i in resp.json()]
        db_executemany("""
            INSERT INTO incursions
                (constellation_id, faction_id, has_boss, infested_solar_systems,
                 influence, staging_solar_system_id, state, type, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, now())
            ON CONFLICT (constellation_id) DO UPDATE SET
                influence = excluded.influence, state = excluded.state, fetched_at = now()
        """, rows)
        logger.info("[universe_extras] %s incursions updated", len(rows))

    # Wars — seed IDs only; details filled by analysis/war_enrichment.py
    resp = esi_get(f"{ESI_BASE}/wars/")
    if resp.ok:
        war_ids: list[int] = resp.json()
        db_executemany("""
            INSERT INTO wars (war_id, fetched_at)
            VALUES (?, now())
            ON CONFLICT (war_id) DO UPDATE SET fetched_at = now()
        """, [(wid,) for wid in war_ids])
        logger.info("[universe_extras] Seeded %s war IDs", len(war_ids))

    # Server status
    resp = esi_get(f"{ESI_BASE}/status/")
    if resp.ok:
        d = resp.json()
        import datetime
        con = public_connect(read_only=False)
        try:
            con.execute("""
                INSERT INTO server_status
                    (id, checked_at, start_time, players, server_version, vip)
                VALUES (1, ?, ?, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    checked_at = excluded.checked_at,
                    players = excluded.players, fetched_at = now()
            """, [datetime.datetime.utcnow(), d.get("start_time"), d.get("players", 0),
                  d.get("server_version"), d.get("vip", False)])
        finally:
            con.close()

    # Freelance jobs — seed IDs; details filled by analysis/freelance_enrichment.py
    resp = esi_get(f"{ESI_BASE}/freelance-jobs/")
    if resp.ok:
        rows = [(str(j.get("freelance_job_id") or j.get("job_id", "")), j.get("status"))
                for j in resp.json() if j.get("freelance_job_id") or j.get("job_id")]
        if rows:
            db_executemany("""
                INSERT INTO freelance_jobs (job_id, status, fetched_at)
                VALUES (?, ?, now())
                ON CONFLICT (job_id) DO UPDATE SET status = excluded.status, fetched_at = now()
            """, rows)
            logger.info("[universe_extras] %s freelance jobs updated", len(rows))

    # Insurance prices
    resp = esi_get(f"{ESI_BASE}/insurance/prices/")
    if resp.ok:
        rows = []
        for item in resp.json():
            type_id = item["type_id"]
            for level in item.get("levels", []):
                rows.append((type_id, level["name"], level.get("cost", 0), level.get("payout", 0)))
        if rows:
            db_executemany("""
                INSERT INTO insurance_prices (type_id, level, cost, payout, fetched_at)
                VALUES (?, ?, ?, ?, now())
                ON CONFLICT (type_id, level) DO UPDATE SET
                    cost = excluded.cost, payout = excluded.payout, fetched_at = now()
            """, rows)
            logger.info("[universe_extras] %s insurance price rows updated", len(rows))
