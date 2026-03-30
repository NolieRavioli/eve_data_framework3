"""
esi/corp/market.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Market  |  Scope: corp
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.client.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_corporations_corporation_id_orders(corporation_id: int, token: str) -> list:
    """List open orders from a corporation.
    Scopes: esi-markets.read_corporation_orders.v1.
    Cache: 1200s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdOrders',
        path_params={'corporation_id': corporation_id},
        token=token,
    )


def get_corporations_corporation_id_orders_history(corporation_id: int, token: str) -> list:
    """List historical orders from a corporation.
    Scopes: esi-markets.read_corporation_orders.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdOrdersHistory',
        path_params={'corporation_id': corporation_id},
        token=token,
    )
