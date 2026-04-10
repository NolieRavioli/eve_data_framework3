"""collectors/public_data/alliances.py — Fetch all alliance IDs from ESI.

Writes bare alliance_id rows to the ``alliances`` table.
Alliance details are enriched by ``analysis/alliance_enrichment.py``.

**Table ownership:** ``alliances``
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
        CREATE TABLE IF NOT EXISTS alliances (
            alliance_id             BIGINT PRIMARY KEY,
            name                    TEXT,
            ticker                  TEXT,
            creator_id              BIGINT,
            creator_corporation_id  BIGINT,
            executor_corporation_id BIGINT,
            faction_id              INTEGER,
            date_founded            TIMESTAMP,
            member_corp_ids         BIGINT[],
            fetched_at              TIMESTAMP DEFAULT now()
        )
    """)


def fetch_alliances() -> None:
    """Seed the alliances table with all current alliance IDs from ESI."""
    con = public_connect(read_only=False)
    try:
        ensure_tables(con)
    finally:
        con.close()

    resp = esi_get(f"{ESI_BASE}/alliances/")
    if not resp.ok:
        logger.warning("[alliances] ESI %s fetching alliance list", resp.status_code)
        return

    alliance_ids: list[int] = resp.json()
    logger.info("[alliances] Seeding %s alliance IDs", len(alliance_ids))

    # Insert bare rows — analysis/alliance_enrichment.py fills the rest
    db_executemany("""
        INSERT INTO alliances (alliance_id, fetched_at)
        VALUES (?, now())
        ON CONFLICT (alliance_id) DO UPDATE SET fetched_at = now()
    """, [(aid,) for aid in alliance_ids])
    logger.info("[alliances] Done")
