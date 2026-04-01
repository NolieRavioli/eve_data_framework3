"""
esi/public/character.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Character  |  Scope: public
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def post_characters_affiliation() -> dict | None:
    """Character affiliation.
    Cache: 3600s.
    """
    result = execute_operation('PostCharactersAffiliation', path_params=None, token=None)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostCharactersAffiliation', result['status_code'], result['url'])
    return None
