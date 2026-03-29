"""
esi/corp/contacts.py
AUTO-GENERATED — do not edit by hand.
Source: ESI 2025-12-16  |  Tag: Contacts  |  Scope: corp
Regenerate: python build.py --collectors --force
"""
# ruff: noqa
from __future__ import annotations

import logging
from typing import Any

from esi.generated.client import execute_operation, fetch_all_pages

logger = logging.getLogger(__name__)


def get_corporations_corporation_id_contacts(corporation_id: int, token: str) -> list:
    """Get corporation contacts.
    Scopes: esi-corporations.read_contacts.v1.
    Cache: 300s.
    """
    return fetch_all_pages(
        'GetCorporationsCorporationIdContacts',
        path_params={'corporation_id': corporation_id},
        token=token,
    )


def get_corporations_corporation_id_contacts_labels(corporation_id: int, token: str) -> dict | None:
    """Get corporation contact labels.
    Scopes: esi-corporations.read_contacts.v1.
    Cache: 300s.
    """
    result = execute_operation('GetCorporationsCorporationIdContactsLabels', path_params={'corporation_id': corporation_id}, token=token)
    if result['status_code'] == 200:
        return result['body']
    logger.debug('%s returned %s for %s', 'GetCorporationsCorporationIdContactsLabels', result['status_code'], result['url'])
    return None
