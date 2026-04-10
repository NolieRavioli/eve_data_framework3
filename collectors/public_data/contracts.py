"""collectors/public_data/contracts.py — Public contracts for all market regions.

**Table ownership:** ``public_contracts``
Contract items/bids are enriched by ``analysis/public_contract_enrichment.py``.
"""

from __future__ import annotations

import logging

from core.db.public import connect as public_connect
from core.db.writer import db_executemany
from core.db import public as sde_store
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS public_contracts (
            contract_id             BIGINT PRIMARY KEY,
            region_id               INTEGER NOT NULL,
            issuer_id               BIGINT NOT NULL,
            issuer_corporation_id   BIGINT,
            assignee_id             BIGINT,
            type                    TEXT,
            status                  TEXT,
            title                   TEXT,
            for_corporation         BOOLEAN DEFAULT FALSE,
            availability            TEXT,
            date_issued             TIMESTAMP,
            date_expired            TIMESTAMP,
            days_to_complete        INTEGER,
            start_location_id       BIGINT,
            end_location_id         BIGINT,
            price                   DOUBLE DEFAULT 0,
            reward                  DOUBLE DEFAULT 0,
            collateral              DOUBLE DEFAULT 0,
            buyout                  DOUBLE DEFAULT 0,
            volume                  DOUBLE DEFAULT 0,
            items_json              TEXT,
            bids_json               TEXT,
            fetched_at              TIMESTAMP DEFAULT now()
        )
    """)


def fetch_public_contracts() -> None:
    """Fetch public contracts for all market regions."""
    con = public_connect(read_only=False)
    try:
        ensure_tables(con)
    finally:
        con.close()

    region_ids = sde_store.list_market_region_ids(skip_recently_refreshed=False) or []
    total_contracts = 0
    for region_id in region_ids:
        resp = esi_get(f"{ESI_BASE}/contracts/public/{region_id}/", params={"page": 1})
        if not resp.ok:
            continue
        contracts = resp.json()
        total_pages = int(resp.headers.get("X-Pages", 1))
        for page in range(2, total_pages + 1):
            r = esi_get(f"{ESI_BASE}/contracts/public/{region_id}/", params={"page": page})
            if r.ok:
                contracts.extend(r.json())

        rows = [(c["contract_id"], int(region_id), c["issuer_id"],
                 c.get("issuer_corporation_id"), c.get("assignee_id"), c.get("type"),
                 c.get("status"), c.get("title"), c.get("for_corporation", False),
                 c.get("availability"), c.get("date_issued"), c.get("date_expired"),
                 c.get("days_to_complete"), c.get("start_location_id"), c.get("end_location_id"),
                 c.get("price", 0), c.get("reward", 0), c.get("collateral", 0),
                 c.get("buyout", 0), c.get("volume", 0))
                for c in contracts]
        if rows:
            db_executemany("""
                INSERT INTO public_contracts
                    (contract_id, region_id, issuer_id, issuer_corporation_id, assignee_id,
                     type, status, title, for_corporation, availability, date_issued,
                     date_expired, days_to_complete, start_location_id, end_location_id,
                     price, reward, collateral, buyout, volume, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (contract_id) DO UPDATE SET
                    status = excluded.status, fetched_at = now()
            """, rows)
        total_contracts += len(rows)
        logger.debug("[contracts] Region %s — %s contracts", region_id, len(rows))

    logger.info("[contracts] Done — %s total contracts", total_contracts)
