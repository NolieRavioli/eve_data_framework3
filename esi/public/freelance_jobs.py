"""
esi/public/freelance_jobs.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Freelance Jobs  |  Scope: public
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.client.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_freelance_jobs_listing() -> dict | None:
    """List freelance jobs.
    """
    result = execute_operation('GetFreelanceJobsListing', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetFreelanceJobsListing', result['status_code'], result['url'])
    return None


def get_freelance_jobs_detail(job_id: int) -> dict | None:
    """Get freelance job details.
    Cache: 60s.
    """
    result = execute_operation('GetFreelanceJobsDetail', path_params={'job_id': job_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetFreelanceJobsDetail', result['status_code'], result['url'])
    return None
