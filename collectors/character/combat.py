"""collectors/character/combat.py — killmails, jump fatigue, freelance jobs.

Writes to the owner's per-entity DuckDB (`<owner_id>.duckdb`).
"""

from __future__ import annotations

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
        CREATE TABLE IF NOT EXISTS character_killmails (
            character_id    BIGINT NOT NULL,
            killmail_id     BIGINT NOT NULL,
            killmail_hash   TEXT NOT NULL,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, killmail_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_jump_fatigue (
            character_id        BIGINT PRIMARY KEY,
            jump_fatigue_expire_date    TIMESTAMP,
            last_jump_date              TIMESTAMP,
            last_update_date            TIMESTAMP,
            fetched_at          TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_freelance_jobs (
            character_id        BIGINT NOT NULL,
            freelance_job_id    BIGINT NOT NULL,
            status              TEXT,
            title               TEXT,
            issuer_id           BIGINT,
            corporation_id      BIGINT,
            reward              BIGINT,
            expiry_date         TIMESTAMP,
            is_participant      BOOLEAN DEFAULT FALSE,
            role                TEXT,
            fetched_at          TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, freelance_job_id)
        )
    """)


# ─────────────────────────────────────────────────────────────────────────────
# Killmails
# ─────────────────────────────────────────────────────────────────────────────

def populate_killmails(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/killmails/recent/"
    headers = {"Authorization": f"Bearer {access_token}"}
    # Paginate (X-Pages)
    resp = esi_get(url, params={"page": 1}, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[combat.killmails] ESI %s for char %s", resp.status_code, character_id)
        return
    data = resp.json()
    total_pages = int(resp.headers.get("X-Pages", 1))
    for page in range(2, total_pages + 1):
        r = esi_get(url, params={"page": page}, headers=headers)
        if r.ok:
            data.extend(r.json())

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for km in data:
            con.execute("""
                INSERT INTO character_killmails (character_id, killmail_id, killmail_hash, fetched_at)
                VALUES (?, ?, ?, now())
                ON CONFLICT (character_id, killmail_id) DO NOTHING
            """, [character_id, km["killmail_id"], km.get("killmail_hash", "")])
    finally:
        con.close()
    logger.info("[combat.killmails] %d for char %s", len(data), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Jump fatigue
# ─────────────────────────────────────────────────────────────────────────────

def populate_fatigue(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/fatigue/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code in (403, 404):
            return
        logger.warning("[combat.fatigue] ESI %s for char %s", resp.status_code, character_id)
        return
    d = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        con.execute("""
            INSERT INTO character_jump_fatigue
                (character_id, jump_fatigue_expire_date, last_jump_date, last_update_date, fetched_at)
            VALUES (?, ?, ?, ?, now())
            ON CONFLICT (character_id) DO UPDATE SET
                jump_fatigue_expire_date = excluded.jump_fatigue_expire_date,
                last_jump_date = excluded.last_jump_date,
                last_update_date = excluded.last_update_date,
                fetched_at = now()
        """, [character_id, d.get("jump_fatigue_expire_date"),
              d.get("last_jump_date"), d.get("last_update_date")])
    finally:
        con.close()
    logger.info("[combat.fatigue] updated for char %s", character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Freelance jobs
# ─────────────────────────────────────────────────────────────────────────────

def populate_freelance_jobs(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/freelance-jobs/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code in (403, 404):
            return
        logger.warning("[combat.freelance_jobs] ESI %s for char %s", resp.status_code, character_id)
        return
    data = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for job in data:
            job_id = job.get("freelance_job_id") or job.get("job_id")
            if not job_id:
                continue

            # Inline enrichment: participation
            is_participant = False
            role = None
            part_url = f"{ESI_BASE}/freelance-jobs/{job_id}/participation/"
            part_resp = esi_get(part_url, headers=headers)
            if part_resp.ok:
                part_data = part_resp.json()
                # part_data is a list; check if character_id is present
                for p in part_data:
                    if p.get("character_id") == character_id:
                        is_participant = True
                        role = p.get("role")
                        break

            con.execute("""
                INSERT INTO character_freelance_jobs
                    (character_id, freelance_job_id, status, title, issuer_id,
                     corporation_id, reward, expiry_date, is_participant, role, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, freelance_job_id) DO UPDATE SET
                    status = excluded.status, is_participant = excluded.is_participant,
                    role = excluded.role, fetched_at = now()
            """, [character_id, job_id, job.get("status"), job.get("title"),
                  job.get("issuer_id"), job.get("corporation_id"), job.get("reward"),
                  job.get("expiry_date"), is_participant, role])
    finally:
        con.close()
    logger.info("[combat.freelance_jobs] %d for char %s", len(data), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Scope → Collector registry
# ─────────────────────────────────────────────────────────────────────────────

SCOPE_COLLECTORS: list[tuple[str, str, object]] = [
    ("esi-killmails.read_killmails.v1",   "killmails",      populate_killmails),
    ("esi-characters.read_fatigue.v1",    "fatigue",        populate_fatigue),
    ("esi-characters.read_fw.v1",         "freelance_jobs", populate_freelance_jobs),
]
NO_SCOPE_COLLECTORS: list[tuple[str, object]] = []
