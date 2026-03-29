"""
esi/public_api/faction_warfare.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Faction Warfare  |  Scope: public_api
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_fw_leaderboards() -> dict | None:
    """List of the top factions in faction warfare.
    """
    result = execute_operation('GetFwLeaderboards', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetFwLeaderboards', result['status_code'], result['url'])
    return None


def get_fw_leaderboards_characters() -> dict | None:
    """List of the top pilots in faction warfare.
    """
    result = execute_operation('GetFwLeaderboardsCharacters', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetFwLeaderboardsCharacters', result['status_code'], result['url'])
    return None


def get_fw_leaderboards_corporations() -> dict | None:
    """List of the top corporations in faction warfare.
    """
    result = execute_operation('GetFwLeaderboardsCorporations', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetFwLeaderboardsCorporations', result['status_code'], result['url'])
    return None


def get_fw_stats() -> dict | None:
    """An overview of statistics about factions involved in faction warfare.
    """
    result = execute_operation('GetFwStats', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetFwStats', result['status_code'], result['url'])
    return None


def get_fw_systems() -> dict | None:
    """Ownership of faction warfare systems.
    Cache: 1800s.
    """
    result = execute_operation('GetFwSystems', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetFwSystems', result['status_code'], result['url'])
    return None


def get_fw_wars() -> dict | None:
    """Data about which NPC factions are at war.
    """
    result = execute_operation('GetFwWars', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetFwWars', result['status_code'], result['url'])
    return None
