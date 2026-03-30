"""
esi/personal/killmails.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Killmails  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.client.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id_killmails_recent(character_id: int, token: str) -> list:
    """Get a character's recent kills and losses.
    Scopes: esi-killmails.read_killmails.v1.
    Cache: 300s.
    """
    return fetch_all_pages(
        'GetCharactersCharacterIdKillmailsRecent',
        path_params={'character_id': character_id},
        token=token,
    )
