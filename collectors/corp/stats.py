"""collectors/corp/stats.py — corp_stats and corp_alliance_history.

Both are public endpoints (no scope required).
"""

from __future__ import annotations

import logging

from core.db.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_stats (
            id                  INTEGER DEFAULT 1 PRIMARY KEY,
            alliance_id         BIGINT,
            ceo_id              BIGINT,
            creator_id          BIGINT,
            date_founded        TIMESTAMP,
            description         TEXT,
            faction_id          INTEGER,
            home_station_id     BIGINT,
            member_count        INTEGER,
            member_limit        INTEGER,
            name                TEXT,
            shares              BIGINT,
            tax_rate            REAL,
            ticker              TEXT,
            fetched_at          TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_alliance_history (
            record_id       INTEGER PRIMARY KEY,
            alliance_id     BIGINT,
            start_date      TIMESTAMP NOT NULL,
            is_deleted      BOOLEAN DEFAULT FALSE,
            fetched_at      TIMESTAMP DEFAULT now()
        )
    """)


def fetch_corp_stats(corporation_id: int, character_id: int, access_token: str) -> None:
    """Fetch public corp stats and alliance history."""
    con = connect_entity(corporation_id)
    try:
        _ensure_tables(con)
        # Corp info (public)
        resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/")
        if resp.ok:
            d = resp.json()
            con.execute("""
                INSERT INTO corp_stats
                    (id, alliance_id, ceo_id, creator_id, date_founded, description,
                     faction_id, home_station_id, member_count, member_limit, name,
                     shares, tax_rate, ticker, fetched_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (id) DO UPDATE SET
                    alliance_id = excluded.alliance_id, member_count = excluded.member_count,
                    ceo_id = excluded.ceo_id, tax_rate = excluded.tax_rate,
                    fetched_at = now()
            """, [d.get("alliance_id"), d.get("ceo_id"), d.get("creator_id"),
                  d.get("date_founded"), d.get("description"), d.get("faction_id"),
                  d.get("home_station_id"), d.get("member_count"), None, d.get("name"),
                  d.get("shares"), d.get("tax_rate"), d.get("ticker")])

        # Alliance history (public)
        hist_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/alliancehistory/")
        if hist_resp.ok:
            for h in hist_resp.json():
                con.execute("""
                    INSERT INTO corp_alliance_history
                        (record_id, alliance_id, start_date, is_deleted, fetched_at)
                    VALUES (?, ?, ?, ?, now())
                    ON CONFLICT (record_id) DO NOTHING
                """, [h["record_id"], h.get("alliance_id"), h.get("start_date"),
                      h.get("is_deleted", False)])
    finally:
        con.close()
    logger.info("[corp.stats] updated for corp %s", corporation_id)


def run_for_all_corps() -> None:
    """Entry point called by the scheduler."""
    from collectors.corp import get_corp_token_map
    token_map = get_corp_token_map()
    for corp_id, (char_id, access_token) in token_map.items():
        try:
            fetch_corp_stats(corp_id, char_id, access_token)
        except Exception:
            logger.exception("[corp.stats] failed for corp %s", corp_id)
