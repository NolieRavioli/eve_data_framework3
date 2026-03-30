"""
esi/personal/character.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Character  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.client.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id(character_id: int) -> dict | None:
    """Get character's public information.
    Cache: 86400s.
    """
    result = execute_operation('GetCharactersCharacterId', path_params={'character_id': character_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterId', result['status_code'], result['url'])
    return None


def get_characters_character_id_agents_research(character_id: int, token: str) -> dict | None:
    """Get agents research.
    Scopes: esi-characters.read_agents_research.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCharactersCharacterIdAgentsResearch', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdAgentsResearch', result['status_code'], result['url'])
    return None


def get_characters_character_id_blueprints(character_id: int, token: str) -> list:
    """Get blueprints.
    Scopes: esi-characters.read_blueprints.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCharactersCharacterIdBlueprints',
        path_params={'character_id': character_id},
        token=token,
    )


def get_characters_character_id_corporationhistory(character_id: int) -> dict | None:
    """Get corporation history.
    Cache: 86400s.
    """
    result = execute_operation('GetCharactersCharacterIdCorporationhistory', path_params={'character_id': character_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdCorporationhistory', result['status_code'], result['url'])
    return None


def post_characters_character_id_cspa(character_id: int, token: str) -> dict | None:
    """Calculate a CSPA charge cost.
    Scopes: esi-characters.read_contacts.v1.
    """
    result = execute_operation('PostCharactersCharacterIdCspa', path_params={'character_id': character_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostCharactersCharacterIdCspa', result['status_code'], result['url'])
    return None


def get_characters_character_id_fatigue(character_id: int, token: str) -> dict | None:
    """Get jump fatigue.
    Scopes: esi-characters.read_fatigue.v1.
    Cache: 300s.
    """
    result = execute_operation('GetCharactersCharacterIdFatigue', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdFatigue', result['status_code'], result['url'])
    return None


def get_characters_character_id_medals(character_id: int, token: str) -> dict | None:
    """Get medals.
    Scopes: esi-characters.read_medals.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCharactersCharacterIdMedals', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdMedals', result['status_code'], result['url'])
    return None


def get_characters_character_id_notifications(character_id: int, token: str) -> dict | None:
    """Get character notifications.
    Scopes: esi-characters.read_notifications.v1.
    Cache: 600s.
    """
    result = execute_operation('GetCharactersCharacterIdNotifications', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdNotifications', result['status_code'], result['url'])
    return None


def get_characters_character_id_notifications_contacts(character_id: int, token: str) -> dict | None:
    """Get new contact notifications.
    Scopes: esi-characters.read_notifications.v1.
    Cache: 600s.
    """
    result = execute_operation('GetCharactersCharacterIdNotificationsContacts', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdNotificationsContacts', result['status_code'], result['url'])
    return None


def get_characters_character_id_portrait(character_id: int) -> dict | None:
    """Get character portraits.
    """
    result = execute_operation('GetCharactersCharacterIdPortrait', path_params={'character_id': character_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdPortrait', result['status_code'], result['url'])
    return None


def get_characters_character_id_roles(character_id: int, token: str) -> dict | None:
    """Get character corporation roles.
    Scopes: esi-characters.read_corporation_roles.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCharactersCharacterIdRoles', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdRoles', result['status_code'], result['url'])
    return None


def get_characters_character_id_standings(character_id: int, token: str) -> dict | None:
    """Get standings.
    Scopes: esi-characters.read_standings.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCharactersCharacterIdStandings', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdStandings', result['status_code'], result['url'])
    return None


def get_characters_character_id_titles(character_id: int, token: str) -> dict | None:
    """Get character corporation titles.
    Scopes: esi-characters.read_titles.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCharactersCharacterIdTitles', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdTitles', result['status_code'], result['url'])
    return None
