"""ESI fetchers for personal blueprint inventories."""

from __future__ import annotations

import logging
from typing import Iterable, List

import requests

from db.database import get_private_session
from db.models import Blueprint
from util.esi_rate_limiter import esi_get
from util.utils import get_token

logger = logging.getLogger(__name__)

ESI = "https://esi.evetech.net/latest"
DATASOURCE = {"datasource": "tranquility"}


# ──────── Fetching ─────────────────────────────────────────────────────────────

def fetch_blueprints(char_id: int, access_token: str) -> List[dict]:
    """Fetch blueprint inventory for a character.

    The ESI endpoint uses standard pagination semantics; iterate until the
    server stops returning additional pages.
    """

    url = f"{ESI}/characters/{char_id}/blueprints/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    page = 1
    payload: List[dict] = []
    while True:
        params = {**DATASOURCE, "page": page}
        response = esi_get(url, headers=headers, params=params)
        response.raise_for_status()

        batch = response.json() or []
        if not isinstance(batch, list):
            logger.warning(
                "[blueprints] Unexpected payload for %s (page %s): %s",
                char_id,
                page,
                batch,
            )
            break

        payload.extend(batch)

        total_pages = int(response.headers.get("x-pages", page))
        if page >= total_pages:
            break
        page += 1

    return payload


# ──────── Storage ───────────────────────────────────────────────────────────────

def _normalize_flag(raw_flag: object) -> str | None:
    """Ensure the blueprint location flag is serialisable."""

    if raw_flag is None:
        return None
    return str(raw_flag)


def store_blueprints(owner_id: int, char_id: int, entries: Iterable[dict]) -> None:
    """Persist blueprint entries for a character, replacing existing rows."""

    session = get_private_session(owner_id)
    try:
        session.query(Blueprint).filter_by(character_id=char_id).delete()

        for entry in entries:
            session.add(
                Blueprint(
                    item_id=entry.get("item_id"),
                    character_id=char_id,
                    type_id=entry.get("type_id"),
                    material_efficiency=entry.get("material_efficiency", 0),
                    time_efficiency=entry.get("time_efficiency", 0),
                    runs=entry.get("runs"),
                    quantity=entry.get("quantity", 1),
                    location_id=entry.get("location_id"),
                    location_flag=_normalize_flag(entry.get("location_flag")),
                )
            )

        session.commit()
        logger.info(
            "[blueprints] Stored %s blueprints for owner %s character %s",
            session.query(Blueprint).filter_by(character_id=char_id).count(),
            owner_id,
            char_id,
        )
    except Exception:
        session.rollback()
        logger.exception(
            "[blueprints] Failed storing blueprints for owner %s character %s",
            owner_id,
            char_id,
        )
        raise
    finally:
        session.close()


# ──────── Orchestrator ───────────────────────────────────────────────────────────

def fetch_all_blueprints(owner_id: int) -> None:
    """Fetch and persist blueprint inventories for all of an owner's characters."""

    tokens = get_token(owner_id)
    for char_id, token_row in tokens.items():
        logger.info("[blueprints] Fetching blueprints for %s", char_id)
        try:
            data = fetch_blueprints(char_id, token_row["access_token"])
            store_blueprints(owner_id, char_id, data)
            logger.info(
                "[blueprints] Stored %s entries for owner %s character %s",
                len(data),
                owner_id,
                char_id,
            )
        except requests.HTTPError as exc:
            logger.error(
                "[blueprints] HTTP error fetching blueprints for %s: %s",
                char_id,
                exc,
            )
        except Exception as exc:
            logger.error(
                "[blueprints] Unexpected error for %s: %s",
                char_id,
                exc,
            )
