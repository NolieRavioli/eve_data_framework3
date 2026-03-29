"""
esi/public_api/alliance.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Alliance  |  Scope: public_api
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_alliances() -> dict | None:
    """List all alliances.
    Cache: 3600s.
    """
    result = execute_operation('GetAlliances', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetAlliances', result['status_code'], result['url'])
    return None


def get_alliances_alliance_id(alliance_id: int) -> dict | None:
    """Get alliance's public information.
    Cache: 3600s.
    """
    result = execute_operation('GetAlliancesAllianceId', path_params={'alliance_id': alliance_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetAlliancesAllianceId', result['status_code'], result['url'])
    return None


def get_alliances_alliance_id_corporations(alliance_id: int) -> dict | None:
    """List alliance's corporations.
    Cache: 3600s.
    """
    result = execute_operation('GetAlliancesAllianceIdCorporations', path_params={'alliance_id': alliance_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetAlliancesAllianceIdCorporations', result['status_code'], result['url'])
    return None


def get_alliances_alliance_id_icons(alliance_id: int) -> dict | None:
    """Get alliance icon.
    """
    result = execute_operation('GetAlliancesAllianceIdIcons', path_params={'alliance_id': alliance_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetAlliancesAllianceIdIcons', result['status_code'], result['url'])
    return None
