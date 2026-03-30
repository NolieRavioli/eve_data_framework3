"""
esi/corp/killmails.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Killmails  |  Scope: corp
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.client.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_corporations_corporation_id_killmails_recent(corporation_id: int, token: str) -> list:
    """Get a corporation's recent kills and losses.
    Scopes: esi-killmails.read_corporation_killmails.v1.
    Cache: 300s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdKillmailsRecent',
        path_params={'corporation_id': corporation_id},
        token=token,
    )
