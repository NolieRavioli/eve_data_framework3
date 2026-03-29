"""
esi/public_api/incursions.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Incursions  |  Scope: public_api
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_incursions() -> dict | None:
    """List incursions.
    Cache: 300s.
    """
    result = execute_operation('GetIncursions', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetIncursions', result['status_code'], result['url'])
    return None
