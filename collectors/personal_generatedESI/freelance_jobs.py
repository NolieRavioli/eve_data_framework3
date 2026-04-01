"""
esi/personal/freelance_jobs.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Freelance Jobs  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_freelance_jobs_listing(character_id: int, token: str) -> dict | None:
    """List character freelance jobs.
    Scopes: esi-characters.read_freelance_jobs.v1.
    Cache: 60s.
    """
    result = execute_operation('GetCharactersFreelanceJobsListing', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersFreelanceJobsListing', result['status_code'], result['url'])
    return None


def get_characters_freelance_jobs_participation(character_id: int, job_id: int, token: str) -> dict | None:
    """Get character freelance job participation.
    Scopes: esi-characters.read_freelance_jobs.v1.
    Cache: 60s.
    """
    result = execute_operation('GetCharactersFreelanceJobsParticipation', path_params={'character_id': character_id, 'job_id': job_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersFreelanceJobsParticipation', result['status_code'], result['url'])
    return None
