"""analysis/corporation_discovery.py — Discover and enrich corporation records.

Aggregates corporation_ids from:
  - ``auth_users.corporation_id`` (public DuckDB)
  - character DuckDBs ``characters.corporation_id``
  - ``alliances.member_corp_ids`` (public DuckDB)

Then inserts bare rows into ``corporations`` for any unknown corp and calls
GET /corporations/{id} to fill details.

**Table ownership:** ``corporations`` (public DuckDB) — DDL in this module.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import core.db.public as db
from core.db.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS corporations (
            corporation_id  BIGINT PRIMARY KEY,
            alliance_id     BIGINT,
            ceo_id          BIGINT,
            creator_id      BIGINT,
            date_founded    TIMESTAMP,
            description     TEXT,
            faction_id      INTEGER,
            home_station_id BIGINT,
            member_count    INTEGER,
            name            TEXT,
            shares          BIGINT,
            tax_rate        REAL,
            ticker          TEXT,
            member_limit    INTEGER,
            fetched_at      TIMESTAMP DEFAULT now()
        )
    """)


def _collect_corp_ids() -> set[int]:
    """Gather all known corporation IDs from the public DuckDB."""
    corp_ids: set[int] = set()
    con = db.connect()
    try:
        _ensure_tables(con)

        # From auth_users
        rows = con.execute(
            "SELECT DISTINCT corporation_id FROM auth_users WHERE corporation_id IS NOT NULL"
        ).fetchall()
        corp_ids.update(r[0] for r in rows)

        # From alliances.member_corp_ids (DuckDB BIGINT[] column)
        try:
            rows = con.execute(
                "SELECT member_corp_ids FROM alliances WHERE member_corp_ids IS NOT NULL"
            ).fetchall()
            for (ids,) in rows:
                if ids:
                    corp_ids.update(ids)
        except Exception:
            pass
    finally:
        con.close()

    # From character DuckDBs
    private_root = Path(os.environ.get("EVE_PRIVATE_DATABASE_FOLDER", "_privateData"))
    for owner_dir in private_root.iterdir():
        if not owner_dir.is_dir() or not owner_dir.name.isdigit():
            continue
        try:
            char_con = connect_entity(int(owner_dir.name))
            try:
                rows = char_con.execute(
                    "SELECT DISTINCT corporation_id FROM characters WHERE corporation_id IS NOT NULL"
                ).fetchall()
                corp_ids.update(r[0] for r in rows)
            finally:
                char_con.close()
        except Exception:
            pass

    return corp_ids


def run_corporation_discovery() -> None:
    """Discover and enrich all corporation records."""
    all_corp_ids = _collect_corp_ids()
    if not all_corp_ids:
        logger.info("[corp_discovery] No corp IDs found.")
        return

    con = db.connect()
    try:
        _ensure_tables(con)
        existing = {r[0] for r in con.execute("SELECT corporation_id FROM corporations").fetchall()}
    finally:
        con.close()

    new_ids = all_corp_ids - existing
    if new_ids:
        con = db.connect()
        try:
            con.executemany(
                "INSERT INTO corporations (corporation_id, fetched_at) VALUES (?, now()) "
                "ON CONFLICT (corporation_id) DO NOTHING",
                [(cid,) for cid in new_ids]
            )
        finally:
            con.close()
        logger.info("[corp_discovery] Inserted %s new bare corp rows", len(new_ids))

    # Enrich rows where name IS NULL
    con = db.connect()
    try:
        unenriched = [r[0] for r in con.execute(
            "SELECT corporation_id FROM corporations WHERE name IS NULL"
        ).fetchall()]
    finally:
        con.close()

    logger.info("[corp_discovery] Enriching %s corporations", len(unenriched))
    enriched = 0
    for corp_id in unenriched:
        try:
            resp = esi_get(f"{ESI_BASE}/corporations/{corp_id}/")
            if not resp.ok:
                continue
            d = resp.json()
            con = db.connect()
            try:
                con.execute("""
                    UPDATE corporations SET
                        alliance_id = ?, ceo_id = ?, creator_id = ?, date_founded = ?,
                        description = ?, faction_id = ?, home_station_id = ?,
                        member_count = ?, name = ?, shares = ?, tax_rate = ?,
                        ticker = ?, fetched_at = now()
                    WHERE corporation_id = ?
                """, [d.get("alliance_id"), d.get("ceo_id"), d.get("creator_id"),
                      d.get("date_founded"), d.get("description"), d.get("faction_id"),
                      d.get("home_station_id"), d.get("member_count"), d.get("name"),
                      d.get("shares"), d.get("tax_rate"), d.get("ticker"), corp_id])
            finally:
                con.close()
            enriched += 1
        except Exception:
            logger.exception("[corp_discovery] Failed for corp %s", corp_id)

    logger.info("[corp_discovery] Done — %s/%s enriched", enriched, len(unenriched))
