"""
esi/corp/corporation.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Corporation  |  Scope: corp
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_corporations_corporation_id(corporation_id: int) -> dict | None:
    """Get corporation's public information.
    Cache: 3600s.
    """
    result = execute_operation('GetCorporationsCorporationId', path_params={'corporation_id': corporation_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsCorporationId', result['status_code'], result['url'])
    return None


def get_corporations_corporation_id_alliancehistory(corporation_id: int) -> dict | None:
    """Get alliance history.
    Cache: 3600s.
    """
    result = execute_operation('GetCorporationsCorporationIdAlliancehistory', path_params={'corporation_id': corporation_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsCorporationIdAlliancehistory', result['status_code'], result['url'])
    return None


def get_corporations_corporation_id_blueprints(corporation_id: int, token: str) -> list:
    """Get corporation blueprints.
    Scopes: esi-corporations.read_blueprints.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdBlueprints',
        path_params={'corporation_id': corporation_id},
        token=token,
    )


def get_corporations_corporation_id_containers_logs(corporation_id: int, token: str) -> list:
    """Get all corporation ALSC logs.
    Scopes: esi-corporations.read_container_logs.v1.
    Cache: 600s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdContainersLogs',
        path_params={'corporation_id': corporation_id},
        token=token,
    )


def get_corporations_corporation_id_divisions(corporation_id: int, token: str) -> dict | None:
    """Get corporation divisions.
    Scopes: esi-corporations.read_divisions.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCorporationsCorporationIdDivisions', path_params={'corporation_id': corporation_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsCorporationIdDivisions', result['status_code'], result['url'])
    return None


def get_corporations_corporation_id_facilities(corporation_id: int, token: str) -> dict | None:
    """Get corporation facilities.
    Scopes: esi-corporations.read_facilities.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCorporationsCorporationIdFacilities', path_params={'corporation_id': corporation_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsCorporationIdFacilities', result['status_code'], result['url'])
    return None


def get_corporations_corporation_id_icons(corporation_id: int) -> dict | None:
    """Get corporation icon.
    Cache: 3600s.
    """
    result = execute_operation('GetCorporationsCorporationIdIcons', path_params={'corporation_id': corporation_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsCorporationIdIcons', result['status_code'], result['url'])
    return None


def get_corporations_corporation_id_medals(corporation_id: int, token: str) -> list:
    """Get corporation medals.
    Scopes: esi-corporations.read_medals.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdMedals',
        path_params={'corporation_id': corporation_id},
        token=token,
    )


def get_corporations_corporation_id_medals_issued(corporation_id: int, token: str) -> list:
    """Get corporation issued medals.
    Scopes: esi-corporations.read_medals.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdMedalsIssued',
        path_params={'corporation_id': corporation_id},
        token=token,
    )


def get_corporations_corporation_id_members(corporation_id: int, token: str) -> dict | None:
    """Get corporation members.
    Scopes: esi-corporations.read_corporation_membership.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCorporationsCorporationIdMembers', path_params={'corporation_id': corporation_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsCorporationIdMembers', result['status_code'], result['url'])
    return None


def get_corporations_corporation_id_members_limit(corporation_id: int, token: str) -> dict | None:
    """Get corporation member limit.
    Scopes: esi-corporations.track_members.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCorporationsCorporationIdMembersLimit', path_params={'corporation_id': corporation_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsCorporationIdMembersLimit', result['status_code'], result['url'])
    return None


def get_corporations_corporation_id_members_titles(corporation_id: int, token: str) -> dict | None:
    """Get corporation's members' titles.
    Scopes: esi-corporations.read_titles.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCorporationsCorporationIdMembersTitles', path_params={'corporation_id': corporation_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsCorporationIdMembersTitles', result['status_code'], result['url'])
    return None


def get_corporations_corporation_id_membertracking(corporation_id: int, token: str) -> dict | None:
    """Track corporation members.
    Scopes: esi-corporations.track_members.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCorporationsCorporationIdMembertracking', path_params={'corporation_id': corporation_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsCorporationIdMembertracking', result['status_code'], result['url'])
    return None


def get_corporations_corporation_id_roles(corporation_id: int, token: str) -> dict | None:
    """Get corporation member roles.
    Scopes: esi-corporations.read_corporation_membership.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCorporationsCorporationIdRoles', path_params={'corporation_id': corporation_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsCorporationIdRoles', result['status_code'], result['url'])
    return None


def get_corporations_corporation_id_roles_history(corporation_id: int, token: str) -> list:
    """Get corporation member roles history.
    Scopes: esi-corporations.read_corporation_membership.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdRolesHistory',
        path_params={'corporation_id': corporation_id},
        token=token,
    )


def get_corporations_corporation_id_shareholders(corporation_id: int, token: str) -> list:
    """Get corporation shareholders.
    Scopes: esi-wallet.read_corporation_wallets.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdShareholders',
        path_params={'corporation_id': corporation_id},
        token=token,
    )


def get_corporations_corporation_id_standings(corporation_id: int, token: str) -> list:
    """Get corporation standings.
    Scopes: esi-corporations.read_standings.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdStandings',
        path_params={'corporation_id': corporation_id},
        token=token,
    )


def get_corporations_corporation_id_starbases(corporation_id: int, token: str) -> list:
    """Get corporation starbases (POSes).
    Scopes: esi-corporations.read_starbases.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdStarbases',
        path_params={'corporation_id': corporation_id},
        token=token,
    )


def get_corporations_corporation_id_starbases_starbase_id(corporation_id: int, starbase_id: int, token: str) -> dict | None:
    """Get starbase (POS) detail.
    Scopes: esi-corporations.read_starbases.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCorporationsCorporationIdStarbasesStarbaseId', path_params={'corporation_id': corporation_id, 'starbase_id': starbase_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsCorporationIdStarbasesStarbaseId', result['status_code'], result['url'])
    return None


def get_corporations_corporation_id_structures(corporation_id: int, token: str) -> list:
    """Get corporation structures.
    Scopes: esi-corporations.read_structures.v1.
    Cache: 3600s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdStructures',
        path_params={'corporation_id': corporation_id},
        token=token,
    )


def get_corporations_corporation_id_titles(corporation_id: int, token: str) -> dict | None:
    """Get corporation titles.
    Scopes: esi-corporations.read_titles.v1.
    Cache: 3600s.
    """
    result = execute_operation('GetCorporationsCorporationIdTitles', path_params={'corporation_id': corporation_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsCorporationIdTitles', result['status_code'], result['url'])
    return None
