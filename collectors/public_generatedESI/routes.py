"""
esi/public/routes.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Routes  |  Scope: public
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def post_route(origin_system_id: int, destination_system_id: int, body: list | dict) -> dict | None:
    """Get route between two systems.
    """
    result = execute_operation('PostRoute', path_params={'origin_system_id': origin_system_id, 'destination_system_id': destination_system_id}, token=None, json_body=body)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostRoute', result['status_code'], result['url'])
    return None

