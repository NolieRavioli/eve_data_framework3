"""
esi/public/meta.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Meta  |  Scope: public
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_meta_changelog() -> dict | None:
    """Get changelog.
    """
    result = execute_operation('GetMetaChangelog', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetMetaChangelog', result['status_code'], result['url'])
    return None


def get_meta_compatibility_dates() -> dict | None:
    """Get compatibility dates.
    """
    result = execute_operation('GetMetaCompatibilityDates', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetMetaCompatibilityDates', result['status_code'], result['url'])
    return None


def get_meta_status() -> dict | None:
    """Get health status.
    """
    result = execute_operation('GetMetaStatus', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetMetaStatus', result['status_code'], result['url'])
    return None
