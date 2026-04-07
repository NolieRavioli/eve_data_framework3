"""Fetch NPC region market orders from ESI and write them to the public DuckDB.

Handles all public NPC station market orders across every EVE region that has
not been recently refreshed.  Regions are skipped when their cooldown entry in
``market_region_cooldowns`` has not yet expired — see
:func:`core.db.public.list_market_region_ids` and
:func:`core.db.public.mark_region_market_refreshed`.

Rate limiting, ETag caching, and 429 back-off are handled transparently by
:func:`core.esi.request.esi_get`; callers in this module do not need their
own retry loops.

**Table ownership:**

- ``market_orders`` — owned by this collector via :func:`ensure_tables`
- ``market_region_cooldowns`` — owned by this collector via :func:`ensure_tables`

**Write strategy — buffered per-region bulk replace:**

As ESI pages arrive they are accumulated in an in-memory buffer
(:mod:`core.db.market_buffer`) rather than written to DuckDB immediately.
The buffer is queryable — any ``market_price()`` call for a buffered region
returns the freshest in-flight data without touching disk.

Once all pages for a region have been collected the buffer is flushed:
a blocking DELETE + vectorised DataFrame INSERT replaces the region's orders
in ``market_orders`` atomically.  The ESI fetch for the next region can then
overlap with any DuckDB WAL housekeeping.

Crash safety: if the process dies mid-region, the in-memory buffer is lost
and the previous run's data remains on disk.  Because market orders are
public ESI data refreshed every hour the impact is negligible.
"""

import logging

from core.db.public import connect as public_connect
from core.db import public as sde_store
from core.db.market_buffer import begin_region, add_page, finish_region, discard_region
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"

_REGION_COOLDOWN_SECONDS = 3600          # 1 hour between successful region refreshes


# ── Table DDL — this collector OWNS market_orders + market_region_cooldowns ───

def ensure_tables(con) -> None:
    """Create market tables if they do not already exist.

    Idempotent and safe to call on every startup or before any write.
    Owns the DDL for both ``market_orders`` and ``market_region_cooldowns``.

    :param con: An open, writable DuckDB connection.
    """
    con.execute("""
        CREATE TABLE IF NOT EXISTS market_orders (
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
    """)
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


# ── Worker ────────────────────────────────────────────────────────────────────

def fetch_all_market_data() -> None:
    """Fetch NPC station market orders for all due regions and persist them.

    Regions whose cooldown has not expired are excluded automatically by
    :func:`core.db.public.list_market_region_ids`.

    For each eligible region the fetch proceeds as follows:

    1. **Page 1** is fetched to discover the total page count from the
       ``X-Pages`` response header.  Regions that return a non-OK status or
       an empty order list are skipped entirely.
    2. The region buffer is opened (:func:`begin_region`).  Each page's
       orders are appended to the in-memory buffer as they arrive — the
       data is immediately queryable by ``market_price()`` and other
       buffer-aware callers.
    3. Once all pages have been collected, :func:`finish_region` flushes
       the buffer to DuckDB via a blocking DELETE + vectorised DataFrame
       INSERT (``replace_market_orders_for_region``).  No per-row conflict
       checking is needed because the entire region is replaced.
    4. Region cooldown and station timestamps are updated.

    Rate limiting, ETag caching, and 429 back-off are delegated to
    :func:`core.esi.request.esi_get`.
    """
    con = public_connect(read_only=False)
    try:
        ensure_tables(con)
        con.execute("CHECKPOINT")
    finally:
        con.close()

    region_ids = sde_store.list_market_region_ids(skip_recently_refreshed=True)
    if not region_ids:
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
        url = f"{ESI_BASE}/markets/{region_id}/orders/"
        params_base = {"order_type": "all", "datasource": "tranquility"}

        resp = esi_get(url, params={**params_base, "page": 1})
        if not resp.ok:
            logger.warning(
                "%s on region %s page 1 — skipping",
                resp.status_code, region_id,
            )
            continue
        orders = resp.json()
        if not orders:
            continue

        total_pages = int(resp.headers.get("X-Pages", 1))
        total_rows = len(orders)
        logger.info("Region %s page 1/%s — %s orders", region_id, total_pages, len(orders))

        # Buffer all pages in RAM — queryable immediately.
        begin_region(region_id)
        try:
            add_page(region_id, [{**o, "region_id": region_id} for o in orders])

            for page in range(2, total_pages + 1):
                resp = esi_get(url, params={**params_base, "page": page})
                if not resp.ok:
                    logger.warning(
                        "%s on region %s page %s — skipping page",
                        resp.status_code, region_id, page,
                    )
                    continue
                orders = resp.json()
                if not orders:
                    break
                total_rows += len(orders)
                logger.info("Region %s page %s/%s — %s orders", region_id, page, total_pages, len(orders))
                add_page(region_id, [{**o, "region_id": region_id} for o in orders])

            # Flush buffer → DELETE + bulk INSERT (blocking).
            finish_region(region_id)
        except Exception:
            discard_region(region_id)
            raise

        sde_store.mark_region_market_refreshed(region_id, cooldown_seconds=_REGION_COOLDOWN_SECONDS)
        logger.info("Region %s done — %s orders written", region_id, total_rows)

    logger.info("Completed")

