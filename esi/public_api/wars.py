"""
esi/public_api/wars.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Wars  |  Scope: public_api
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_wars() -> dict | None:
    """List wars.
    Cache: 3600s.
    """
    result = execute_operation('GetWars', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetWars', result['status_code'], result['url'])
    return None


def get_wars_war_id(war_id: int) -> dict | None:
    """Get war information.
    Cache: 3600s.
    """
    result = execute_operation('GetWarsWarId', path_params={'war_id': war_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetWarsWarId', result['status_code'], result['url'])
    return None


def get_wars_war_id_killmails(war_id: int) -> list:
    """List kills for a war.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetWarsWarIdKillmails',
        path_params={'war_id': war_id},
        token=None,
    )
