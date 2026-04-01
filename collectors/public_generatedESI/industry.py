"""
esi/public/industry.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Industry  |  Scope: public
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_industry_facilities() -> dict | None:
    """List industry facilities.
    Cache: 3600s.
    """
    result = execute_operation('GetIndustryFacilities', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetIndustryFacilities', result['status_code'], result['url'])
    return None


def get_industry_systems() -> dict | None:
    """List solar system cost indices.
    Cache: 3600s.
    """
    result = execute_operation('GetIndustrySystems', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetIndustrySystems', result['status_code'], result['url'])
    return None
