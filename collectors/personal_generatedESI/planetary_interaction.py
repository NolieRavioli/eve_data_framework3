"""
esi/personal/planetary_interaction.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Planetary Interaction  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id_planets(character_id: int, token: str) -> dict | None:
    """Get colonies.
    Scopes: esi-planets.manage_planets.v1.
    Cache: 600s.
    """
    result = execute_operation('GetCharactersCharacterIdPlanets', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdPlanets', result['status_code'], result['url'])
    return None


def get_characters_character_id_planets_planet_id(character_id: int, planet_id: int, token: str) -> dict | None:
    """Get colony layout.
    Scopes: esi-planets.manage_planets.v1.
    Cache: 600s.
    """
    result = execute_operation('GetCharactersCharacterIdPlanetsPlanetId', path_params={'character_id': character_id, 'planet_id': planet_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdPlanetsPlanetId', result['status_code'], result['url'])
    return None
