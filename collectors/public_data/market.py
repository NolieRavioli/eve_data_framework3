"""collectors/public_data/market.py — All public market collectors.

Migrated from collectors/market/{regions,structures,history}.py (Phase 5).
Old modules re-export from here for backward compatibility.

**Table ownership:**

- ``market_orders``           — :func:`ensure_tables`
- ``market_region_cooldowns`` — :func:`ensure_tables`
- ``market_structures``       — :func:`ensure_tables`
- ``market_history``          — :func:`ensure_tables`
- ``market_prices``           — :func:`ensure_tables`
- ``market_items``            — :func:`ensure_tables`
- ``structures`` cooldown cols — enrichment via :func:`ensure_structure_columns`

**Entry points for scheduler:**

- :func:`fetch_region_orders`      — NPC region market orders (every hour)
- :func:`fetch_structure_orders`   — player structure market orders (every hour)
- :func:`fetch_market_meta`        — market prices + active item lists (every hour)
- :func:`fetch_active_market_history` — batch history (daily, starts DISABLED)

**Backward-compatible aliases (old import paths still work):**

- ``fetch_all_market_data``        → :func:`fetch_region_orders`
- ``update_structure_market_orders`` → :func:`fetch_structure_orders`
- ``fetch_market_history``         → :func:`on_demand_history`
- ``cache_history_rows``           → :func:`cache_history_rows`
"""

import logging
import time
from datetime import datetime

from core.db.public import connect as public_connect
from core.db import public as sde_store
from core.db.market_buffer import begin_region, add_page, finish_region, discard_region
from core.db.writer import db_executemany
from core.esi import esi_get as _esi_get
import core.db.sde as sde
from core.auth import resolve_default_owner_id, pick_token, fresh_token
from core.config import get_market_config, get_structures_config

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"
DATASOURCE = {"datasource": "tranquility"}

_REGION_COOLDOWN_SECONDS = 3600

# Sentinels for structure market access
_MARKET_403 = object()
_MARKET_404 = object()
_ENRICH_403 = object()
_ENRICH_404 = object()

_STRUCTURE_INFO_CACHE: dict[int, tuple[float, dict]] = {}
_STRUCTURE_INFO_TTL = 24 * 3600


# ── Table DDL ─────────────────────────────────────────────────────────────────

def ensure_tables(con) -> None:
    """Idempotent DDL for all market tables."""
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
    con.execute("""
        CREATE TABLE IF NOT EXISTS market_structures (
            structure_id    BIGINT PRIMARY KEY,
            solar_system_id BIGINT,
            region_id       BIGINT,
            owner_id        BIGINT,
            name            VARCHAR,
            type_id         BIGINT,
            position_json   VARCHAR,
            last_seen       TIMESTAMP
        )
    """)
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
    con.execute("""
        CREATE TABLE IF NOT EXISTS market_prices (
            type_id         INTEGER PRIMARY KEY,
            average_price   DOUBLE,
            adjusted_price  DOUBLE,
            fetched_at      TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS market_items (
            region_id   INTEGER NOT NULL,
            type_id     INTEGER NOT NULL,
            fetched_at  TIMESTAMP DEFAULT now(),
            PRIMARY KEY (region_id, type_id)
        )
    """)


def ensure_structure_columns(con) -> None:
    """Add cooldown columns to the structures table (enrichment pattern)."""
    from collectors.public_data.structures import ensure_tables as _ensure_structures
    _ensure_structures(con)
    con.execute("ALTER TABLE structures ADD COLUMN IF NOT EXISTS market_forbidden_until TIMESTAMP")
    con.execute("ALTER TABLE structures ADD COLUMN IF NOT EXISTS market_refreshed_until TIMESTAMP")


# ── Region market orders (NPC stations) ───────────────────────────────────────

def fetch_region_orders() -> None:
    """Fetch NPC station market orders for all due regions.

    Scheduler entry point — runs every hour per job config.
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
            logger.warning("No regions found — SDE may not be loaded.")
        else:
            logger.info("All regions refreshed recently — nothing to do.")
        return
    logger.info("Processing %s regions...", len(region_ids))

    for region_id in region_ids:
        url = f"{ESI_BASE}/markets/{region_id}/orders/"
        params_base = {"order_type": "all", "datasource": "tranquility"}

        resp = _esi_get(url, params={**params_base, "page": 1})
        if not resp.ok:
            logger.warning("%s on region %s page 1 — skipping", resp.status_code, region_id)
            continue
        orders = resp.json()
        if not orders:
            continue

        total_pages = int(resp.headers.get("X-Pages", 1))
        total_rows = len(orders)
        logger.info("Region %s page 1/%s — %s orders", region_id, total_pages, len(orders))

        begin_region(region_id)
        try:
            add_page(region_id, [{**o, "region_id": region_id} for o in orders])

            for page in range(2, total_pages + 1):
                resp = _esi_get(url, params={**params_base, "page": page})
                if not resp.ok:
                    logger.warning("%s on region %s page %s — skipping page",
                                   resp.status_code, region_id, page)
                    continue
                orders = resp.json()
                if not orders:
                    break
                total_rows += len(orders)
                add_page(region_id, [{**o, "region_id": region_id} for o in orders])

            finish_region(region_id)
        except Exception:
            discard_region(region_id)
            raise

        sde_store.mark_region_market_refreshed(region_id,
                                               cooldown_seconds=_REGION_COOLDOWN_SECONDS)
        logger.info("Region %s done — %s orders written", region_id, total_rows)

    logger.info("Completed")


# ── Structure market orders (player-owned) ────────────────────────────────────

def _fetch_structure_order_page(structure_id: int, token: str, page: int = 1,
                                 retries: int = 3) -> tuple[list, int]:
    url = f"{ESI_BASE}/markets/structures/{structure_id}/"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    for attempt in range(1, retries + 1):
        try:
            resp = _esi_get(url, headers=headers,
                            params={**DATASOURCE, "page": page}, timeout=15)
            if resp.status_code == 403:
                return _MARKET_403, 1
            if resp.status_code == 404:
                return _MARKET_404, 1
            resp.raise_for_status()
            return resp.json(), int(resp.headers.get("x-pages", 1))
        except Exception as exc:
            logger.warning("[market.structures] attempt %s/%s for %s page %s: %s",
                           attempt, retries, structure_id, page, exc)
    logger.error("[market.structures] failed after %s retries for %s page %s",
                 retries, structure_id, page)
    return [], 1


def _fetch_structure_details_cached(structure_id: int, token: str) -> "dict | object | None":
    now = time.time()
    cached = _STRUCTURE_INFO_CACHE.get(structure_id)
    if cached and cached[0] > now:
        return cached[1]

    url = f"{ESI_BASE}/universe/structures/{structure_id}/"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        resp = _esi_get(url, headers=headers, params=DATASOURCE, timeout=15)
    except Exception as exc:
        logger.warning("[market.structures] metadata request failed for %s: %s", structure_id, exc)
        return None

    if resp.status_code in (403, 404):
        return _ENRICH_403 if resp.status_code == 403 else _ENRICH_404

    try:
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("[market.structures] failed to parse metadata for %s: %s", structure_id, exc)
        return None

    _STRUCTURE_INFO_CACHE[structure_id] = (now + _STRUCTURE_INFO_TTL, data)
    return data


def _populate_structure_metadata(structure: dict, token: str) -> tuple[dict, str]:
    updated = dict(structure)
    needs_lookup = not (
        updated.get("solar_system_id") and updated.get("name")
        and updated.get("type_id") and updated.get("owner_id")
    )
    if needs_lookup:
        info = _fetch_structure_details_cached(updated["structure_id"], token)
        if info is _ENRICH_403:
            updated["last_seen"] = datetime.utcnow()
            return updated, "unauthorized"
        if info is _ENRICH_404:
            updated["last_seen"] = datetime.utcnow()
            return updated, "forbidden"
        if info is None:
            updated["last_seen"] = datetime.utcnow()
            return updated, "error"
        updated["name"] = info.get("name")
        updated["solar_system_id"] = info.get("solar_system_id")
        updated["owner_id"] = info.get("owner_id")
        updated["type_id"] = info.get("type_id")
        enrich_status = "success"
    else:
        enrich_status = "skipped"

    if updated.get("solar_system_id") and not updated.get("region_id"):
        updated["region_id"] = sde.region_id_from_system_id(updated["solar_system_id"])

    updated["last_seen"] = datetime.utcnow()
    return updated, enrich_status


def fetch_structure_orders() -> None:
    """Fetch player structure market orders.

    Scheduler entry point — runs every hour per job config.
    """
    _mc = get_market_config()
    _sc = get_structures_config()
    market_unauthorized_cooldown = int(_mc.get("unauthorized_cooldown_days", 7)) * 86400
    market_forbidden_cooldown    = int(_mc.get("forbidden_cooldown_days", 21)) * 86400
    market_authorized_cooldown   = int(_mc.get("authorized_cooldown_seconds", 3600))
    enrich_unauthorized_cooldown = int(_sc.get("unauthorized_cooldown_days", 7)) * 86400
    enrich_forbidden_cooldown    = int(_sc.get("forbidden_cooldown_days", 21)) * 86400
    enrich_authorized_cooldown   = int(_sc.get("authorized_cooldown_seconds", 3600))
    max_retries                  = int(_mc.get("max_retries", 3))

    con = public_connect(read_only=False)
    try:
        ensure_tables(con)
        ensure_structure_columns(con)
    finally:
        con.close()

    owner_id = resolve_default_owner_id()
    if owner_id is None:
        logger.error("[market.structures] No private owner directories found.")
        return

    _char_id, token_data = pick_token(owner_id)
    token = token_data["access_token"]
    structures = sde_store.list_public_structures(skip_market_forbidden=True)
    total = len(structures)
    logger.info("[market.structures] Checking %s structures.", total)

    skipped = 0
    market_unauthorized_ids: list[int] = []
    market_forbidden_ids: list[int] = []
    orders_total = 0
    t0 = time.time()
    log_every = max(1, total // 20) if total else 1

    for count, structure in enumerate(structures, start=1):
        num_orders = 0
        structure_id = structure["structure_id"]
        try:
            _char_id, token_data = fresh_token(owner_id, _char_id, token_data)
            token = token_data["access_token"]

            structure, enrich_status = _populate_structure_metadata(structure, token)
            sde_store.upsert_structures([structure])
            sde_store.upsert_market_structures([structure])

            if enrich_status == "success":
                sde_store.mark_structures_enrich_refreshed([structure_id], enrich_authorized_cooldown)
            elif enrich_status == "unauthorized":
                sde_store.mark_structures_forbidden([structure_id], enrich_unauthorized_cooldown)
            elif enrich_status == "forbidden":
                sde_store.mark_structures_forbidden([structure_id], enrich_forbidden_cooldown)

            orders, pages = _fetch_structure_order_page(structure_id, token, page=1,
                                                        retries=max_retries)
            if orders is _MARKET_403:
                market_unauthorized_ids.append(structure_id)
                skipped += 1
                continue
            if orders is _MARKET_404:
                market_forbidden_ids.append(structure_id)
                skipped += 1
                continue
            if not orders:
                skipped += 1
                continue

            region_id = structure.get("region_id")
            all_rows = [{**o, "region_id": region_id, "location_id": structure_id}
                        for o in orders]
            num_orders += len(all_rows)

            for page in range(2, pages + 1):
                _char_id, token_data = fresh_token(owner_id, _char_id, token_data)
                token = token_data["access_token"]
                more, _ = _fetch_structure_order_page(structure_id, token, page=page,
                                                      retries=max_retries)
                page_rows = [{**o, "region_id": region_id, "location_id": structure_id}
                             for o in more]
                all_rows.extend(page_rows)
                num_orders += len(page_rows)

            sde_store.upsert_market_orders(all_rows)
            sde_store.mark_structures_market_refreshed([structure_id], market_authorized_cooldown)
            orders_total += num_orders

            if count % log_every == 0 or count == total:
                elapsed = time.time() - t0
                eta = (elapsed / count) * (total - count) if count else 0
                logger.info("[market.structures] %s/%s (%.1f%%) ETA %.0fs orders=%s skipped=%s",
                            count, total, (100 * count / total) if total else 100.0,
                            eta, f"{orders_total:,}", skipped)
        except Exception:
            logger.exception("[market.structures] Failed for %s.", structure_id)

    if market_unauthorized_ids:
        sde_store.mark_market_structures_forbidden(market_unauthorized_ids,
                                                   market_unauthorized_cooldown)
        logger.info("[market.structures] Marked %s structure(s) as market-403.",
                    len(market_unauthorized_ids))
    if market_forbidden_ids:
        sde_store.mark_market_structures_forbidden(market_forbidden_ids,
                                                   market_forbidden_cooldown)
        logger.info("[market.structures] Marked %s structure(s) as market-404.",
                    len(market_forbidden_ids))


# ── Market meta (prices + active type lists) ──────────────────────────────────

def fetch_market_meta() -> None:
    """Fetch market price index and active type_id lists for all regions.

    Scheduler entry point — runs every hour.
    Writes to ``market_prices`` and ``market_items``.
    """
    con = public_connect(read_only=False)
    try:
        ensure_tables(con)
    finally:
        con.close()

    # Market prices (universe-wide adjusted/average)
    resp = _esi_get(f"{ESI_BASE}/markets/prices/")
    if resp.ok:
        rows = [(p["type_id"], p.get("average_price"), p.get("adjusted_price"))
                for p in resp.json()]
        db_executemany("""
            INSERT INTO market_prices (type_id, average_price, adjusted_price, fetched_at)
            VALUES (?, ?, ?, now())
            ON CONFLICT (type_id) DO UPDATE SET
                average_price = excluded.average_price,
                adjusted_price = excluded.adjusted_price,
                fetched_at = now()
        """, rows)
        logger.info("[market.meta] Updated %s market prices", len(rows))

    # Active market items per region
    region_ids = sde_store.list_market_region_ids(skip_recently_refreshed=False) or []
    for region_id in region_ids:
        resp = _esi_get(f"{ESI_BASE}/markets/{region_id}/types/",
                        params={"page": 1})
        if not resp.ok:
            continue
        type_ids = resp.json()
        total = int(resp.headers.get("X-Pages", 1))
        for page in range(2, total + 1):
            r = _esi_get(f"{ESI_BASE}/markets/{region_id}/types/",
                         params={"page": page})
            if r.ok:
                type_ids.extend(r.json())
        rows = [(int(region_id), int(tid)) for tid in type_ids]
        if rows:
            db_executemany("""
                INSERT INTO market_items (region_id, type_id, fetched_at)
                VALUES (?, ?, now())
                ON CONFLICT (region_id, type_id) DO UPDATE SET fetched_at = now()
            """, rows)
        logger.debug("[market.meta] Region %s — %s active types", region_id, len(rows))


# ── Market history helpers (on-demand + batch) ────────────────────────────────

def cache_history_rows(type_id: int, region_id: int, data: list[dict]) -> None:
    """Cache ESI market history rows.  Called from route handlers after a live fetch."""
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
            rows.append((type_id, region_id, d["date"],
                         d.get("lowest"), d.get("highest"), d.get("average"),
                         d.get("volume", 0), d.get("order_count", 0)))
        except (KeyError, TypeError):
            continue

    if rows:
        db_executemany("""
            INSERT INTO market_history
                (type_id, region_id, date, lowest, highest, average, volume, order_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (type_id, region_id, date) DO UPDATE SET
                lowest = excluded.lowest, highest = excluded.highest,
                average = excluded.average, volume = excluded.volume,
                order_count = excluded.order_count
        """, rows)


def on_demand_history(type_id: int, region_id: int) -> list[dict]:
    """Fetch and cache market history for a single type/region.

    Called from route handlers when the user requests type history.
    Returns parsed JSON list, or [] on failure.
    """
    url = f"{ESI_BASE}/markets/{region_id}/history/"
    resp = _esi_get(url, params={"type_id": type_id})
    if not resp.ok:
        logger.warning("ESI %s fetching history for type %d region %d",
                       resp.status_code, type_id, region_id)
        return []
    data = resp.json()
    cache_history_rows(type_id, region_id, data)
    return data


def fetch_active_market_history() -> None:
    """Batch-fetch market history for all currently-active type_id/region combos.

    Scheduler entry point — runs daily, STARTS DISABLED.
    Reads from ``market_items`` to discover which type_ids are active per region,
    then fetches and caches history for each pair not updated today.
    """
    con = public_connect(read_only=False)
    try:
        ensure_tables(con)
        pairs = con.execute("""
            SELECT mi.region_id, mi.type_id
              FROM market_items mi
         LEFT JOIN (
                      SELECT type_id, region_id, MAX(date) AS last_date
                        FROM market_history
                    GROUP BY type_id, region_id
                  ) mh ON mh.type_id = mi.type_id AND mh.region_id = mi.region_id
             WHERE mh.last_date IS NULL OR mh.last_date < current_date
        """).fetchall()
    finally:
        con.close()

    total = len(pairs)
    logger.info("[market.history] Fetching history for %s type/region pairs...", total)
    fetched = 0
    for region_id, type_id in pairs:
        try:
            on_demand_history(type_id, region_id)
            fetched += 1
        except Exception:
            logger.exception("[market.history] Failed for type %s region %s", type_id, region_id)

    logger.info("[market.history] Done — %s/%s pairs fetched", fetched, total)


# ── Backward-compatible aliases ───────────────────────────────────────────────

fetch_all_market_data          = fetch_region_orders
update_structure_market_orders = fetch_structure_orders
fetch_market_history           = on_demand_history
