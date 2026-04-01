"""
esi/personal/clones.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Clones  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id_clones(character_id: int, token: str) -> dict | None:
    """Get clones.
    Scopes: esi-clones.read_clones.v1.
    Cache: 120s.
    """
    result = execute_operation('GetCharactersCharacterIdClones', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdClones', result['status_code'], result['url'])
    return None


def get_characters_character_id_implants(character_id: int, token: str) -> dict | None:
    """Get active implants.
    Scopes: esi-clones.read_implants.v1.
    Cache: 120s.
    """
    result = execute_operation('GetCharactersCharacterIdImplants', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdImplants', result['status_code'], result['url'])
    return None
