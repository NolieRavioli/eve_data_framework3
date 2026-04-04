"""Fetch NPC region market orders from ESI and write them to the public DuckDB.

Handles all public NPC station market orders across every EVE region that has
not been recently refreshed.  Regions are skipped when their cooldown entry in
``market_region_cooldowns`` has not yet expired — see
:func:`core.db.publicDB.list_market_region_ids` and
:func:`core.db.publicDB.mark_region_market_refreshed`.

Rate limiting, ETag caching, and 429 back-off are handled transparently by
:func:`core.queue.esi_req.esi_get`; callers in this module do not need their
own retry loops.

**Table ownership:**

- ``market_orders`` — owned by this collector via :func:`ensure_tables`
- ``market_region_cooldowns`` — owned by this collector via :func:`ensure_tables`

**Write strategy:**

Orders are upserted to DuckDB immediately as each ESI page arrives via the
non-blocking ``db_executemany_nowait`` path.  The writer thread's coalesce
logic automatically merges consecutive same-SQL batches (up to 50 k rows per
BEGIN/COMMIT cycle), so the per-page 1 k-row submissions become large
vectorised commits without any Python-side accumulation.

A ``refresh_start`` timestamp is recorded before page 1 of each region is
fetched.  After all pages have been submitted, a non-blocking DELETE removes
any orders whose ``last_seen`` pre-dates ``refresh_start`` — i.e. orders that
were in the DB from a previous fetch but were not present in this refresh cycle.
Because the write queue is FIFO, the DELETE always executes after every upsert
for the region has committed, with no additional coordination required.

Crash safety is improved over the old approach: each committed page is
immediately durable.  A crash mid-region leaves the already-committed pages
intact; the stale-cleanup DELETE fires correctly on the next successful run.
"""

import logging
from datetime import datetime, timedelta, timezone

from core.db.publicDB import connect as public_connect
from core.db import publicDB as sde_store
from core.queue.esi_req import esi_get
from core.db.writer import db_write_nowait

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"

_REGION_COOLDOWN_SECONDS = 3600          # 1 hour between successful region refreshes
_STATION_FORBIDDEN_DAYS = 1              # mark stations forbidden for 1 day on ESI error


# ── Table DDL — this collector OWNS market_orders + market_region_cooldowns ───

def ensure_tables(con) -> None:
    """Create market tables if they do not already exist.

    Idempotent and safe to call on every startup or before any write.
    Owns the DDL for both ``market_orders`` and ``market_region_cooldowns``.

    If ``market_orders`` exists without a PRIMARY KEY on ``order_id`` (legacy
    schema), the table is migrated in-place: renamed, recreated with the PK,
    deduplicated data copied across, and the old table dropped.

    :param con: An open, writable DuckDB connection.
    """
    _MARKET_ORDERS_DDL = """
        CREATE TABLE market_orders (
            order_id      BIGINT PRIMARY KEY,
            type_id       BIGINT,
            location_id   BIGINT,
            region_id     BIGINT,
            is_buy_order  BOOLEAN,
            issued        TIMESTAMP,
            duration      BIGINT,
            price         DOUBLE,
            order_range   VARCHAR,
            volume_remain BIGINT,
            volume_total  BIGINT,
            min_volume    BIGINT,
            last_seen     TIMESTAMP
        )
    """
    has_table = con.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'market_orders'"
    ).fetchone()[0] > 0
    if has_table:
        has_pk = con.execute(
            "SELECT COUNT(*) FROM duckdb_constraints() "
            "WHERE table_name = 'market_orders' AND constraint_type = 'PRIMARY KEY'"
        ).fetchone()[0] > 0
        if not has_pk:
            logger.info(
                "[ensure_tables] Migrating market_orders: adding PRIMARY KEY on order_id"
            )
            con.execute("DROP TABLE IF EXISTS market_orders_old")
            con.execute("DROP INDEX IF EXISTS idx_market_orders_region")
            con.execute("ALTER TABLE market_orders RENAME TO market_orders_old")
            con.execute(_MARKET_ORDERS_DDL)
            con.execute("""
                INSERT INTO market_orders
                SELECT DISTINCT ON (order_id) *
                FROM market_orders_old
                ORDER BY order_id, last_seen DESC NULLS LAST
            """)
            con.execute("DROP TABLE market_orders_old")
    else:
        con.execute(_MARKET_ORDERS_DDL)

    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_market_orders_region
        ON market_orders (region_id)
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS market_region_cooldowns (
            region_id       BIGINT PRIMARY KEY,
            refreshed_until TIMESTAMP
        )
    """)


def ensure_columns(con) -> None:
    """Add market cooldown tracking columns to ``dim_stations`` (enrichment pattern).

    ``dim_stations`` is owned by the SDE loader; we add columns here following
    the enrichment pattern from AGENTS.md.  Wrapped in a try/except in the
    caller because the SDE may not be loaded yet.
    """
    con.execute(
        "ALTER TABLE dim_stations ADD COLUMN IF NOT EXISTS market_forbidden_until TIMESTAMP"
    )
    con.execute(
        "ALTER TABLE dim_stations ADD COLUMN IF NOT EXISTS market_refreshed_until TIMESTAMP"
    )


# ── Station cooldown helpers ──────────────────────────────────────────────────

def _mark_stations_refreshed(region_id: int) -> None:
    """Set market_refreshed_until on all dim_stations rows for this region."""
    refreshed_until = datetime.now(timezone.utc) + timedelta(seconds=_REGION_COOLDOWN_SECONDS)
    db_write_nowait(
        "UPDATE dim_stations SET market_refreshed_until = ? WHERE region_id = ?",
        [refreshed_until, region_id],
    )


def _mark_stations_forbidden(region_id: int) -> None:
    """Set market_forbidden_until on all dim_stations rows for this region."""
    forbidden_until = datetime.now(timezone.utc) + timedelta(days=_STATION_FORBIDDEN_DAYS)
    db_write_nowait(
        "UPDATE dim_stations SET market_forbidden_until = ? WHERE region_id = ?",
        [forbidden_until, region_id],
    )


# ── Worker ────────────────────────────────────────────────────────────────────

def fetch_all_market_data() -> None:
    """Fetch NPC station market orders for all due regions and persist them.

    Regions whose cooldown has not expired are excluded automatically by
    :func:`core.db.publicDB.list_market_region_ids`.

    For each eligible region the fetch proceeds as follows:

    1. ``refresh_start`` is recorded (UTC) before page 1 is fetched.
    2. **Page 1** is fetched to discover the total page count from the
       ``X-Pages`` response header.  Regions that return a non-OK status or
       an empty order list are skipped entirely.
    3. Each page's orders are upserted to ``market_orders`` immediately via
       the non-blocking ``upsert_market_orders`` path — the write queue
       coalesces consecutive same-SQL batches automatically, so the 1 k-row
       per-page submissions become large vectorised commits without any
       Python-side accumulation.  The ESI fetch loop for subsequent pages
       runs concurrently with the writer committing earlier pages.
    4. After all pages are submitted, a non-blocking DELETE removes orders
       whose ``last_seen`` pre-dates ``refresh_start`` (i.e. orders absent
       from the current refresh cycle).  The FIFO write queue guarantees the
       DELETE executes only after every upsert has committed.
    5. Region cooldown and station timestamps are updated (non-blocking).

    Rate limiting, ETag caching, and 429 back-off are delegated to
    :func:`core.queue.esi_req.esi_get`.
    """
    con = public_connect(read_only=False)
    try:
        ensure_tables(con)
        try:
            ensure_columns(con)
        except Exception as exc:
            logger.debug("dim_stations columns skipped (%s) — SDE not loaded yet?", exc)
        con.execute("CHECKPOINT")
    finally:
        con.close()

    region_ids = sde_store.list_market_region_ids(skip_recently_refreshed=True)
    if not region_ids:
        # Distinguish between "all on cooldown" and "dim_regions not loaded"
        all_ids = sde_store.list_market_region_ids(skip_recently_refreshed=False)
        if not all_ids:
            logger.warning(
                "No regions found — SDE may not be loaded (dim_regions missing)."
            )
        else:
            logger.info("All regions refreshed recently — nothing to do.")
        return
    logger.info("Processing %s regions...", len(region_ids))

    for region_id in region_ids:
        # Record the start time before any pages are fetched.  Orders whose
        # last_seen is older than this were not present in the current refresh
        # and will be cleaned up after all pages are submitted.
        refresh_start = datetime.now(timezone.utc)

        url = f"{ESI_BASE}/markets/{region_id}/orders/"
        params_base = {"order_type": "all", "datasource": "tranquility"}

        resp = esi_get(url, params={**params_base, "page": 1})
        if not resp.ok:
            logger.warning(
                "%s on region %s page 1 — skipping",
                resp.status_code, region_id,
            )
            if resp.status_code in (403, 404):
                _mark_stations_forbidden(region_id)
            continue
        orders = resp.json()
        if not orders:
            continue

        total_pages = int(resp.headers.get("X-Pages", 1))
        total_rows = len(orders)
        logger.info("Region %s page 1/%s — %s orders", region_id, total_pages, len(orders))

        # Upsert page 1 immediately — non-blocking, writer coalesces batches.
        sde_store.upsert_market_orders([{**o, "region_id": region_id} for o in orders])

        for page in range(2, total_pages + 1):
            resp = esi_get(url, params={**params_base, "page": page})
            if not resp.ok:
                logger.warning(
                    "%s on region %s page %s — skipping",
                    resp.status_code, region_id, page,
                )
                continue
            orders = resp.json()
            if not orders:
                break
            total_rows += len(orders)
            logger.info("Region %s page %s/%s — %s orders", region_id, page, total_pages, len(orders))
            # Upsert each page as it arrives — no accumulation in RAM.
            sde_store.upsert_market_orders([{**o, "region_id": region_id} for o in orders])

        # All page upserts are in the write queue.  The stale-cleanup DELETE is
        # enqueued after them so it executes once every new order is committed.
        sde_store.cleanup_stale_market_orders_for_region(region_id, refresh_start)
        sde_store.mark_region_market_refreshed(region_id, cooldown_seconds=_REGION_COOLDOWN_SECONDS)
        _mark_stations_refreshed(region_id)
        logger.info("Region %s done — %s orders submitted", region_id, total_rows)

    logger.info("Completed")

