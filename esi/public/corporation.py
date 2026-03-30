"""
esi/public/corporation.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Corporation  |  Scope: public
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.client.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_corporations_npccorps() -> dict | None:
    """Get npc corporations.
    """
    result = execute_operation('GetCorporationsNpccorps', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsNpccorps', result['status_code'], result['url'])
    return None
