"""
esi/personal/calendar.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Calendar  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id_calendar(character_id: int, token: str) -> dict | None:
    """List calendar event summaries.
    Scopes: esi-calendar.read_calendar_events.v1.
    Cache: 5s.
    """
    result = execute_operation('GetCharactersCharacterIdCalendar', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdCalendar', result['status_code'], result['url'])
    return None


def get_characters_character_id_calendar_event_id(character_id: int, event_id: int, token: str) -> dict | None:
    """Get an event.
    Scopes: esi-calendar.read_calendar_events.v1.
    Cache: 5s.
    """
    result = execute_operation('GetCharactersCharacterIdCalendarEventId', path_params={'character_id': character_id, 'event_id': event_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdCalendarEventId', result['status_code'], result['url'])
    return None


def put_characters_character_id_calendar_event_id(character_id: int, event_id: int, token: str) -> dict | None:
    """Respond to an event.
    Scopes: esi-calendar.respond_calendar_events.v1.
    Cache: 5s.
    """
    result = execute_operation('PutCharactersCharacterIdCalendarEventId', path_params={'character_id': character_id, 'event_id': event_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PutCharactersCharacterIdCalendarEventId', result['status_code'], result['url'])
    return None


def get_characters_character_id_calendar_event_id_attendees(character_id: int, event_id: int, token: str) -> dict | None:
    """Get attendees.
    Scopes: esi-calendar.read_calendar_events.v1.
    Cache: 600s.
    """
    result = execute_operation('GetCharactersCharacterIdCalendarEventIdAttendees', path_params={'character_id': character_id, 'event_id': event_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdCalendarEventIdAttendees', result['status_code'], result['url'])
    return None
