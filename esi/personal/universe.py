"""
esi/personal/universe.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Universe  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_universe_structures_structure_id(structure_id: int, token: str) -> dict | None:
    """Get structure information.
    Scopes: esi-universe.read_structures.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetUniverseStructuresStructureId', path_params={'structure_id': structure_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseStructuresStructureId', result['status_code'], result['url'])
    return None
