"""
esi/corp/industry.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Industry  |  Scope: corp
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_corporation_corporation_id_mining_extractions(corporation_id: int, token: str) -> list:
    """Moon extraction timers.
    Scopes: esi-industry.read_corporation_mining.v1.
    Cache: 1800s.
    """
    return fetch_all_pages(
        'GetCorporationCorporationIdMiningExtractions',
        path_params={'corporation_id': corporation_id},
        token=token,
    )


def get_corporation_corporation_id_mining_observers(corporation_id: int, token: str) -> list:
    """Corporation mining observers.
    Scopes: esi-industry.read_corporation_mining.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCorporationCorporationIdMiningObservers',
        path_params={'corporation_id': corporation_id},
        token=token,
    )


def get_corporation_corporation_id_mining_observers_observer_id(corporation_id: int, observer_id: int, token: str) -> list:
    """Observed corporation mining.
    Scopes: esi-industry.read_corporation_mining.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCorporationCorporationIdMiningObserversObserverId',
        path_params={'corporation_id': corporation_id, 'observer_id': observer_id},
        token=token,
    )


def get_corporations_corporation_id_industry_jobs(corporation_id: int, token: str) -> list:
    """List corporation industry jobs.
    Scopes: esi-industry.read_corporation_jobs.v1.
    Cache: 300s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdIndustryJobs',
        path_params={'corporation_id': corporation_id},
        token=token,
    )

