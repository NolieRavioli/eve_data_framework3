"""analysis/asset_enrichment.py — Resolve asset names and positions for personal/corp assets.

Uses:
  POST /characters/{character_id}/assets/locations  → position_x/y/z
  POST /characters/{character_id}/assets/names      → custom name
  POST /corporations/{corporation_id}/assets/locations
  POST /corporations/{corporation_id}/assets/names

Requires esi-assets.read_assets.v1 for personal and esi-assets.read_corp_assets.v1 for corp.
Batch size: up to 1000 item_ids per POST per ESI spec.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from core.auth import pick_token, fresh_token
from core.io.entity_db import connect_entity
from core.esi import esi_post

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"
_BATCH = 1000


def _get_owner_ids() -> list[int]:
    private_root = Path(os.environ.get("EVE_PRIVATE_DATABASE_FOLDER", "_privateData"))
    return [int(d.name) for d in private_root.iterdir()
            if d.is_dir() and d.name.isdigit()]


def _enrich_assets_for_entity(entity_id: int, char_id: int, access_token: str,
                               url_base: str) -> None:
    """Enrich character_assets or corp_assets with names and positions."""
    con = connect_entity(entity_id)
    try:
        table = "character_assets" if "characters" in url_base else "corp_assets"
        try:
            rows = con.execute(
                f"SELECT item_id FROM {table} WHERE name IS NULL OR position_x IS NULL"
            ).fetchall()
        except Exception:
            return
        if not rows:
            return

        item_ids = [r[0] for r in rows]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Names
        for i in range(0, len(item_ids), _BATCH):
            batch = item_ids[i:i + _BATCH]
            resp = esi_post(f"{url_base}/names/", json=batch, headers=headers)
            if resp.ok:
                for item in resp.json():
                    con.execute(
                        f"UPDATE {table} SET name = ? WHERE item_id = ?",
                        [item.get("name"), item["item_id"]]
                    )

        # Locations
        for i in range(0, len(item_ids), _BATCH):
            batch = item_ids[i:i + _BATCH]
            resp = esi_post(f"{url_base}/locations/", json=batch, headers=headers)
            if resp.ok:
                for item in resp.json():
                    pos = item.get("position", {})
                    con.execute(
                        f"UPDATE {table} SET position_x=?, position_y=?, position_z=? "
                        f"WHERE item_id=?",
                        [pos.get("x"), pos.get("y"), pos.get("z"), item["item_id"]]
                    )
    finally:
        con.close()


def run_asset_enrichment() -> None:
    """Enrich asset names and positions for all owners."""
    owner_ids = _get_owner_ids()
    for owner_id in owner_ids:
        try:
            char_id, token_data = pick_token(owner_id)
            _, fresh_data = fresh_token(owner_id, char_id, token_data)
            token = fresh_data["access_token"]

            # Personal assets
            con = connect_entity(owner_id)
            try:
                char_id_rows = con.execute("SELECT DISTINCT character_id FROM character_assets").fetchall()
            finally:
                con.close()
            for (cid,) in char_id_rows:
                _enrich_assets_for_entity(
                    owner_id, char_id, token,
                    f"{ESI_BASE}/characters/{cid}/assets"
                )
        except Exception:
            logger.exception("[asset_enrichment] Failed for owner %s", owner_id)

    # Corp assets (needs corp-scoped token)
    from collectors.corp import get_corp_token_map
    token_map = get_corp_token_map()
    for corp_id, (char_id, access_token) in token_map.items():
        try:
            _enrich_assets_for_entity(
                corp_id, char_id, access_token,
                f"{ESI_BASE}/corporations/{corp_id}/assets"
            )
        except Exception:
            logger.exception("[asset_enrichment] Failed for corp %s", corp_id)

    logger.info("[asset_enrichment] Done")
