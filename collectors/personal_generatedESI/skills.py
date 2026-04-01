"""
esi/personal/skills.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Skills  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id_attributes(character_id: int, token: str) -> dict | None:
    """Get character attributes.
    Scopes: esi-skills.read_skills.v1.
    Cache: 120s.
    """
    result = execute_operation('GetCharactersCharacterIdAttributes', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdAttributes', result['status_code'], result['url'])
    return None


def get_characters_character_id_skillqueue(character_id: int, token: str) -> dict | None:
    """Get character's skill queue.
    Scopes: esi-skills.read_skillqueue.v1.
    Cache: 60s.
    """
    result = execute_operation('GetCharactersCharacterIdSkillqueue', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdSkillqueue', result['status_code'], result['url'])
    return None


def get_characters_character_id_skills(character_id: int, token: str) -> dict | None:
    """Get character skills.
    Scopes: esi-skills.read_skills.v1.
    Cache: 60s.
    """
    result = execute_operation('GetCharactersCharacterIdSkills', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdSkills', result['status_code'], result['url'])
    return None
