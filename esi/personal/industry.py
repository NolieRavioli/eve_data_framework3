"""
esi/personal/industry.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Industry  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.client.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id_industry_jobs(character_id: int, token: str) -> dict | None:
    """List character industry jobs.
    Scopes: esi-industry.read_character_jobs.v1.
    Cache: 300s.
    """
    result = execute_operation('GetCharactersCharacterIdIndustryJobs', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdIndustryJobs', result['status_code'], result['url'])
    return None


def get_characters_character_id_mining(character_id: int, token: str) -> list:
    """Character mining ledger.
    Scopes: esi-industry.read_character_mining.v1.
    Cache: 600s.
    """
    return fetch_all_pages(
        'GetCharactersCharacterIdMining',
        path_params={'character_id': character_id},
        token=token,
    )
