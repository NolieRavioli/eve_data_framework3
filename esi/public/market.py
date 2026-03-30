"""
esi/public/market.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Market  |  Scope: public
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.client.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_markets_groups() -> dict | None:
    """Get item groups.
    """
    result = execute_operation('GetMarketsGroups', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetMarketsGroups', result['status_code'], result['url'])
    return None


def get_markets_groups_market_group_id(market_group_id: int) -> dict | None:
    """Get item group information.
    """
    result = execute_operation('GetMarketsGroupsMarketGroupId', path_params={'market_group_id': market_group_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetMarketsGroupsMarketGroupId', result['status_code'], result['url'])
    return None


def get_markets_prices() -> dict | None:
    """List market prices.
    Cache: 3600s.
    """
    result = execute_operation('GetMarketsPrices', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetMarketsPrices', result['status_code'], result['url'])
    return None


def get_markets_region_id_history(region_id: int) -> dict | None:
    """List historical market statistics in a region.
    """
    result = execute_operation('GetMarketsRegionIdHistory', path_params={'region_id': region_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetMarketsRegionIdHistory', result['status_code'], result['url'])
    return None


def get_markets_region_id_orders(region_id: int) -> list:
    """List orders in a region.
    Cache: 300s.
    """
    return fetch_all_pages(
        'GetMarketsRegionIdOrders',
        path_params={'region_id': region_id},
        token=None,
    )


def get_markets_region_id_types(region_id: int) -> list:
    """List type IDs relevant to a market.
    Cache: 600s.
    """
    return fetch_all_pages(
        'GetMarketsRegionIdTypes',
        path_params={'region_id': region_id},
        token=None,
    )
