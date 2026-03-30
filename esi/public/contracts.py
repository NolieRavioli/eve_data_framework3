"""
esi/public/contracts.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Contracts  |  Scope: public
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.client.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_contracts_public_bids_contract_id(contract_id: int) -> list:
    """Get public contract bids.
    Cache: 300s.
    """
    return fetch_all_pages(
        'GetContractsPublicBidsContractId',
        path_params={'contract_id': contract_id},
        token=None,
    )


def get_contracts_public_items_contract_id(contract_id: int) -> list:
    """Get public contract items.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetContractsPublicItemsContractId',
        path_params={'contract_id': contract_id},
        token=None,
    )


def get_contracts_public_region_id(region_id: int) -> list:
    """Get public contracts.
    Cache: 1800s.
    """
    return fetch_all_pages(
        'GetContractsPublicRegionId',
        path_params={'region_id': region_id},
        token=None,
    )
