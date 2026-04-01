"""
esi/personal/fleets.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Fleets  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_characters_character_id_fleet(character_id: int, token: str) -> dict | None:
    """Get character fleet info.
    Scopes: esi-fleets.read_fleet.v1.
    Cache: 60s.
    """
    result = execute_operation('GetCharactersCharacterIdFleet', path_params={'character_id': character_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCharactersCharacterIdFleet', result['status_code'], result['url'])
    return None


def get_fleets_fleet_id(fleet_id: int, token: str) -> dict | None:
    """Get fleet information.
    Scopes: esi-fleets.read_fleet.v1.
    Cache: 5s.
    """
    result = execute_operation('GetFleetsFleetId', path_params={'fleet_id': fleet_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetFleetsFleetId', result['status_code'], result['url'])
    return None


def put_fleets_fleet_id(fleet_id: int, token: str) -> dict | None:
    """Update fleet.
    Scopes: esi-fleets.write_fleet.v1.
    """
    result = execute_operation('PutFleetsFleetId', path_params={'fleet_id': fleet_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PutFleetsFleetId', result['status_code'], result['url'])
    return None


def get_fleets_fleet_id_members(fleet_id: int, token: str) -> dict | None:
    """Get fleet members.
    Scopes: esi-fleets.read_fleet.v1.
    Cache: 5s.
    """
    result = execute_operation('GetFleetsFleetIdMembers', path_params={'fleet_id': fleet_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetFleetsFleetIdMembers', result['status_code'], result['url'])
    return None


def post_fleets_fleet_id_members(fleet_id: int, token: str) -> dict | None:
    """Create fleet invitation.
    Scopes: esi-fleets.write_fleet.v1.
    """
    result = execute_operation('PostFleetsFleetIdMembers', path_params={'fleet_id': fleet_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostFleetsFleetIdMembers', result['status_code'], result['url'])
    return None


def delete_fleets_fleet_id_members_member_id(fleet_id: int, member_id: int, token: str) -> dict | None:
    """Kick fleet member.
    Scopes: esi-fleets.write_fleet.v1.
    """
    result = execute_operation('DeleteFleetsFleetIdMembersMemberId', path_params={'fleet_id': fleet_id, 'member_id': member_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'DeleteFleetsFleetIdMembersMemberId', result['status_code'], result['url'])
    return None


def put_fleets_fleet_id_members_member_id(fleet_id: int, member_id: int, token: str) -> dict | None:
    """Move fleet member.
    Scopes: esi-fleets.write_fleet.v1.
    """
    result = execute_operation('PutFleetsFleetIdMembersMemberId', path_params={'fleet_id': fleet_id, 'member_id': member_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PutFleetsFleetIdMembersMemberId', result['status_code'], result['url'])
    return None


def delete_fleets_fleet_id_squads_squad_id(fleet_id: int, squad_id: int, token: str) -> dict | None:
    """Delete fleet squad.
    Scopes: esi-fleets.write_fleet.v1.
    """
    result = execute_operation('DeleteFleetsFleetIdSquadsSquadId', path_params={'fleet_id': fleet_id, 'squad_id': squad_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'DeleteFleetsFleetIdSquadsSquadId', result['status_code'], result['url'])
    return None


def put_fleets_fleet_id_squads_squad_id(fleet_id: int, squad_id: int, token: str) -> dict | None:
    """Rename fleet squad.
    Scopes: esi-fleets.write_fleet.v1.
    """
    result = execute_operation('PutFleetsFleetIdSquadsSquadId', path_params={'fleet_id': fleet_id, 'squad_id': squad_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PutFleetsFleetIdSquadsSquadId', result['status_code'], result['url'])
    return None


def get_fleets_fleet_id_wings(fleet_id: int, token: str) -> dict | None:
    """Get fleet wings.
    Scopes: esi-fleets.read_fleet.v1.
    Cache: 5s.
    """
    result = execute_operation('GetFleetsFleetIdWings', path_params={'fleet_id': fleet_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetFleetsFleetIdWings', result['status_code'], result['url'])
    return None


def post_fleets_fleet_id_wings(fleet_id: int, token: str) -> dict | None:
    """Create fleet wing.
    Scopes: esi-fleets.write_fleet.v1.
    """
    result = execute_operation('PostFleetsFleetIdWings', path_params={'fleet_id': fleet_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostFleetsFleetIdWings', result['status_code'], result['url'])
    return None


def delete_fleets_fleet_id_wings_wing_id(fleet_id: int, wing_id: int, token: str) -> dict | None:
    """Delete fleet wing.
    Scopes: esi-fleets.write_fleet.v1.
    """
    result = execute_operation('DeleteFleetsFleetIdWingsWingId', path_params={'fleet_id': fleet_id, 'wing_id': wing_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'DeleteFleetsFleetIdWingsWingId', result['status_code'], result['url'])
    return None


def put_fleets_fleet_id_wings_wing_id(fleet_id: int, wing_id: int, token: str) -> dict | None:
    """Rename fleet wing.
    Scopes: esi-fleets.write_fleet.v1.
    """
    result = execute_operation('PutFleetsFleetIdWingsWingId', path_params={'fleet_id': fleet_id, 'wing_id': wing_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PutFleetsFleetIdWingsWingId', result['status_code'], result['url'])
    return None


def post_fleets_fleet_id_wings_wing_id_squads(fleet_id: int, wing_id: int, token: str) -> dict | None:
    """Create fleet squad.
    Scopes: esi-fleets.write_fleet.v1.
    """
    result = execute_operation('PostFleetsFleetIdWingsWingIdSquads', path_params={'fleet_id': fleet_id, 'wing_id': wing_id}, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostFleetsFleetIdWingsWingIdSquads', result['status_code'], result['url'])
    return None
