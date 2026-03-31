"""Discover and enrich all public player-owned structures.

Phase 1 — Seed
    Pull the full list of public structure IDs from ESI (no auth required).
    Any IDs not already in the structures table are inserted as bare rows so
    that the market-structure worker can start fetching market data immediately.

Phase 2 — Enrich
    For structures where name IS NULL (and not inside an enrich cooldown window),
    fetch full metadata using an authenticated character token.  Cooldowns are
    applied per-structure based on the ESI outcome:

      success       → enrich_authorized_cooldown_seconds
      403           → enrich_unauthorized_cooldown_days  × 86400
      404           → enrich_forbidden_cooldown_days     × 86400
      network error → no cooldown (retry next run)

Cooldown values are read from the ``Structures:`` section of config.yaml.
"""

import logging
import time
from datetime import datetime

import workers as _w
from db import sde_store
from esi.rate_limiter import esi_get
from sde import region_id_from_system_id
from config import CONFIG_PATH, load_config

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"
DATASOURCE = {"datasource": "tranquility"}


# ── config helpers ────────────────────────────────────────────────────────────

def _cfg_enrich_unauthorized_cooldown() -> int:
    try:
        cfg = load_config(CONFIG_PATH)
        days = int(cfg.get("Structures", {}).get("enrich_unauthorized_cooldown_days", 7))
    except Exception:
        days = 7
    return days * 24 * 3600


def _cfg_enrich_forbidden_cooldown() -> int:
    try:
        cfg = load_config(CONFIG_PATH)
        days = int(cfg.get("Structures", {}).get("enrich_forbidden_cooldown_days", 21))
    except Exception:
        days = 21
    return days * 24 * 3600


def _cfg_enrich_authorized_cooldown() -> int:
    try:
        cfg = load_config(CONFIG_PATH)
        return int(cfg.get("Structures", {}).get("enrich_authorized_cooldown_seconds", 3600))
    except Exception:
        return 3600


# ── ESI calls ─────────────────────────────────────────────────────────────────

def _fetch_public_structure_ids() -> list[int]:
    """Return all public structure IDs from ESI.  Returns [] on failure."""
    url = f"{ESI_BASE}/universe/structures/"
    try:
        resp = esi_get(url, params=DATASOURCE)
        if resp.ok:
            return [int(x) for x in resp.json()]
        logger.warning("[DiscoverStructures] /universe/structures/ returned %s", resp.status_code)
    except Exception as exc:
        logger.warning("[DiscoverStructures] Failed to fetch structure list: %s", exc)
    return []


def _fetch_structure_details(structure_id: int, token: str) -> tuple[dict | None, str]:
    """Fetch structure metadata for one ID using an authenticated token.

    Returns ``(data, status)`` where *status* is one of:
    ``"success"`` | ``"unauthorized"`` (403) | ``"forbidden"`` (404) | ``"error"``.
    """
    url = f"{ESI_BASE}/universe/structures/{structure_id}/"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        resp = esi_get(url, headers=headers, params=DATASOURCE, timeout=15)
    except Exception as exc:
        logger.warning("[DiscoverStructures] Request error for %s: %s", structure_id, exc)
        return None, "error"
    if resp.status_code == 403:
        return None, "unauthorized"
    if resp.status_code == 404:
        return None, "forbidden"
    try:
        resp.raise_for_status()
        return resp.json(), "success"
    except Exception as exc:
        logger.warning("[DiscoverStructures] Parse error for %s: %s", structure_id, exc)
        return None, "error"


# ── main worker ───────────────────────────────────────────────────────────────

def discover_structures(owner_id: int | None = None) -> None:
    """Discover public structures and enrich them with metadata.

    *owner_id* is the character whose token is used for Phase 2 enrichment.
    If omitted, the first available owner in the private data folder is used.

    Intended to be enqueued via::

        from tasks.task_queue import enqueue
        from workers.publicData.DiscoverStructures import discover_structures
        enqueue("Discover Structures", discover_structures, owner_id=owner_id, queue="public")
    """
    if owner_id is None:
        owner_id = _w.resolve_default_owner_id()
    if owner_id is None:
        logger.error("[DiscoverStructures] No owner available for authentication; aborting.")
        return

    # ── Phase 1: seed ─────────────────────────────────────────────────────────
    logger.info("[DiscoverStructures] Fetching public structure list from ESI...")
    esi_ids = set(_fetch_public_structure_ids())
    if not esi_ids:
        logger.warning("[DiscoverStructures] Received empty structure list from ESI; aborting.")
        return

    known_ids = sde_store.list_public_structure_ids()
    new_ids = esi_ids - known_ids
    logger.info(
        "[DiscoverStructures] ESI total: %s  |  already known: %s  |  new: %s",
        len(esi_ids), len(known_ids), len(new_ids),
    )

    if new_ids:
        bare_rows = [{"structure_id": sid} for sid in new_ids]
        inserted = sde_store.upsert_structures(bare_rows)
        logger.info("[DiscoverStructures] Inserted %s new bare structure rows.", inserted)

    # ── Phase 2: enrich ───────────────────────────────────────────────────────
    needs_enrichment = sde_store.list_public_structure_ids(missing_name_only=True)
    total = len(needs_enrichment)
    logger.info("[DiscoverStructures] %s structure(s) need enrichment.", total)
    if not total:
        logger.info("[DiscoverStructures] Nothing left to enrich; done.")
        return

    _char_id, token_data = _w.pick_token(owner_id)
    token = token_data["access_token"]

    succeeded = failed_403 = failed_404 = errors = 0
    log_every = max(1, total // 20)
    t0 = time.time()

    for count, structure_id in enumerate(sorted(needs_enrichment), start=1):
        try:
            _char_id, token_data = _w.fresh_token(owner_id, _char_id, token_data)
            token = token_data["access_token"]

            data, status = _fetch_structure_details(structure_id, token)

            if status == "success":
                row: dict = {
                    "structure_id": structure_id,
                    "name": data.get("name"),
                    "solar_system_id": data.get("solar_system_id"),
                    "owner_id": data.get("owner_id"),
                    "type_id": data.get("type_id"),
                    "last_seen": datetime.utcnow(),
                }
                if row.get("solar_system_id"):
                    row["region_id"] = region_id_from_system_id(row["solar_system_id"])
                sde_store.upsert_structures([row])
                sde_store.mark_structures_enrich_refreshed(
                    [structure_id], _cfg_enrich_authorized_cooldown()
                )
                succeeded += 1

            elif status == "unauthorized":
                sde_store.mark_structures_forbidden(
                    [structure_id], _cfg_enrich_unauthorized_cooldown()
                )
                failed_403 += 1

            elif status == "forbidden":
                sde_store.mark_structures_forbidden(
                    [structure_id], _cfg_enrich_forbidden_cooldown()
                )
                failed_404 += 1

            else:  # "error" — no cooldown, retry next run
                errors += 1

        except Exception:
            logger.exception("[DiscoverStructures] Unexpected error for structure %s.", structure_id)
            errors += 1

        if count % log_every == 0 or count == total:
            elapsed = time.time() - t0
            eta = (elapsed / count) * (total - count) if count else 0
            logger.info(
                "[Progress] %s/%s (%.1f%%) ETA %.0fs  ok=%s  403=%s  404=%s  err=%s",
                count, total, (100 * count / total) if total else 100.0,
                eta, succeeded, failed_403, failed_404, errors,
            )

    logger.info(
        "[DiscoverStructures] Done.  enriched=%s  403=%s  404=%s  errors=%s",
        succeeded, failed_403, failed_404, errors,
    )
