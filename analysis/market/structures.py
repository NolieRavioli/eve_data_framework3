"""Fetch player-structure market orders from ESI and write them to the public DuckDB.

Structures are enriched with metadata (name, solar system, owner, type) before
market orders are fetched.  Cooldowns are applied per-structure based on the
ESI response code so stale or inaccessible structures are skipped on future runs.

**Table ownership:**

- ``market_structures`` — owned by this collector via :func:`ensure_tables`
- ``structures`` cooldown columns — enrichment via :func:`ensure_columns`
  (cross-calls :func:`analysis.structures.discover.ensure_tables`)
"""

import logging
import time
from datetime import datetime

import requests

from core.db.publicDB import connect as public_connect
from core.db import publicDB as sde_store
from core.queue.esi_req import esi_get as _esi_get
import core.sde as sde
from core.esi.auth import resolve_default_owner_id, pick_token, fresh_token
from core.config import CONFIG_PATH, load_config

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"
DATASOURCE = {"datasource": "tranquility"}

_STRUCTURE_INFO_CACHE: dict[int, tuple[float, dict]] = {}
_STRUCTURE_INFO_TTL = 24 * 3600

_MARKET_403 = object()  # sentinel: 403 on /markets/structures/{id}/
_MARKET_404 = object()  # sentinel: 404 on /markets/structures/{id}/
_ENRICH_403 = object()  # sentinel: 403 on /universe/structures/{id}/
_ENRICH_404 = object()  # sentinel: 404 on /universe/structures/{id}/


# ── Table DDL — this collector OWNS market_structures ─────────────────────────

def ensure_tables(con) -> None:
    """Idempotent DDL for the market_structures table."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS market_structures (
            structure_id BIGINT PRIMARY KEY,
            solar_system_id BIGINT,
            region_id BIGINT,
            owner_id BIGINT,
            name VARCHAR,
            type_id BIGINT,
            position_json VARCHAR,
            last_seen TIMESTAMP
        )
    """)


def ensure_columns(con) -> None:
    """Add cooldown columns to the structures table (enrichment pattern).

    Cross-calls :func:`analysis.structures.discover.ensure_tables`
    first to guarantee the base table exists.
    """
    from analysis.structures.discover import ensure_tables as _ensure_structures
    _ensure_structures(con)

    con.execute("ALTER TABLE structures ADD COLUMN IF NOT EXISTS market_forbidden_until TIMESTAMP")
    con.execute("ALTER TABLE structures ADD COLUMN IF NOT EXISTS market_refreshed_until TIMESTAMP")


# ── ESI calls ─────────────────────────────────────────────────────────────────

def fetch_structure_orders(
    structure_id: int,
    token: str,
    page: int = 1,
    retries: int = 3,
) -> tuple[list, int]:
    url = f"{ESI_BASE}/markets/structures/{structure_id}/"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    for attempt in range(1, retries + 1):
        try:
            resp = _esi_get(url, headers=headers, params={**DATASOURCE, "page": page}, timeout=15)

            if resp.status_code == 403:
                logger.warning("[MarketStructure] Skipping %s page %s: HTTP 403", structure_id, page)
                return _MARKET_403, 1

            if resp.status_code == 404:
                logger.warning("[MarketStructure] Skipping %s page %s: HTTP 404", structure_id, page)
                return _MARKET_404, 1

            if resp.status_code == 420:
                logger.warning("[MarketStructure] 420 rate limit for %s, retrying", structure_id)
                continue

            resp.raise_for_status()
            data = resp.json()
            pages = int(resp.headers.get("x-pages", 1))
            return data, pages

        except requests.exceptions.Timeout:
            logger.warning(
                "[MarketStructure] Timeout attempt %s/%s for structure %s page %s",
                attempt, retries, structure_id, page,
            )
        except Exception as exc:
            logger.warning(
                "[MarketStructure] Retry %s/%s for structure %s page %s: %s",
                attempt, retries, structure_id, page, exc,
            )

    logger.error("[MarketStructure] Failed after %s retries for structure %s page %s", retries, structure_id, page)
    return [], 1


def fetch_structure_details(structure_id: int, token: str) -> "dict | object | None":
    now = time.time()
    cached = _STRUCTURE_INFO_CACHE.get(structure_id)
    if cached and cached[0] > now:
        return cached[1]

    url = f"{ESI_BASE}/universe/structures/{structure_id}/"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    try:
        resp = _esi_get(url, headers=headers, params=DATASOURCE, timeout=15)
    except Exception as exc:
        logger.warning("[MarketStructure] Metadata request failed for %s: %s", structure_id, exc)
        return None

    if resp.status_code in (403, 404):
        logger.debug("[MarketStructure] Access denied for %s: HTTP %s", structure_id, resp.status_code)
        return _ENRICH_403 if resp.status_code == 403 else _ENRICH_404

    try:
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("[MarketStructure] Failed to parse metadata for %s: %s", structure_id, exc)
        return None

    _STRUCTURE_INFO_CACHE[structure_id] = (now + _STRUCTURE_INFO_TTL, data)
    return data


def populate_structure_metadata(structure: dict, token: str) -> tuple[dict, str]:
    """Try to enrich structure with ESI metadata.

    Returns a (dict, status) tuple where status is one of:
    - "success"      — ESI returned data and fields were updated
    - "skipped"      — all fields already present; no ESI call made
    - "unauthorized" — ESI returned 403
    - "forbidden"    — ESI returned 404
    - "error"        — network or parse failure
    """
    updated = dict(structure)
    needs_lookup = not (
        updated.get("solar_system_id")
        and updated.get("name")
        and updated.get("type_id")
        and updated.get("owner_id")
    )
    if needs_lookup:
        info = fetch_structure_details(updated["structure_id"], token)
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


# ── main worker ───────────────────────────────────────────────────────────────

def update_structure_market_orders() -> None:
    # Load config once for this run
    try:
        _raw_cfg = load_config(CONFIG_PATH)
    except Exception:
        _raw_cfg = {}
    _mc = _raw_cfg.get("Market", {})
    _sc = _raw_cfg.get("Structures", {})
    market_unauthorized_cooldown = int(_mc.get("unauthorized_cooldown_days", 7)) * 86400
    market_forbidden_cooldown    = int(_mc.get("forbidden_cooldown_days", 21)) * 86400
    market_authorized_cooldown   = int(_mc.get("authorized_cooldown_seconds", 3600))
    enrich_unauthorized_cooldown = int(_sc.get("unauthorized_cooldown_days", 7)) * 86400
    enrich_forbidden_cooldown    = int(_sc.get("forbidden_cooldown_days", 21)) * 86400
    enrich_authorized_cooldown   = int(_sc.get("authorized_cooldown_seconds", 3600))
    max_retries                  = int(_mc.get("max_retries", 3))

    # Ensure our tables + enrichment columns exist
    con = public_connect(read_only=False)
    try:
        ensure_tables(con)
        ensure_columns(con)
    finally:
        con.close()

    # Also ensure market_orders table from regions exists
    from analysis.market.regions import ensure_tables as _ensure_market
    con = public_connect(read_only=False)
    try:
        _ensure_market(con)
    finally:
        con.close()

    owner_id = resolve_default_owner_id()
    if owner_id is None:
        logger.error("[MarketStructure] No private owner directories found.")
        return

    _char_id, token_data = pick_token(owner_id)
    token = token_data["access_token"]
    structures = sde_store.list_public_structures(skip_market_forbidden=True)
    logger.info("[MarketStructure] Checking %s structures.", len(structures))
    total = len(structures)
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

            structure, enrich_status = populate_structure_metadata(structure, token)
            sde_store.upsert_structures([structure])
            sde_store.upsert_market_structures([structure])

            if enrich_status == "success":
                sde_store.mark_structures_enrich_refreshed([structure_id], enrich_authorized_cooldown)
            elif enrich_status == "unauthorized":
                sde_store.mark_structures_forbidden([structure_id], enrich_unauthorized_cooldown)
            elif enrich_status == "forbidden":
                sde_store.mark_structures_forbidden([structure_id], enrich_forbidden_cooldown)

            orders, pages = fetch_structure_orders(
                structure_id, token, page=1,
                retries=max_retries,
            )
            if orders is _MARKET_403:
                market_unauthorized_ids.append(structure_id)
                skipped += 1
                if count % log_every == 0 or count == total:
                    elapsed = time.time() - t0
                    eta = (elapsed / count) * (total - count) if count else 0
                    logger.info(
                        "[MarketStructure] %s/%s (%.1f%%) ETA %.0fs orders %s skipped %s",
                        count, total, (100 * count / total) if total else 100.0,
                        eta, f"{orders_total:,}", skipped,
                    )
                continue
            if orders is _MARKET_404:
                market_forbidden_ids.append(structure_id)
                skipped += 1
                if count % log_every == 0 or count == total:
                    elapsed = time.time() - t0
                    eta = (elapsed / count) * (total - count) if count else 0
                    logger.info(
                        "[MarketStructure] %s/%s (%.1f%%) ETA %.0fs orders %s skipped %s",
                        count, total, (100 * count / total) if total else 100.0,
                        eta, f"{orders_total:,}", skipped,
                    )
                continue
            if not orders:
                skipped += 1
                if count % log_every == 0 or count == total:
                    elapsed = time.time() - t0
                    eta = (elapsed / count) * (total - count) if count else 0
                    logger.info(
                        "[MarketStructure] %s/%s (%.1f%%) ETA %.0fs orders %s skipped %s",
                        count, total, (100 * count / total) if total else 100.0,
                        eta, f"{orders_total:,}", skipped,
                    )
                continue

            region_id = structure.get("region_id")
            all_rows = [{**order, "region_id": region_id, "location_id": structure_id} for order in orders]
            num_orders += len(all_rows)

            for page in range(2, pages + 1):
                _char_id, token_data = fresh_token(owner_id, _char_id, token_data)
                token = token_data["access_token"]
                more, _ = fetch_structure_orders(
                    structure_id, token, page=page,
                    retries=max_retries,
                )
                page_rows = [{**order, "region_id": region_id, "location_id": structure_id} for order in more]
                all_rows.extend(page_rows)
                num_orders += len(page_rows)

            sde_store.upsert_market_orders(all_rows)
            sde_store.mark_structures_market_refreshed([structure_id], market_authorized_cooldown)
            orders_total += num_orders
            logger.debug("[MarketStructure] Synced %s orders for %s.", num_orders, structure_id)

            if count % log_every == 0 or count == total:
                elapsed = time.time() - t0
                eta = (elapsed / count) * (total - count) if count else 0
                logger.info(
                    "[MarketStructure] %s/%s (%.1f%%) ETA %.0fs orders %s skipped %s",
                    count, total, (100 * count / total) if total else 100.0,
                    eta, f"{orders_total:,}", skipped,
                )
        except Exception:
            logger.exception("[MarketStructure] Failed for %s.", structure_id)

    if market_unauthorized_ids:
        cooldown = market_unauthorized_cooldown
        sde_store.mark_market_structures_forbidden(market_unauthorized_ids, cooldown)
        logger.info(
            "[MarketStructure] Marked %s structure(s) as market-403; will skip for %s days.",
            len(market_unauthorized_ids), cooldown // 86400,
        )

    if market_forbidden_ids:
        cooldown = market_forbidden_cooldown
        sde_store.mark_market_structures_forbidden(market_forbidden_ids, cooldown)
        logger.info(
            "[MarketStructure] Marked %s structure(s) as market-404; will skip for %s days.",
            len(market_forbidden_ids), cooldown // 86400,
        )

