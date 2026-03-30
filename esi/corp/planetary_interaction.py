"""
esi/corp/planetary_interaction.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Planetary Interaction  |  Scope: corp
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.client.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_corporations_corporation_id_customs_offices(corporation_id: int, token: str) -> list:
    """List corporation customs offices.
    Scopes: esi-planets.read_customs_offices.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdCustomsOffices',
        path_params={'corporation_id': corporation_id},
        token=token,
    )
