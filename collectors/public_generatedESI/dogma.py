"""
esi/public/dogma.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Dogma  |  Scope: public
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_dogma_attributes() -> dict | None:
    """Get attributes.
    """
    result = execute_operation('GetDogmaAttributes', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetDogmaAttributes', result['status_code'], result['url'])
    return None


def get_dogma_attributes_attribute_id(attribute_id: int) -> dict | None:
    """Get attribute information.
    """
    result = execute_operation('GetDogmaAttributesAttributeId', path_params={'attribute_id': attribute_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetDogmaAttributesAttributeId', result['status_code'], result['url'])
    return None


def get_dogma_dynamic_items_type_id_item_id(item_id: int, type_id: int) -> dict | None:
    """Get dynamic item information.
    """
    result = execute_operation('GetDogmaDynamicItemsTypeIdItemId', path_params={'item_id': item_id, 'type_id': type_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetDogmaDynamicItemsTypeIdItemId', result['status_code'], result['url'])
    return None


def get_dogma_effects() -> dict | None:
    """Get effects.
    """
    result = execute_operation('GetDogmaEffects', path_params=None, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetDogmaEffects', result['status_code'], result['url'])
    return None


def get_dogma_effects_effect_id(effect_id: int) -> dict | None:
    """Get effect information.
    """
    result = execute_operation('GetDogmaEffectsEffectId', path_params={'effect_id': effect_id}, token=None)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetDogmaEffectsEffectId', result['status_code'], result['url'])
    return None

