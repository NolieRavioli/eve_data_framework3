"""
esi/public/status.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Status  |  Scope: public
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_status() -> dict | None:
    """Retrieve the uptime and player counts.
    Cache: 30s.
    """
    result = execute_operation('GetStatus', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetStatus', result['status_code'], result['url'])
    return None

