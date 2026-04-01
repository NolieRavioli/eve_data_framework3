"""
esi/personal/fittings.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Fittings  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id_fittings(character_id: int, token: str) -> dict | None:
    """Get fittings.
    Scopes: esi-fittings.read_fittings.v1.
    Cache: 300s.
    """
    result = execute_operation('GetCharactersCharacterIdFittings', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdFittings', result['status_code'], result['url'])
    return None


def post_characters_character_id_fittings(character_id: int, token: str) -> dict | None:
    """Create fitting.
    Scopes: esi-fittings.write_fittings.v1.
    """
    result = execute_operation('PostCharactersCharacterIdFittings', path_params={'character_id': character_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostCharactersCharacterIdFittings', result['status_code'], result['url'])
    return None


def delete_characters_character_id_fittings_fitting_id(character_id: int, fitting_id: int, token: str) -> dict | None:
    """Delete fitting.
    Scopes: esi-fittings.write_fittings.v1.
    """
    result = execute_operation('DeleteCharactersCharacterIdFittingsFittingId', path_params={'character_id': character_id, 'fitting_id': fitting_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'DeleteCharactersCharacterIdFittingsFittingId', result['status_code'], result['url'])
    return None

