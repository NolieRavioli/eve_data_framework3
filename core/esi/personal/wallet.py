"""
esi/personal/wallet.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Wallet  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id_wallet(character_id: int, token: str) -> dict | None:
    """Get a character's wallet balance.
    Scopes: esi-wallet.read_character_wallet.v1.
    Cache: 120s.
    """
    result = execute_operation('GetCharactersCharacterIdWallet', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdWallet', result['status_code'], result['url'])
    return None


def get_characters_character_id_wallet_journal(character_id: int, token: str) -> list:
    """Get character wallet journal.
    Scopes: esi-wallet.read_character_wallet.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCharactersCharacterIdWalletJournal',
        path_params={'character_id': character_id},
        token=token,
    )


def get_characters_character_id_wallet_transactions(character_id: int, token: str) -> dict | None:
    """Get wallet transactions.
    Scopes: esi-wallet.read_character_wallet.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCharactersCharacterIdWalletTransactions', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdWalletTransactions', result['status_code'], result['url'])
    return None
