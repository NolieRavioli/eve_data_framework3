"""
esi/personal/corporation_projects.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Corporation Projects  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.client.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_corporations_projects_contribution(corporation_id: int, project_id: int, character_id: int, token: str) -> dict | None:
    """Get your project contribution.
    Scopes: esi-corporations.read_projects.v1.
    Cache: 60s.
    """
    result = execute_operation('GetCorporationsProjectsContribution', path_params={'corporation_id': corporation_id, 'project_id': project_id, 'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsProjectsContribution', result['status_code'], result['url'])
    return None
