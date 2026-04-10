"""collectors/public_data/industry.py — Industry facilities and cost indices.

**Table ownership:** ``industry_facilities``, ``industry_cost_indices``
"""

from __future__ import annotations

import logging

from core.io.public import connect as public_connect
from core.io.writer import db_executemany
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS industry_facilities (
            facility_id     BIGINT PRIMARY KEY,
            owner_id        BIGINT,
            region_id       INTEGER,
            solar_system_id INTEGER,
            type_id         INTEGER,
            tax             REAL,
            fetched_at      TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS industry_cost_indices (
            solar_system_id INTEGER NOT NULL,
            activity        TEXT NOT NULL,
            cost_index      DOUBLE NOT NULL,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (solar_system_id, activity)
        )
    """)


def fetch_industry_data() -> None:
    """Fetch industry facilities and system cost indices from ESI."""
    con = public_connect(read_only=False)
    try:
        ensure_tables(con)
    finally:
        con.close()

    # Facilities
    resp = esi_get(f"{ESI_BASE}/industry/facilities/")
    if resp.ok:
        rows = [(f["facility_id"], f.get("owner_id"), f.get("region_id"),
                 f.get("solar_system_id"), f.get("type_id"), f.get("tax"))
                for f in resp.json()]
        db_executemany("""
            INSERT INTO industry_facilities
                (facility_id, owner_id, region_id, solar_system_id, type_id, tax, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, now())
            ON CONFLICT (facility_id) DO UPDATE SET
                tax = excluded.tax, fetched_at = now()
        """, rows)
        logger.info("[industry] %s facilities updated", len(rows))

    # Cost indices
    resp = esi_get(f"{ESI_BASE}/industry/systems/")
    if resp.ok:
        rows = []
        for system in resp.json():
            sid = system["solar_system_id"]
            for idx in system.get("cost_indices", []):
                rows.append((sid, idx["activity"], idx["cost_index"]))
        db_executemany("""
            INSERT INTO industry_cost_indices
                (solar_system_id, activity, cost_index, fetched_at)
            VALUES (?, ?, ?, now())
            ON CONFLICT (solar_system_id, activity) DO UPDATE SET
                cost_index = excluded.cost_index, fetched_at = now()
        """, rows)
        logger.info("[industry] %s cost index rows updated", len(rows))
