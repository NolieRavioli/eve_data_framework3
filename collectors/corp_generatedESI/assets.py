"""
esi/corp/assets.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Assets  |  Scope: corp
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_corporations_corporation_id_assets(corporation_id: int, token: str) -> list:
    """Get corporation assets.
    Scopes: esi-assets.read_corporation_assets.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdAssets',
        path_params={'corporation_id': corporation_id},
        token=token,
    )


def post_corporations_corporation_id_assets_locations(corporation_id: int, token: str) -> dict | None:
    """Get corporation asset locations.
    Scopes: esi-assets.read_corporation_assets.v1.
    """
    result = execute_operation('PostCorporationsCorporationIdAssetsLocations', path_params={'corporation_id': corporation_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostCorporationsCorporationIdAssetsLocations', result['status_code'], result['url'])
    return None


def post_corporations_corporation_id_assets_names(corporation_id: int, token: str) -> dict | None:
    """Get corporation asset names.
    Scopes: esi-assets.read_corporation_assets.v1.
    """
    result = execute_operation('PostCorporationsCorporationIdAssetsNames', path_params={'corporation_id': corporation_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostCorporationsCorporationIdAssetsNames', result['status_code'], result['url'])
    return None
