"""
esi/public/planetary_interaction.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Planetary Interaction  |  Scope: public
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_universe_schematics_schematic_id(schematic_id: int) -> dict | None:
    """Get schematic information.
    Cache: 3600s.
    """
    result = execute_operation('GetUniverseSchematicsSchematicId', path_params={'schematic_id': schematic_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseSchematicsSchematicId', result['status_code'], result['url'])
    return None
