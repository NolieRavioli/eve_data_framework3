"""
esi/personal/assets.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Assets  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id_assets(character_id: int, token: str) -> list:
    """Get character assets.
    Scopes: esi-assets.read_assets.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCharactersCharacterIdAssets',
        path_params={'character_id': character_id},
        token=token,
    )


def post_characters_character_id_assets_locations(character_id: int, token: str) -> dict | None:
    """Get character asset locations.
    Scopes: esi-assets.read_assets.v1.
    """
    result = execute_operation('PostCharactersCharacterIdAssetsLocations', path_params={'character_id': character_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostCharactersCharacterIdAssetsLocations', result['status_code'], result['url'])
    return None


def post_characters_character_id_assets_names(character_id: int, token: str) -> dict | None:
    """Get character asset names.
    Scopes: esi-assets.read_assets.v1.
    """
    result = execute_operation('PostCharactersCharacterIdAssetsNames', path_params={'character_id': character_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostCharactersCharacterIdAssetsNames', result['status_code'], result['url'])
    return None

