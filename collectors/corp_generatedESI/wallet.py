"""
esi/corp/wallet.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Wallet  |  Scope: corp
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_corporations_corporation_id_wallets(corporation_id: int, token: str) -> dict | None:
    """Returns a corporation's wallet balance.
    Scopes: esi-wallet.read_corporation_wallets.v1.
    Cache: 300s.
    """
    result = execute_operation('GetCorporationsCorporationIdWallets', path_params={'corporation_id': corporation_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsCorporationIdWallets', result['status_code'], result['url'])
    return None


def get_corporations_corporation_id_wallets_division_journal(corporation_id: int, division: str, token: str) -> list:
    """Get corporation wallet journal.
    Scopes: esi-wallet.read_corporation_wallets.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdWalletsDivisionJournal',
        path_params={'corporation_id': corporation_id, 'division': division},
        token=token,
    )


def get_corporations_corporation_id_wallets_division_transactions(corporation_id: int, division: str, token: str) -> dict | None:
    """Get corporation wallet transactions.
    Scopes: esi-wallet.read_corporation_wallets.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCorporationsCorporationIdWalletsDivisionTransactions', path_params={'corporation_id': corporation_id, 'division': division}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsCorporationIdWalletsDivisionTransactions', result['status_code'], result['url'])
    return None

