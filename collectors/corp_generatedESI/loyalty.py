"""
esi/corp/loyalty.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Loyalty  |  Scope: corp
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_loyalty_stores_corporation_id_offers(corporation_id: int) -> dict | None:
    """List loyalty store offers.
    """
    result = execute_operation('GetLoyaltyStoresCorporationIdOffers', path_params={'corporation_id': corporation_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetLoyaltyStoresCorporationIdOffers', result['status_code'], result['url'])
    return None

