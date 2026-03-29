"""
esi/personal/location.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Location  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id_location(character_id: int, token: str) -> dict | None:
    """Get character location.
    Scopes: esi-location.read_location.v1.
    Cache: 5s.
    """
    result = execute_operation('GetCharactersCharacterIdLocation', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdLocation', result['status_code'], result['url'])
    return None


def get_characters_character_id_online(character_id: int, token: str) -> dict | None:
    """Get character online.
    Scopes: esi-location.read_online.v1.
    Cache: 60s.
    """
    result = execute_operation('GetCharactersCharacterIdOnline', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdOnline', result['status_code'], result['url'])
    return None


def get_characters_character_id_ship(character_id: int, token: str) -> dict | None:
    """Get current ship.
    Scopes: esi-location.read_ship_type.v1.
    Cache: 5s.
    """
    result = execute_operation('GetCharactersCharacterIdShip', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdShip', result['status_code'], result['url'])
    return None
