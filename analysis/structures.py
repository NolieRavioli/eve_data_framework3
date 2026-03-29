import logging
import os
import time
from datetime import datetime
from typing import Optional

import requests

from db.database import get_private_session
from db.models import Asset, IndustryJob
from util import sde_store
from util.esi_rate_limiter import esi_request
from util.sde import region_id_from_system_id
from util.utils import PRIVATE_DATA_FOLDER, batched, get_token

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"
DATASOURCE = {"datasource": "tranquility"}
INT32_MAX = 2_147_483_647
_system_name_cache = {}
STRUCTURE_ENRICH_LOG_EVERY = 25
STRUCTURE_ENRICH_FLUSH_SIZE = 50


def safe_request(method, url, max_retries=5, backoff_factor=2, suppress_forbidden_log=False, **kwargs):
    delay = 1
    for attempt in range(1, max_retries + 1):
        try:
            kwargs.setdefault("timeout", 30)
            resp = esi_request(method, url, **kwargs)
            if resp.status_code == 420:
                logger.warning("[RateLimit] 420 on %s, sleeping 7s (attempt %s)", url, attempt)
                time.sleep(7)
                continue
            if resp.status_code == 403:
                if not suppress_forbidden_log:
                    logger.warning("[Forbidden] 403 on %s, skipping.", url)
                return None
            if resp.status_code == 401:
                logger.warning("[Unauthorized] 401 on %s, skipping retries.", url)
                return None
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            logger.warning("[HTTP Error] %s on %s (attempt %s)", exc, url, attempt)
            if attempt == max_retries:
                logger.error("[FAILED] Max retries reached for %s", url)
                return None
            time.sleep(delay)
            delay *= backoff_factor
    return None


class _TokenExpired(Exception):
    """Raised when ESI returns 401 (token is invalid / has expired)."""


def fetch_structure_info(structure_id: int, token: str) -> Optional[dict]:
    """Return structure metadata dict, None if inaccessible, or raise _TokenExpired on 401."""
    url = f"{ESI_BASE}/universe/structures/{structure_id}/"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        resp = esi_request("GET", url, headers=headers, params=DATASOURCE, timeout=30)
    except Exception as exc:
        logger.warning("[StructInfo] Request failed for %s: %s", structure_id, exc)
        return None
    if resp.status_code == 401:
        raise _TokenExpired(f"401 on structure {structure_id}")
    if resp.status_code in (403, 404, 422):
        return None
    if not resp.ok:
        logger.warning("[StructInfo] HTTP %s for structure %s", resp.status_code, structure_id)
        return None
    try:
        return resp.json()
    except Exception as exc:
        logger.warning("[StructInfo] JSON parse failed for %s: %s", structure_id, exc)
        return None


def collect_structure_tokens(owner_ids: list[int]) -> list[dict]:
    token_candidates = []
    for owner_id in owner_ids:
        try:
            tokens = get_token(owner_id)
        except Exception as exc:
            logger.warning("[Enrich] Failed loading tokens for owner %s: %s", owner_id, exc)
            continue
        usable = 0
        for char_id, token_data in sorted(tokens.items()):
            access_token = token_data.get("access_token")
            if not access_token:
                continue
            token_candidates.append(
                {
                    "owner_id": owner_id,
                    "character_id": char_id,
                    "access_token": access_token,
                }
            )
            usable += 1
        if usable:
            logger.info("[Enrich] Owner %s contributed %s usable structure token(s)", owner_id, usable)
        else:
            logger.warning("[Enrich] No usable tokens for owner %s", owner_id)
    return token_candidates


def discover_private_structure_ids(owner_id: int) -> set[int]:
    ids = set()
    with get_private_session(owner_id) as session:
        for (loc,) in session.query(Asset.location_id).distinct():
            if loc and loc > INT32_MAX:
                ids.add(loc)
        for (loc,) in session.query(IndustryJob.facility_id).distinct():
            if loc and loc > INT32_MAX:
                ids.add(loc)
        for (loc,) in session.query(IndustryJob.output_location_id).distinct():
            if loc and loc > INT32_MAX:
                ids.add(loc)
    logger.info("[StructIDs] Owner %s private IDs: %s", owner_id, len(ids))
    return ids


def fetch_public_structures() -> set[int]:
    url = f"{ESI_BASE}/universe/structures/"
    resp = safe_request("GET", url, params=DATASOURCE, headers={"Accept": "application/json"})
    if not resp:
        return set()
    try:
        return set(resp.json())
    except Exception as exc:
        logger.error("[Discovery] Failed parsing public structures list: %s", exc)
        return set()


def fetch_owned_structures(owner_id: int) -> set[int]:
    structure_ids = set()
    _system_name_cache.clear()
    main_char_id = owner_id

    tokens = get_token(owner_id)
    token_data = tokens.get(main_char_id) or {}
    if token_data.get("expires_at", 0) < time.time():
        logger.info("[TokenRefresh] Expired for %s, refreshing...", main_char_id)
        tokens = get_token(owner_id)
        token_data = tokens.get(main_char_id) or {}
    access_token = token_data.get("access_token")
    if not access_token:
        logger.warning("[StructScan] No token for character %s", main_char_id)
        return structure_ids

    corp_id = token_data.get("corporation_id")
    alliance_id = token_data.get("alliance_id")
    logger.info(
        "[StructScan] Starting sov scan for char %s, corp %s, alliance %s",
        main_char_id,
        corp_id,
        alliance_id,
    )

    friendly_corp_ids = set()
    friendly_alliance_ids = set()

    if corp_id:
        resp = safe_request(
            "GET",
            f"{ESI_BASE}/corporations/{corp_id}/contacts/",
            headers={"Authorization": f"Bearer {access_token}"},
            params=DATASOURCE,
        )
        if resp:
            for contact in resp.json():
                if contact.get("standing", 0) > 0:
                    if contact["contact_type"] == "corporation":
                        friendly_corp_ids.add(contact["contact_id"])
                    elif contact["contact_type"] == "alliance":
                        friendly_alliance_ids.add(contact["contact_id"])

    if alliance_id:
        resp = safe_request(
            "GET",
            f"{ESI_BASE}/alliances/{alliance_id}/contacts/",
            headers={"Authorization": f"Bearer {access_token}"},
            params=DATASOURCE,
        )
        if resp:
            for contact in resp.json():
                if contact.get("standing", 0) > 0:
                    if contact["contact_type"] == "corporation":
                        friendly_corp_ids.add(contact["contact_id"])
                    elif contact["contact_type"] == "alliance":
                        friendly_alliance_ids.add(contact["contact_id"])

    if not friendly_corp_ids and corp_id:
        logger.info("[StructScan] No friendly corps; using own corp.")
        friendly_corp_ids.add(corp_id)
    if not friendly_alliance_ids and alliance_id:
        logger.info("[StructScan] No friendly alliances; using own alliance.")
        friendly_alliance_ids.add(alliance_id)

    sov_resp = safe_request("GET", f"{ESI_BASE}/sovereignty/map/", params=DATASOURCE)
    if not sov_resp:
        logger.error("[StructScan] Failed to fetch sovereignty map.")
        return structure_ids

    sov_map = sov_resp.json()
    sov_systems = {
        entry["system_id"]
        for entry in sov_map
        if entry.get("corporation_id") in friendly_corp_ids
        or entry.get("alliance_id") in friendly_alliance_ids
    }
    logger.info("[StructScan] Found %s friendly sov systems", len(sov_systems))

    for batch in batched(list(sov_systems), 1000):
        name_resp = safe_request(
            "POST",
            f"{ESI_BASE}/universe/names/",
            json=batch,
            headers={"Accept": "application/json"},
        )
        if name_resp:
            for entry in name_resp.json():
                if entry["category"] == "solar_system":
                    _system_name_cache[entry["id"]] = entry["name"]

    total = len(sov_systems)
    t0 = time.time()
    for idx, sid in enumerate(sov_systems, start=1):
        system_name = _system_name_cache.get(sid)
        if not system_name:
            continue

        search_resp = safe_request(
            "GET",
            f"{ESI_BASE}/characters/{main_char_id}/search/",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"categories": "structure", "search": f"{system_name} - ", "strict": "false"},
        )
        if search_resp:
            structure_ids.update(search_resp.json().get("structure", []))

        if idx % max(1, total // 500) == 0:
            elapsed = time.time() - t0
            eta = (elapsed / idx) * (total - idx)
            logger.info("[StructSearch] %.1f%% done. ETA %.1fs", 100 * idx / total, eta)

    logger.info("[StructScan] Found %s structures in friendly sov", len(structure_ids))
    return structure_ids


def discover_all_structures() -> list[int]:
    if not os.path.isdir(PRIVATE_DATA_FOLDER):
        owner_ids = []
    else:
        owner_ids = [
            int(directory)
            for directory in os.listdir(PRIVATE_DATA_FOLDER)
            if directory.isdigit() and int(directory) > 0 and os.path.isdir(os.path.join(PRIVATE_DATA_FOLDER, directory))
        ]
    logger.info("[Discovery] Found %s owners.", len(owner_ids))

    try:
        public_ids = fetch_public_structures()
        logger.info("[Discovery] Pulled %s public structures from /universe/structures/", len(public_ids))
    except Exception as exc:
        logger.error("[Discovery] Could not fetch public structures: %s", exc)
        public_ids = set()

    structure_ids = set(public_ids)

    for owner_id in owner_ids:
        try:
            pvt = discover_private_structure_ids(owner_id)
            sov = fetch_owned_structures(owner_id)
            structure_ids |= pvt | sov
        except Exception as exc:
            logger.warning("[Discovery] Skipped owner %s due to: %s", owner_id, exc)

    logger.info("[Discovery] Total unique structure IDs: %s", len(structure_ids))

    existing_ids = sde_store.list_public_structure_ids()
    new_ids = structure_ids - existing_ids
    added_count = sde_store.seed_structures(new_ids)
    logger.info(
        "[Discovery] %s new structures added to DB (%s already known).",
        added_count,
        len(existing_ids),
    )

    remaining_ids = sde_store.list_public_structure_ids(missing_name_only=True)
    logger.info(
        "[Enrich] %s structures need metadata enrichment via authenticated structure lookups.",
        len(remaining_ids),
    )

    token_candidates = collect_structure_tokens(owner_ids)
    enriched = []
    total = len(remaining_ids)
    count = 0
    t0 = time.time()
    pending_rows = []

    if total and not token_candidates:
        logger.warning("[Enrich] No usable tokens available for protected structure metadata enrichment.")

    if total and token_candidates:
        logger.info(
            "[Enrich] Starting pooled enrichment across %s structure IDs using %s token(s).",
            total,
            len(token_candidates),
        )

    active_tokens = list(token_candidates)  # shrinks as tokens expire

    for sid in list(sorted(remaining_ids)):
        if not active_tokens:
            break
        count += 1
        info = None
        expired_this_round = []
        for token_data in active_tokens:
            access_token = token_data.get("access_token")
            if not access_token:
                continue
            try:
                info = fetch_structure_info(sid, access_token)
            except _TokenExpired:
                expired_this_round.append(token_data)
                logger.warning(
                    "[Enrich] Token for char %s is expired/invalid — removing from pool (%d left)",
                    token_data.get("character_id"),
                    len(active_tokens) - len(expired_this_round),
                )
                continue
            if info:
                break

        for t in expired_this_round:
            active_tokens.remove(t)

        if not active_tokens:
            logger.warning(
                "[Enrich] All tokens expired at %s/%s — stopping enrichment early.",
                count, total,
            )
            break

        if info:
            solar_system_id = info.get("solar_system_id")
            region_id = region_id_from_system_id(solar_system_id) if solar_system_id else None
            pending_rows.append(
                {
                    "structure_id": sid,
                    "name": info.get("name"),
                    "solar_system_id": solar_system_id,
                    "region_id": region_id,
                    "owner_id": info.get("owner_id"),
                    "type_id": info.get("type_id"),
                    "last_seen": datetime.utcnow(),
                }
            )
            enriched.append(sid)

        if len(pending_rows) >= STRUCTURE_ENRICH_FLUSH_SIZE:
            sde_store.upsert_structures(pending_rows)
            pending_rows.clear()

        if count % STRUCTURE_ENRICH_LOG_EVERY == 0 or count == total:
            elapsed = time.time() - t0
            eta = (elapsed / count) * (total - count) if count else 0
            logger.info(
                "[Enrich] %s/%s (%.1f%%) ETA %.0fs enriched %s pending_writes %s",
                count,
                total,
                (100 * count / total) if total else 100.0,
                eta,
                len(enriched),
                len(pending_rows),
            )

    if pending_rows:
        sde_store.upsert_structures(pending_rows)

    if remaining_ids:
        patch_rows = []
        for structure in sde_store.list_public_structures():
            sid = structure["structure_id"]
            if sid in enriched:
                continue
            if structure.get("solar_system_id") and not structure.get("region_id"):
                patch_rows.append(
                    {
                        **structure,
                        "region_id": region_id_from_system_id(structure["solar_system_id"]),
                        "last_seen": datetime.utcnow(),
                    }
                )
        if patch_rows:
            sde_store.upsert_structures(patch_rows)

    logger.info("[Discovery] Enriched metadata for %s structures.", len(enriched))
    return enriched
