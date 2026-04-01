"""
esi/personal/search.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Search  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id_search(character_id: int, token: str) -> dict | None:
    """Search on a string.
    Scopes: esi-search.search_structures.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCharactersCharacterIdSearch', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdSearch', result['status_code'], result['url'])
    return None
