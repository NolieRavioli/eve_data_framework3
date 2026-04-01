"""
esi/corp/corporation_projects.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Corporation Projects  |  Scope: corp
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_corporations_projects_listing(corporation_id: int, token: str) -> dict | None:
    """List corporation projects.
    Scopes: esi-corporations.read_projects.v1.
    """
    result = execute_operation('GetCorporationsProjectsListing', path_params={'corporation_id': corporation_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsProjectsListing', result['status_code'], result['url'])
    return None


def get_corporations_projects_detail(corporation_id: int, project_id: int, token: str) -> dict | None:
    """Get project details.
    Scopes: esi-corporations.read_projects.v1.
    Cache: 60s.
    """
    result = execute_operation('GetCorporationsProjectsDetail', path_params={'corporation_id': corporation_id, 'project_id': project_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsProjectsDetail', result['status_code'], result['url'])
    return None


def get_corporations_projects_contributors(corporation_id: int, project_id: int, token: str) -> dict | None:
    """List project contributors.
    Scopes: esi-corporations.read_projects.v1.
    """
    result = execute_operation('GetCorporationsProjectsContributors', path_params={'corporation_id': corporation_id, 'project_id': project_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsProjectsContributors', result['status_code'], result['url'])
    return None
