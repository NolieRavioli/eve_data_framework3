"""
esi/corp/freelance_jobs.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Freelance Jobs  |  Scope: corp
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_corporations_freelance_jobs_listing(corporation_id: int, token: str) -> dict | None:
    """List corporation freelance jobs.
    Scopes: esi-corporations.read_freelance_jobs.v1.
    """
    result = execute_operation('GetCorporationsFreelanceJobsListing', path_params={'corporation_id': corporation_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsFreelanceJobsListing', result['status_code'], result['url'])
    return None


def get_corporations_freelance_jobs_participants(corporation_id: int, job_id: int, token: str) -> dict | None:
    """List participants of a freelance job.
    Scopes: esi-corporations.read_freelance_jobs.v1.
    """
    result = execute_operation('GetCorporationsFreelanceJobsParticipants', path_params={'corporation_id': corporation_id, 'job_id': job_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsFreelanceJobsParticipants', result['status_code'], result['url'])
    return None
