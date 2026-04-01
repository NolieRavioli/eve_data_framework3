"""
esi/personal/market.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Market  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id_orders(character_id: int, token: str) -> dict | None:
    """List open orders from a character.
    Scopes: esi-markets.read_character_orders.v1.
    Cache: 1200s.
    """
    result = execute_operation('GetCharactersCharacterIdOrders', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdOrders', result['status_code'], result['url'])
    return None


def get_characters_character_id_orders_history(character_id: int, token: str) -> list:
    """List historical orders by a character.
    Scopes: esi-markets.read_character_orders.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCharactersCharacterIdOrdersHistory',
        path_params={'character_id': character_id},
        token=token,
    )


def get_markets_structures_structure_id(structure_id: int, token: str) -> list:
    """List orders in a structure.
    Scopes: esi-markets.structure_markets.v1.
    Cache: 300s.
    """
    return fetch_all_pages(
        'GetMarketsStructuresStructureId',
        path_params={'structure_id': structure_id},
        token=token,
    )
