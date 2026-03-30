import logging
import time
from datetime import datetime
from typing import Optional

import requests

from util import sde_store
from util.esi_rate_limiter import esi_get
from util.sde import region_id_from_system_id
from util.utils import CONFIG_PATH, PRIVATE_DATA_FOLDER, get_token, load_config

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"
DATASOURCE = {"datasource": "tranquility"}

_STRUCTURE_INFO_CACHE: dict[int, tuple[float, dict]] = {}
_STRUCTURE_INFO_TTL = 24 * 3600

_MARKET_403 = object()  # sentinel: 403 on /markets/structures/{id}/


def _get_market_unauthorized_cooldown() -> int:
    try:
        cfg = load_config(CONFIG_PATH)
        days = int(cfg.get("Structures", {}).get("market_unauthorized_cooldown_days", 7))
    except Exception:
        days = 7
    return days * 24 * 3600


def _get_market_forbidden_cooldown() -> int:
    try:
        cfg = load_config(CONFIG_PATH)
        days = int(cfg.get("Structures", {}).get("market_forbidden_cooldown_days", 21))
    except Exception:
        days = 21
    return days * 24 * 3600


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
            resp = esi_get(url, headers=headers, params={**DATASOURCE, "page": page}, timeout=15)

            if resp.status_code == 403:
                logger.warning(
                    "[MarketFetch] Skipping %s page %s: HTTP 403",
                    structure_id,
                    page,
                )
                return _MARKET_403, 1

            if resp.status_code == 404:
                logger.warning(
                    "[MarketFetch] Skipping %s page %s: HTTP 404",
                    structure_id,
                    page,
                )
                return [], 1

            if resp.status_code == 420:
                logger.warning("[RateLimit] 420 returned for %s, sleeping 10s", structure_id)
                time.sleep(10)
                continue

            resp.raise_for_status()
            data = resp.json()
            pages = int(resp.headers.get("x-pages", 1))
            return data, pages

        except requests.exceptions.Timeout:
            logger.warning("[Timeout] Attempt %s/%s for structure %s page %s", attempt, retries, structure_id, page)
            time.sleep(3 * attempt)
        except Exception as exc:
            logger.warning(
                "[RetryError] Attempt %s/%s for structure %s page %s: %s",
                attempt,
                retries,
                structure_id,
                page,
                exc,
            )
            time.sleep(2 * attempt)

    logger.error("[MarketFetch] Failed after %s retries for structure %s page %s", retries, structure_id, page)
    return [], 1


def fetch_structure_details(structure_id: int, token: str) -> Optional[dict]:
    now = time.time()
    cached = _STRUCTURE_INFO_CACHE.get(structure_id)
    if cached and cached[0] > now:
        return cached[1]

    url = f"{ESI_BASE}/universe/structures/{structure_id}/"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    try:
        resp = esi_get(url, headers=headers, params=DATASOURCE, timeout=15)
    except Exception as exc:
        logger.warning("[StructMeta] Request failed for %s: %s", structure_id, exc)
        return None

    if resp.status_code in (403, 404):
        logger.debug("[StructMeta] Access denied for %s: HTTP %s", structure_id, resp.status_code)
        return None

    try:
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("[StructMeta] Failed to parse metadata for %s: %s", structure_id, exc)
        return None

    _STRUCTURE_INFO_CACHE[structure_id] = (now + _STRUCTURE_INFO_TTL, data)
    return data


def _pick_token(owner_id: int) -> tuple[int, dict]:
    tokens = get_token(owner_id)
    char_id, token_data = sorted(tokens.items())[0]
    if token_data.get("expires_at") and token_data["expires_at"] < time.time():
        logger.info("[TokenRefresh] Token expired for %s, refreshing...", char_id)
        tokens = get_token(owner_id)
        char_id, token_data = sorted(tokens.items())[0]
    return char_id, token_data


def _get_fresh_token(owner_id: int, char_id: int, token_data: dict) -> tuple[int, dict]:
    """Return current token if still valid; only call _pick_token (DB query) if expired."""
    expires_at = token_data.get("expires_at")
    if expires_at is not None and expires_at > time.time() + 30:
        return char_id, token_data
    return _pick_token(owner_id)


def _resolve_default_owner_id() -> int | None:
    import os
    from os.path import isdir, join

    if not os.path.isdir(PRIVATE_DATA_FOLDER):
        return None

    owner_ids = [
        int(name)
        for name in os.listdir(PRIVATE_DATA_FOLDER)
        if name.isdigit() and isdir(join(PRIVATE_DATA_FOLDER, name))
    ]
    return min(owner_ids) if owner_ids else None


def populate_structure_metadata(structure: dict, token: str) -> dict:
    updated = dict(structure)
    needs_lookup = not (
        updated.get("solar_system_id")
        and updated.get("name")
        and updated.get("type_id")
        and updated.get("owner_id")
    )
    if needs_lookup:
        info = fetch_structure_details(updated["structure_id"], token)
        if info:
            updated["name"] = info.get("name")
            updated["solar_system_id"] = info.get("solar_system_id")
            updated["owner_id"] = info.get("owner_id")
            updated["type_id"] = info.get("type_id")

    if updated.get("solar_system_id") and not updated.get("region_id"):
        updated["region_id"] = region_id_from_system_id(updated["solar_system_id"])

    updated["last_seen"] = datetime.utcnow()
    return updated


def update_structure_market_orders() -> None:
    owner_id = _resolve_default_owner_id()
    if owner_id is None:
        logger.error("[MarketUpdate] No private owner directories found.")
        return

    _char_id, token_data = _pick_token(owner_id)
    token = token_data["access_token"]
    structures = sde_store.list_public_structures(skip_market_forbidden=True)
    logger.info("[MarketUpdate] Checking %s structures.", len(structures))
    total = len(structures)
    skipped = 0
    unauthorized_ids: list[int] = []   # 403 on market endpoint
    orders_total = 0
    t0 = time.time()
    log_every = max(1, total // 20) if total else 1

    for count, structure in enumerate(structures, start=1):
        num_orders = 0
        structure_id = structure["structure_id"]
        try:
            _char_id, token_data = _get_fresh_token(owner_id, _char_id, token_data)
            token = token_data["access_token"]

            structure = populate_structure_metadata(structure, token)
            sde_store.upsert_structures([structure])
            sde_store.upsert_market_structures([structure])

            orders, pages = fetch_structure_orders(structure_id, token, page=1)
            if orders is _MARKET_403:
                unauthorized_ids.append(structure_id)
                skipped += 1
                if count % log_every == 0 or count == total:
                    elapsed = time.time() - t0
                    eta = (elapsed / count) * (total - count) if count else 0
                    logger.info(
                        "[Progress] %s/%s (%.1f%%) ETA %.0fs orders %s skipped %s",
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
                        "[Progress] %s/%s (%.1f%%) ETA %.0fs orders %s skipped %s",
                        count,
                        total,
                        (100 * count / total) if total else 100.0,
                        eta,
                        f"{orders_total:,}",
                        skipped,
                    )
                continue

            region_id = structure.get("region_id")
            all_rows = [{**order, "region_id": region_id, "location_id": structure_id} for order in orders]
            num_orders += len(all_rows)

            for page in range(2, pages + 1):
                _char_id, token_data = _get_fresh_token(owner_id, _char_id, token_data)
                token = token_data["access_token"]
                more, _ = fetch_structure_orders(structure_id, token, page=page)
                page_rows = [{**order, "region_id": region_id, "location_id": structure_id} for order in more]
                all_rows.extend(page_rows)
                num_orders += len(page_rows)

            sde_store.upsert_market_orders(all_rows)
            sde_store.mark_structures_market_refreshed([structure_id])
            orders_total += num_orders
            logger.debug("[MarketUpdate] Synced %s orders for %s.", num_orders, structure_id)

            if count % log_every == 0 or count == total:
                elapsed = time.time() - t0
                eta = (elapsed / count) * (total - count) if count else 0
                logger.info(
                    "[Progress] %s/%s (%.1f%%) ETA %.0fs orders %s skipped %s",
                    count,
                    total,
                    (100 * count / total) if total else 100.0,
                    eta,
                    f"{orders_total:,}",
                    skipped,
                )
        except Exception:
            logger.exception("[MarketUpdate] Failed for %s.", structure_id)

    if unauthorized_ids:
        cooldown = _get_market_unauthorized_cooldown()
        sde_store.mark_market_structures_forbidden(unauthorized_ids, cooldown)
        logger.info(
            "[MarketUpdate] Marked %s structure(s) as 403-inaccessible on market; will skip for %s days.",
            len(unauthorized_ids),
            cooldown // 86400,
        )


def update_structure_market(owner_id: int) -> None:
    logger.warning(
        "[Compat] update_structure_market(owner_id=%s) is deprecated, using update_structure_market_orders().",
        owner_id,
    )
    update_structure_market_orders()


def fetch_all_structure_markets() -> None:
    logger.warning(
        "[Compat] fetch_all_structure_markets() is deprecated, using update_structure_market_orders()."
    )
    update_structure_market_orders()
