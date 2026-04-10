"""collectors/public_data/structures.py — Discover and enrich public player structures.

Migrated from collectors/structures/discover.py (Phase 5 — no schema changes).
The old module re-exports from here for backward compatibility.

**Table ownership:**

- ``structures`` — owned by this module via :func:`ensure_tables`
"""

import logging
import time
from datetime import datetime

from core.io.public import connect as public_connect
from core.io import public as sde_store
from core.esi import esi_get as _esi_get
import core.io.sde as sde
from core.auth import resolve_default_owner_id, pick_token, fresh_token
from core.config import get_structures_config

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"
DATASOURCE = {"datasource": "tranquility"}


# ── Table DDL ─────────────────────────────────────────────────────────────────

def ensure_tables(con) -> None:
    """Idempotent DDL for the structures table."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS structures (
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


def ensure_columns(con) -> None:
    """Add enrichment cooldown columns to the structures table."""
    con.execute("ALTER TABLE structures ADD COLUMN IF NOT EXISTS forbidden_until TIMESTAMP")
    con.execute("ALTER TABLE structures ADD COLUMN IF NOT EXISTS enrich_refreshed_until TIMESTAMP")


# ── ESI calls ─────────────────────────────────────────────────────────────────

def _fetch_public_structure_ids() -> list[int]:
    url = f"{ESI_BASE}/universe/structures/"
    try:
        resp = _esi_get(url, params=DATASOURCE)
        if resp.ok:
            return [int(x) for x in resp.json()]
        logger.warning("[DiscoverStructures] /universe/structures/ returned %s", resp.status_code)
    except Exception as exc:
        logger.warning("[DiscoverStructures] Failed to fetch structure list: %s", exc)
    return []


def _fetch_structure_details(structure_id: int, token: str) -> tuple[dict | None, str]:
    url = f"{ESI_BASE}/universe/structures/{structure_id}/"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        resp = _esi_get(url, headers=headers, params=DATASOURCE, timeout=15)
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

    Phase 1: seed bare rows for newly discovered structure IDs.
    Phase 2: enrich unenriched rows with ESI metadata (authenticated).
    """
    if owner_id is None:
        owner_id = resolve_default_owner_id()
    if owner_id is None:
        logger.error("[DiscoverStructures] No owner available for authentication; aborting.")
        return

    _sc = get_structures_config()
    enrich_unauthorized_cooldown = int(_sc.get("unauthorized_cooldown_days", 7)) * 86400
    enrich_forbidden_cooldown    = int(_sc.get("forbidden_cooldown_days", 21)) * 86400
    enrich_authorized_cooldown   = int(_sc.get("authorized_cooldown_seconds", 3600))

    con = public_connect(read_only=False)
    try:
        ensure_tables(con)
        ensure_columns(con)
    finally:
        con.close()

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

    needs_enrichment = sde_store.list_public_structure_ids(missing_name_only=True)
    total = len(needs_enrichment)
    logger.info("[DiscoverStructures] %s structure(s) need enrichment.", total)
    if not total:
        logger.info("[DiscoverStructures] Nothing left to enrich; done.")
        return

    _char_id, token_data = pick_token(owner_id)
    token = token_data["access_token"]

    succeeded = failed_403 = failed_404 = errors = 0
    log_every = max(1, total // 20)
    t0 = time.time()

    for count, structure_id in enumerate(sorted(needs_enrichment), start=1):
        try:
            _char_id, token_data = fresh_token(owner_id, _char_id, token_data)
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
                    row["region_id"] = sde.region_id_from_system_id(row["solar_system_id"])
                sde_store.upsert_structures([row])
                sde_store.mark_structures_enrich_refreshed(
                    [structure_id], enrich_authorized_cooldown
                )
                succeeded += 1

            elif status == "unauthorized":
                sde_store.mark_structures_forbidden([structure_id], enrich_unauthorized_cooldown)
                failed_403 += 1

            elif status == "forbidden":
                sde_store.mark_structures_forbidden([structure_id], enrich_forbidden_cooldown)
                failed_404 += 1

            else:
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
