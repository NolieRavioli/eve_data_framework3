"""
esi/public/killmails.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Killmails  |  Scope: public
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_killmails_killmail_id_killmail_hash(killmail_hash: str, killmail_id: int) -> dict | None:
    """Get a single killmail.
    Cache: 2592000s.
    """
    result = execute_operation('GetKillmailsKillmailIdKillmailHash', path_params={'killmail_hash': killmail_hash, 'killmail_id': killmail_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetKillmailsKillmailIdKillmailHash', result['status_code'], result['url'])
    return None
