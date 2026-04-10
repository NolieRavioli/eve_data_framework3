"""collectors/character/skillqueue.py — character skill queue collector.

Registered scheduler job: ``character_skillqueue_refresh`` (interval 30 min).
"""

from __future__ import annotations

import logging

import core.io.public as db
from core.auth.tokens import pick_token, fresh_token
from core.io.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_skill_queue (
            character_id        BIGINT NOT NULL,
            queue_position      INTEGER NOT NULL,
            skill_id            INTEGER NOT NULL,
            finished_level      INTEGER NOT NULL,
            start_date          TIMESTAMP,
            finish_date         TIMESTAMP,
            level_start_sp      INTEGER,
            level_end_sp        INTEGER,
            training_start_sp   INTEGER,
            fetched_at          TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, queue_position)
        )
    """)


def fetch_skillqueue(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/skillqueue/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[skillqueue] ESI %s for char %s", resp.status_code, character_id)
        return
    data = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        # Full replace — skill queue changes frequently
        con.execute("DELETE FROM character_skill_queue WHERE character_id = ?", [character_id])
        for item in data:
            con.execute("""
                INSERT INTO character_skill_queue
                    (character_id, queue_position, skill_id, finished_level,
                     start_date, finish_date, level_start_sp, level_end_sp,
                     training_start_sp, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, now())
            """, [character_id, item["queue_position"], item["skill_id"], item["finished_level"],
                  item.get("start_date"), item.get("finish_date"),
                  item.get("level_start_sp"), item.get("level_end_sp"),
                  item.get("training_start_sp")])
    finally:
        con.close()
    logger.info("[skillqueue] %d entries for char %s", len(data), character_id)


def run_skillqueue_refresh() -> None:
    """Public entry point — called by the scheduler.
    Iterates all known owners and refreshes their skill queues.
    """
    con = db.connect()
    try:
        rows = con.execute("SELECT DISTINCT owner_id FROM auth_users").fetchall()
        owner_ids = [r[0] for r in rows]
    finally:
        con.close()

    REQUIRED_SCOPE = "esi-skills.read_skillqueue.v1"

    for owner_id in owner_ids:
        try:
            char_id, token_data = pick_token(owner_id)
            char_id, token_data = fresh_token(owner_id, char_id, token_data)
        except Exception:
            logger.warning("[skillqueue] no token for owner %s", owner_id)
            continue

        scopes = set((token_data.get("scopes") or "").split())
        if REQUIRED_SCOPE not in scopes:
            continue

        try:
            fetch_skillqueue(owner_id, char_id, token_data["access_token"])
        except Exception:
            logger.exception("[skillqueue] failed for owner %s char %s", owner_id, char_id)
