"""
esi/personal/mail.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Mail  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id_mail(character_id: int, token: str) -> dict | None:
    """Return mail headers.
    Scopes: esi-mail.read_mail.v1.
    Cache: 30s.
    """
    result = execute_operation('GetCharactersCharacterIdMail', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdMail', result['status_code'], result['url'])
    return None


def post_characters_character_id_mail(character_id: int, token: str) -> dict | None:
    """Send a new mail.
    Scopes: esi-mail.send_mail.v1.
    """
    result = execute_operation('PostCharactersCharacterIdMail', path_params={'character_id': character_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostCharactersCharacterIdMail', result['status_code'], result['url'])
    return None


def get_characters_character_id_mail_labels(character_id: int, token: str) -> dict | None:
    """Get mail labels and unread counts.
    Scopes: esi-mail.read_mail.v1.
    Cache: 30s.
    """
    result = execute_operation('GetCharactersCharacterIdMailLabels', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdMailLabels', result['status_code'], result['url'])
    return None


def post_characters_character_id_mail_labels(character_id: int, token: str) -> dict | None:
    """Create a mail label.
    Scopes: esi-mail.organize_mail.v1.
    """
    result = execute_operation('PostCharactersCharacterIdMailLabels', path_params={'character_id': character_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostCharactersCharacterIdMailLabels', result['status_code'], result['url'])
    return None


def delete_characters_character_id_mail_labels_label_id(character_id: int, label_id: int, token: str) -> dict | None:
    """Delete a mail label.
    Scopes: esi-mail.organize_mail.v1.
    """
    result = execute_operation('DeleteCharactersCharacterIdMailLabelsLabelId', path_params={'character_id': character_id, 'label_id': label_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'DeleteCharactersCharacterIdMailLabelsLabelId', result['status_code'], result['url'])
    return None


def get_characters_character_id_mail_lists(character_id: int, token: str) -> dict | None:
    """Return mailing list subscriptions.
    Scopes: esi-mail.read_mail.v1.
    Cache: 120s.
    """
    result = execute_operation('GetCharactersCharacterIdMailLists', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdMailLists', result['status_code'], result['url'])
    return None


def delete_characters_character_id_mail_mail_id(character_id: int, mail_id: int, token: str) -> dict | None:
    """Delete a mail.
    Scopes: esi-mail.organize_mail.v1.
    """
    result = execute_operation('DeleteCharactersCharacterIdMailMailId', path_params={'character_id': character_id, 'mail_id': mail_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'DeleteCharactersCharacterIdMailMailId', result['status_code'], result['url'])
    return None


def get_characters_character_id_mail_mail_id(character_id: int, mail_id: int, token: str) -> dict | None:
    """Return a mail.
    Scopes: esi-mail.read_mail.v1.
    Cache: 30s.
    """
    result = execute_operation('GetCharactersCharacterIdMailMailId', path_params={'character_id': character_id, 'mail_id': mail_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdMailMailId', result['status_code'], result['url'])
    return None


def put_characters_character_id_mail_mail_id(character_id: int, mail_id: int, token: str) -> dict | None:
    """Update metadata about a mail.
    Scopes: esi-mail.organize_mail.v1.
    """
    result = execute_operation('PutCharactersCharacterIdMailMailId', path_params={'character_id': character_id, 'mail_id': mail_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PutCharactersCharacterIdMailMailId', result['status_code'], result['url'])
    return None
