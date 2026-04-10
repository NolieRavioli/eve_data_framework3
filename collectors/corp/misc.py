"""collectors/corp/misc.py — corp_fw_stats, corp_freelance_jobs, corp_container_logs."""

from __future__ import annotations

import logging

from core.io.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_fw_stats (
            id                          INTEGER DEFAULT 1 PRIMARY KEY,
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
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_freelance_jobs (
            job_id          TEXT PRIMARY KEY,
            status          TEXT,
            details_json    TEXT,
            fetched_at      TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_container_logs (
            log_time            TIMESTAMP NOT NULL,
            container_id        BIGINT NOT NULL,
            character_id        BIGINT NOT NULL,
            action              TEXT NOT NULL,
            container_type_id   INTEGER,
            location_flag       TEXT,
            location_id         BIGINT,
            new_config_bitmask  INTEGER,
            old_config_bitmask  INTEGER,
            password_type       TEXT,
            quantity            INTEGER,
            type_id             INTEGER,
            fetched_at          TIMESTAMP DEFAULT now(),
            PRIMARY KEY (log_time, container_id, character_id)
        )
    """)


def fetch_corp_misc(corporation_id: int, character_id: int, access_token: str) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}
    con = connect_entity(corporation_id)
    try:
        _ensure_tables(con)

        # FW stats
        fw_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/fw/stats/", headers=headers)
        if fw_resp.ok:
            d = fw_resp.json()
            kills = d.get("kills", {})
            vp = d.get("victory_points", {})
            con.execute("""
                INSERT INTO corp_fw_stats
                    (id, current_rank, highest_rank, enlisted_on, faction_id,
                     kills_last_week, kills_total, kills_yesterday,
                     victory_points_last_week, victory_points_total, victory_points_yesterday, fetched_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (id) DO UPDATE SET
                    kills_total = excluded.kills_total,
                    victory_points_total = excluded.victory_points_total, fetched_at = now()
            """, [d.get("current_rank"), d.get("highest_rank"), d.get("enlisted_on"),
                  d.get("faction_id"), kills.get("last_week", 0), kills.get("total", 0),
                  kills.get("yesterday", 0), vp.get("last_week", 0), vp.get("total", 0),
                  vp.get("yesterday", 0)])

        # Freelance jobs
        fj_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/freelance-jobs/",
                          headers=headers)
        if fj_resp.ok:
            for job in fj_resp.json():
                job_id = job.get("freelance_job_id") or job.get("job_id")
                if job_id:
                    con.execute("""
                        INSERT INTO corp_freelance_jobs (job_id, status, fetched_at)
                        VALUES (?, ?, now())
                        ON CONFLICT (job_id) DO UPDATE SET status = excluded.status, fetched_at = now()
                    """, [str(job_id), job.get("status")])

        # Container logs (paginated)
        cl_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/containers/logs/",
                          params={"page": 1}, headers=headers)
        if cl_resp.ok:
            logs = cl_resp.json()
            total = int(cl_resp.headers.get("X-Pages", 1))
            for page in range(2, total + 1):
                r = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/containers/logs/",
                            params={"page": page}, headers=headers)
                if r.ok:
                    logs.extend(r.json())
            con.executemany("""
                INSERT INTO corp_container_logs
                    (log_time, container_id, character_id, action, container_type_id,
                     location_flag, location_id, new_config_bitmask, old_config_bitmask,
                     password_type, quantity, type_id, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (log_time, container_id, character_id) DO NOTHING
            """, [(log["logged_at"], log["container_id"], log["character_id"], log["action"],
                   log.get("container_type_id"), log.get("location_flag"), log.get("location_id"),
                   log.get("new_config_bitmask"), log.get("old_config_bitmask"),
                   log.get("password_type"), log.get("quantity"), log.get("type_id"))
                  for log in logs])
    finally:
        con.close()
    logger.info("[corp.misc] updated for corp %s", corporation_id)


def run_for_all_corps() -> None:
    from collectors.corp import get_corp_token_map
    token_map = get_corp_token_map()
    for corp_id, (char_id, access_token) in token_map.items():
        try:
            fetch_corp_misc(corp_id, char_id, access_token)
        except Exception:
            logger.exception("[corp.misc] failed for corp %s", corp_id)
