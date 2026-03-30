"""
esi/personal/contracts.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Contracts  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.client.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id_contracts(character_id: int, token: str) -> list:
    """Get contracts.
    Scopes: esi-contracts.read_character_contracts.v1.
    Cache: 300s.
    """
    return fetch_all_pages(
        'GetCharactersCharacterIdContracts',
        path_params={'character_id': character_id},
        token=token,
    )


def get_characters_character_id_contracts_contract_id_bids(character_id: int, contract_id: int, token: str) -> dict | None:
    """Get contract bids.
    Scopes: esi-contracts.read_character_contracts.v1.
    Cache: 300s.
    """
    result = execute_operation('GetCharactersCharacterIdContractsContractIdBids', path_params={'character_id': character_id, 'contract_id': contract_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdContractsContractIdBids', result['status_code'], result['url'])
    return None


def get_characters_character_id_contracts_contract_id_items(character_id: int, contract_id: int, token: str) -> dict | None:
    """Get contract items.
    Scopes: esi-contracts.read_character_contracts.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCharactersCharacterIdContractsContractIdItems', path_params={'character_id': character_id, 'contract_id': contract_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdContractsContractIdItems', result['status_code'], result['url'])
    return None
