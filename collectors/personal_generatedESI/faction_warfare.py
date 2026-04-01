"""
esi/personal/faction_warfare.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Faction Warfare  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id_fw_stats(character_id: int, token: str) -> dict | None:
    """Overview of a character involved in faction warfare.
    Scopes: esi-characters.read_fw_stats.v1.
    """
    result = execute_operation('GetCharactersCharacterIdFwStats', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdFwStats', result['status_code'], result['url'])
    return None

