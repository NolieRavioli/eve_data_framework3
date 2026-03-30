"""
esi/personal/contacts.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Contacts  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.client.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_alliances_alliance_id_contacts(alliance_id: int, token: str) -> list:
    """Get alliance contacts.
    Scopes: esi-alliances.read_contacts.v1.
    Cache: 300s.
    """
    return fetch_all_pages(
        'GetAlliancesAllianceIdContacts',
        path_params={'alliance_id': alliance_id},
        token=token,
    )


def get_alliances_alliance_id_contacts_labels(alliance_id: int, token: str) -> dict | None:
    """Get alliance contact labels.
    Scopes: esi-alliances.read_contacts.v1.
    Cache: 300s.
    """
    result = execute_operation('GetAlliancesAllianceIdContactsLabels', path_params={'alliance_id': alliance_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetAlliancesAllianceIdContactsLabels', result['status_code'], result['url'])
    return None


def delete_characters_character_id_contacts(character_id: int, token: str) -> dict | None:
    """Delete contacts.
    Scopes: esi-characters.write_contacts.v1.
    """
    result = execute_operation('DeleteCharactersCharacterIdContacts', path_params={'character_id': character_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'DeleteCharactersCharacterIdContacts', result['status_code'], result['url'])
    return None


def get_characters_character_id_contacts(character_id: int, token: str) -> list:
    """Get contacts.
    Scopes: esi-characters.read_contacts.v1.
    Cache: 300s.
    """
    return fetch_all_pages(
        'GetCharactersCharacterIdContacts',
        path_params={'character_id': character_id},
        token=token,
    )


def post_characters_character_id_contacts(character_id: int, token: str) -> dict | None:
    """Add contacts.
    Scopes: esi-characters.write_contacts.v1.
    """
    result = execute_operation('PostCharactersCharacterIdContacts', path_params={'character_id': character_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostCharactersCharacterIdContacts', result['status_code'], result['url'])
    return None


def put_characters_character_id_contacts(character_id: int, token: str) -> dict | None:
    """Edit contacts.
    Scopes: esi-characters.write_contacts.v1.
    """
    result = execute_operation('PutCharactersCharacterIdContacts', path_params={'character_id': character_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PutCharactersCharacterIdContacts', result['status_code'], result['url'])
    return None


def get_characters_character_id_contacts_labels(character_id: int, token: str) -> dict | None:
    """Get contact labels.
    Scopes: esi-characters.read_contacts.v1.
    Cache: 300s.
    """
    result = execute_operation('GetCharactersCharacterIdContactsLabels', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdContactsLabels', result['status_code'], result['url'])
    return None
