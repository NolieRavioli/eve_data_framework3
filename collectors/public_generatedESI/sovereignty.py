"""
esi/public/sovereignty.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Sovereignty  |  Scope: public
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_sovereignty_campaigns() -> dict | None:
    """List sovereignty campaigns.
    Cache: 5s.
    """
    result = execute_operation('GetSovereigntyCampaigns', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetSovereigntyCampaigns', result['status_code'], result['url'])
    return None


def get_sovereignty_map() -> dict | None:
    """List sovereignty of systems.
    Cache: 3600s.
    """
    result = execute_operation('GetSovereigntyMap', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetSovereigntyMap', result['status_code'], result['url'])
    return None


def get_sovereignty_structures() -> dict | None:
    """List sovereignty structures.
    Cache: 120s.
    """
    result = execute_operation('GetSovereigntyStructures', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetSovereigntyStructures', result['status_code'], result['url'])
    return None

