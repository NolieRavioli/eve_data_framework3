"""Fetch and cache ESI market history (daily OHLC + volume) in DuckDB.

**Table ownership:**

- ``market_history`` — owned by this collector via :func:`ensure_tables`

Market history is immutable once a day's data is published — rows for past
dates never change.  Only the most recent day's row may be updated during a
re-fetch.  This makes aggressive caching safe.
"""

import logging

from core.db.public import connect as public_connect
from core.db.writer import db_executemany
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


# ── Table DDL — this collector OWNS market_history ────────────────────────────

def ensure_tables(con) -> None:
    """Idempotent DDL for the market_history table."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS market_history (
            type_id      INTEGER NOT NULL,
            region_id    INTEGER NOT NULL,
            date         DATE NOT NULL,
            lowest       DOUBLE,
            highest      DOUBLE,
            average      DOUBLE,
            volume       BIGINT,
            order_count  INTEGER,
            PRIMARY KEY (type_id, region_id, date)
        )
    """)


def cache_history_rows(type_id: int, region_id: int, data: list[dict]) -> None:
    """Write ESI history response rows to the DuckDB cache.

    Called from the market type_history route after a successful ESI fetch.
    DDL is executed via a direct connection (idempotent); data writes go
    through the serialised writer.
    """
    if not data:
        return

    con = public_connect(read_only=False)
    try:
        ensure_tables(con)
    finally:
        con.close()

    rows = []
    for d in data:
        try:
            rows.append((
                type_id,
                region_id,
                d["date"],
                d.get("lowest"),
                d.get("highest"),
                d.get("average"),
                d.get("volume", 0),
                d.get("order_count", 0),
            ))
        except (KeyError, TypeError):
            continue

    if rows:
        db_executemany(
            """
            INSERT INTO market_history
                (type_id, region_id, date, lowest, highest, average, volume, order_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (type_id, region_id, date) DO UPDATE SET
                lowest      = excluded.lowest,
                highest     = excluded.highest,
                average     = excluded.average,
                volume      = excluded.volume,
                order_count = excluded.order_count
            """,
            rows,
        )
        logger.debug(
            "Cached %d history rows for type %d region %d",
            len(rows), type_id, region_id,
        )


def fetch_market_history(type_id: int, region_id: int) -> list[dict]:
    """Fetch market history for a type/region from ESI and cache it.

    Returns the parsed JSON list, or an empty list on failure.
    """
    url = f"{ESI_BASE}/markets/{region_id}/history/"
    resp = esi_get(url, params={"type_id": type_id})
    if not resp.ok:
        logger.warning("ESI %s fetching history for type %d region %d",
                        resp.status_code, type_id, region_id)
        return []

    data = resp.json()
    cache_history_rows(type_id, region_id, data)
    return data
