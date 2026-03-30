"""
esi/corp/contracts.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Contracts  |  Scope: corp
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.client.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_corporations_corporation_id_contracts(corporation_id: int, token: str) -> list:
    """Get corporation contracts.
    Scopes: esi-contracts.read_corporation_contracts.v1.
    Cache: 300s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdContracts',
        path_params={'corporation_id': corporation_id},
        token=token,
    )


def get_corporations_corporation_id_contracts_contract_id_bids(contract_id: int, corporation_id: int, token: str) -> list:
    """Get corporation contract bids.
    Scopes: esi-contracts.read_corporation_contracts.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdContractsContractIdBids',
        path_params={'contract_id': contract_id, 'corporation_id': corporation_id},
        token=token,
    )


def get_corporations_corporation_id_contracts_contract_id_items(contract_id: int, corporation_id: int, token: str) -> dict | None:
    """Get corporation contract items.
    Scopes: esi-contracts.read_corporation_contracts.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCorporationsCorporationIdContractsContractIdItems', path_params={'contract_id': contract_id, 'corporation_id': corporation_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsCorporationIdContractsContractIdItems', result['status_code'], result['url'])
    return None
