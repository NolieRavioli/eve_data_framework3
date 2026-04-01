"""
esi/personal/user_interface.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: User Interface  |  Scope: personal
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from core.esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def post_ui_autopilot_waypoint(token: str) -> dict | None:
    """Set Autopilot Waypoint.
    Scopes: esi-ui.write_waypoint.v1.
    """
    result = execute_operation('PostUiAutopilotWaypoint', path_params=None, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostUiAutopilotWaypoint', result['status_code'], result['url'])
    return None


def post_ui_openwindow_contract(token: str) -> dict | None:
    """Open Contract Window.
    Scopes: esi-ui.open_window.v1.
    """
    result = execute_operation('PostUiOpenwindowContract', path_params=None, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostUiOpenwindowContract', result['status_code'], result['url'])
    return None


def post_ui_openwindow_information(token: str) -> dict | None:
    """Open Information Window.
    Scopes: esi-ui.open_window.v1.
    """
    result = execute_operation('PostUiOpenwindowInformation', path_params=None, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostUiOpenwindowInformation', result['status_code'], result['url'])
    return None


def post_ui_openwindow_marketdetails(token: str) -> dict | None:
    """Open Market Details.
    Scopes: esi-ui.open_window.v1.
    """
    result = execute_operation('PostUiOpenwindowMarketdetails', path_params=None, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostUiOpenwindowMarketdetails', result['status_code'], result['url'])
    return None


def post_ui_openwindow_newmail(token: str) -> dict | None:
    """Open New Mail Window.
    Scopes: esi-ui.open_window.v1.
    """
    result = execute_operation('PostUiOpenwindowNewmail', path_params=None, token=token)
    if result['status_code'] in (200, 201, 204):
        return result['body']
    logger.debug('%s returned %s for %s', 'PostUiOpenwindowNewmail', result['status_code'], result['url'])
    return None
