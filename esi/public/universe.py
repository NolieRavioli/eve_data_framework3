"""
esi/public/universe.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Universe  |  Scope: public
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.client.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_universe_ancestries() -> dict | None:
    """Get ancestries.
    """
    result = execute_operation('GetUniverseAncestries', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseAncestries', result['status_code'], result['url'])
    return None


def get_universe_asteroid_belts_asteroid_belt_id(asteroid_belt_id: int) -> dict | None:
    """Get asteroid belt information.
    """
    result = execute_operation('GetUniverseAsteroidBeltsAsteroidBeltId', path_params={'asteroid_belt_id': asteroid_belt_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseAsteroidBeltsAsteroidBeltId', result['status_code'], result['url'])
    return None


def get_universe_bloodlines() -> dict | None:
    """Get bloodlines.
    """
    result = execute_operation('GetUniverseBloodlines', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseBloodlines', result['status_code'], result['url'])
    return None


def get_universe_categories() -> dict | None:
    """Get item categories.
    """
    result = execute_operation('GetUniverseCategories', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseCategories', result['status_code'], result['url'])
    return None


def get_universe_categories_category_id(category_id: int) -> dict | None:
    """Get item category information.
    """
    result = execute_operation('GetUniverseCategoriesCategoryId', path_params={'category_id': category_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseCategoriesCategoryId', result['status_code'], result['url'])
    return None


def get_universe_constellations() -> dict | None:
    """Get constellations.
    """
    result = execute_operation('GetUniverseConstellations', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseConstellations', result['status_code'], result['url'])
    return None


def get_universe_constellations_constellation_id(constellation_id: int) -> dict | None:
    """Get constellation information.
    """
    result = execute_operation('GetUniverseConstellationsConstellationId', path_params={'constellation_id': constellation_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseConstellationsConstellationId', result['status_code'], result['url'])
    return None


def get_universe_factions() -> dict | None:
    """Get factions.
    """
    result = execute_operation('GetUniverseFactions', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseFactions', result['status_code'], result['url'])
    return None


def get_universe_graphics() -> dict | None:
    """Get graphics.
    """
    result = execute_operation('GetUniverseGraphics', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseGraphics', result['status_code'], result['url'])
    return None


def get_universe_graphics_graphic_id(graphic_id: int) -> dict | None:
    """Get graphic information.
    """
    result = execute_operation('GetUniverseGraphicsGraphicId', path_params={'graphic_id': graphic_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseGraphicsGraphicId', result['status_code'], result['url'])
    return None


def get_universe_groups() -> list:
    """Get item groups.
    """
    return fetch_all_pages(
        'GetUniverseGroups',
        path_params=None,
        token=None,
    )


def get_universe_groups_group_id(group_id: int) -> dict | None:
    """Get item group information.
    """
    result = execute_operation('GetUniverseGroupsGroupId', path_params={'group_id': group_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseGroupsGroupId', result['status_code'], result['url'])
    return None


def post_universe_ids() -> dict | None:
    """Bulk names to IDs.
    """
    result = execute_operation('PostUniverseIds', path_params=None, token=None)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostUniverseIds', result['status_code'], result['url'])
    return None


def get_universe_moons_moon_id(moon_id: int) -> dict | None:
    """Get moon information.
    """
    result = execute_operation('GetUniverseMoonsMoonId', path_params={'moon_id': moon_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseMoonsMoonId', result['status_code'], result['url'])
    return None


def post_universe_names() -> dict | None:
    """Get names and categories for a set of IDs.
    """
    result = execute_operation('PostUniverseNames', path_params=None, token=None)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostUniverseNames', result['status_code'], result['url'])
    return None


def get_universe_planets_planet_id(planet_id: int) -> dict | None:
    """Get planet information.
    """
    result = execute_operation('GetUniversePlanetsPlanetId', path_params={'planet_id': planet_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniversePlanetsPlanetId', result['status_code'], result['url'])
    return None


def get_universe_races() -> dict | None:
    """Get character races.
    """
    result = execute_operation('GetUniverseRaces', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseRaces', result['status_code'], result['url'])
    return None


def get_universe_regions() -> dict | None:
    """Get regions.
    """
    result = execute_operation('GetUniverseRegions', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseRegions', result['status_code'], result['url'])
    return None


def get_universe_regions_region_id(region_id: int) -> dict | None:
    """Get region information.
    """
    result = execute_operation('GetUniverseRegionsRegionId', path_params={'region_id': region_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseRegionsRegionId', result['status_code'], result['url'])
    return None


def get_universe_stargates_stargate_id(stargate_id: int) -> dict | None:
    """Get stargate information.
    """
    result = execute_operation('GetUniverseStargatesStargateId', path_params={'stargate_id': stargate_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseStargatesStargateId', result['status_code'], result['url'])
    return None


def get_universe_stars_star_id(star_id: int) -> dict | None:
    """Get star information.
    """
    result = execute_operation('GetUniverseStarsStarId', path_params={'star_id': star_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseStarsStarId', result['status_code'], result['url'])
    return None


def get_universe_stations_station_id(station_id: int) -> dict | None:
    """Get station information.
    """
    result = execute_operation('GetUniverseStationsStationId', path_params={'station_id': station_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseStationsStationId', result['status_code'], result['url'])
    return None


def get_universe_structures() -> dict | None:
    """List all public structures.
    Cache: 3600s.
    """
    result = execute_operation('GetUniverseStructures', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseStructures', result['status_code'], result['url'])
    return None


def get_universe_system_jumps() -> dict | None:
    """Get system jumps.
    Cache: 3600s.
    """
    result = execute_operation('GetUniverseSystemJumps', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseSystemJumps', result['status_code'], result['url'])
    return None


def get_universe_system_kills() -> dict | None:
    """Get system kills.
    Cache: 3600s.
    """
    result = execute_operation('GetUniverseSystemKills', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseSystemKills', result['status_code'], result['url'])
    return None


def get_universe_systems() -> dict | None:
    """Get solar systems.
    """
    result = execute_operation('GetUniverseSystems', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseSystems', result['status_code'], result['url'])
    return None


def get_universe_systems_system_id(system_id: int) -> dict | None:
    """Get solar system information.
    """
    result = execute_operation('GetUniverseSystemsSystemId', path_params={'system_id': system_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseSystemsSystemId', result['status_code'], result['url'])
    return None


def get_universe_types() -> list:
    """Get types.
    """
    return fetch_all_pages(
        'GetUniverseTypes',
        path_params=None,
        token=None,
    )


def get_universe_types_type_id(type_id: int) -> dict | None:
    """Get type information.
    """
    result = execute_operation('GetUniverseTypesTypeId', path_params={'type_id': type_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetUniverseTypesTypeId', result['status_code'], result['url'])
    return None
