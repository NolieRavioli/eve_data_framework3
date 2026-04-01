"""
esi/personal/loyalty.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Loyalty  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id_loyalty_points(character_id: int, token: str) -> dict | None:
    """Get loyalty points.
    Scopes: esi-characters.read_loyalty.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCharactersCharacterIdLoyaltyPoints', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdLoyaltyPoints', result['status_code'], result['url'])
    return None

