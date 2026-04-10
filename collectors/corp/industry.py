"""collectors/corp/industry.py — corp_industry_jobs, corp_moon_extractions, corp_mining_observers, corp_mining_ledger."""

from __future__ import annotations

import logging

from core.io.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_industry_jobs (
            job_id                  INTEGER PRIMARY KEY,
            installer_id            BIGINT,
            facility_id             BIGINT,
            station_id              BIGINT,
            blueprint_id            BIGINT,
            blueprint_type_id       INTEGER,
            blueprint_location_id   BIGINT,
            output_location_id      BIGINT,
            runs                    INTEGER,
            activity_id             INTEGER,
            status                  TEXT,
            start_date              TIMESTAMP,
            end_date                TIMESTAMP,
            pause_date              TIMESTAMP,
            completed_date          TIMESTAMP,
            completed_character_id  BIGINT,
            cost                    DOUBLE,
            licensed_runs           INTEGER,
            probability             REAL,
            product_type_id         INTEGER,
            duration                INTEGER,
            fetched_at              TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_moon_extractions (
            moon_id                 INTEGER NOT NULL,
            structure_id            BIGINT NOT NULL,
            extraction_start_time   TIMESTAMP,
            chunk_arrival_time      TIMESTAMP,
            natural_decay_time      TIMESTAMP,
            fetched_at              TIMESTAMP DEFAULT now(),
            PRIMARY KEY (moon_id, structure_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_mining_observers (
            observer_id     BIGINT PRIMARY KEY,
            observer_type   TEXT,
            last_updated    TIMESTAMP,
            fetched_at      TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_mining_ledger (
            observer_id             BIGINT NOT NULL,
            character_id            BIGINT NOT NULL,
            recorded_corporation_id BIGINT,
            type_id                 INTEGER NOT NULL,
            quantity                BIGINT NOT NULL,
            last_updated            TIMESTAMP,
            fetched_at              TIMESTAMP DEFAULT now(),
            PRIMARY KEY (observer_id, character_id, type_id)
        )
    """)


def fetch_corp_industry(corporation_id: int, character_id: int, access_token: str) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}
    con = connect_entity(corporation_id)
    try:
        _ensure_tables(con)

        # Industry jobs (paginated)
        resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/industry/jobs/",
                       params={"page": 1, "include_completed": True}, headers=headers)
        if resp.ok:
            jobs = resp.json()
            total = int(resp.headers.get("X-Pages", 1))
            for page in range(2, total + 1):
                r = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/industry/jobs/",
                            params={"page": page, "include_completed": True}, headers=headers)
                if r.ok:
                    jobs.extend(r.json())
            for j in jobs:
                con.execute("""
                    INSERT INTO corp_industry_jobs
                        (job_id, installer_id, facility_id, station_id, blueprint_id,
                         blueprint_type_id, blueprint_location_id, output_location_id, runs,
                         activity_id, status, start_date, end_date, pause_date, completed_date,
                         completed_character_id, cost, licensed_runs, probability,
                         product_type_id, duration, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                    ON CONFLICT (job_id) DO UPDATE SET status = excluded.status, fetched_at = now()
                """, [j["job_id"], j.get("installer_id"), j.get("facility_id"),
                      j.get("station_id"), j.get("blueprint_id"), j.get("blueprint_type_id"),
                      j.get("blueprint_location_id"), j.get("output_location_id"), j.get("runs"),
                      j.get("activity_id"), j.get("status"), j.get("start_date"),
                      j.get("end_date"), j.get("pause_date"), j.get("completed_date"),
                      j.get("completed_character_id"), j.get("cost"), j.get("licensed_runs"),
                      j.get("probability"), j.get("product_type_id"), j.get("duration")])

        # Moon extractions
        me_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/mining/extractions/",
                          headers=headers)
        if me_resp.ok:
            for m in me_resp.json():
                con.execute("""
                    INSERT INTO corp_moon_extractions
                        (moon_id, structure_id, extraction_start_time, chunk_arrival_time,
                         natural_decay_time, fetched_at)
                    VALUES (?, ?, ?, ?, ?, now())
                    ON CONFLICT (moon_id, structure_id) DO UPDATE SET
                        chunk_arrival_time = excluded.chunk_arrival_time, fetched_at = now()
                """, [m["moon_id"], m["structure_id"], m.get("extraction_start_time"),
                      m.get("chunk_arrival_time"), m.get("natural_decay_time")])

        # Mining observers + inline ledger
        obs_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/mining/observers/",
                           headers=headers)
        if obs_resp.ok:
            for obs in obs_resp.json():
                obs_id = obs["observer_id"]
                con.execute("""
                    INSERT INTO corp_mining_observers (observer_id, observer_type, last_updated, fetched_at)
                    VALUES (?, ?, ?, now())
                    ON CONFLICT (observer_id) DO UPDATE SET last_updated = excluded.last_updated, fetched_at = now()
                """, [obs_id, obs.get("observer_type"), obs.get("last_updated")])

                # Inline ledger (paginated)
                led_resp = esi_get(
                    f"{ESI_BASE}/corporations/{corporation_id}/mining/observers/{obs_id}/",
                    params={"page": 1}, headers=headers)
                if led_resp.ok:
                    ledger = led_resp.json()
                    total = int(led_resp.headers.get("X-Pages", 1))
                    for page in range(2, total + 1):
                        r = esi_get(
                            f"{ESI_BASE}/corporations/{corporation_id}/mining/observers/{obs_id}/",
                            params={"page": page}, headers=headers)
                        if r.ok:
                            ledger.extend(r.json())
                    con.executemany("""
                        INSERT INTO corp_mining_ledger
                            (observer_id, character_id, recorded_corporation_id, type_id, quantity, last_updated, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?, now())
                        ON CONFLICT (observer_id, character_id, type_id) DO UPDATE SET
                            quantity = excluded.quantity, last_updated = excluded.last_updated, fetched_at = now()
                    """, [(obs_id, lrow["character_id"], lrow.get("recorded_corporation_id"),
                           lrow["type_id"], lrow["quantity"], lrow.get("last_updated"))
                          for lrow in ledger])
    finally:
        con.close()
    logger.info("[corp.industry] updated for corp %s", corporation_id)


def run_for_all_corps() -> None:
    from collectors.corp import get_corp_token_map
    token_map = get_corp_token_map()
    for corp_id, (char_id, access_token) in token_map.items():
        try:
            fetch_corp_industry(corp_id, char_id, access_token)
        except Exception:
            logger.exception("[corp.industry] failed for corp %s", corp_id)
