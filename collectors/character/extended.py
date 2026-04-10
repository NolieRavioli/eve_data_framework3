"""collectors/character/extended.py — scope-gated orchestrator for all character sub-collectors.

Registered scheduler job: ``character_extended_refresh`` (interval 1 h).

For each owner:
  1. Loads a fresh access token via pick_token / fresh_token.
  2. Gathers the character's active scope set from the token_data.
  3. Runs every SCOPE_COLLECTORS entry whose required scope is present.
  4. Runs all NO_SCOPE_COLLECTORS unconditionally.
"""

from __future__ import annotations

import logging

import core.io.public as db
from core.auth.tokens import pick_token, fresh_token

logger = logging.getLogger(__name__)


def _get_scope_set(token_data: dict) -> set[str]:
    scopes_str = token_data.get("scopes", "")
    return set(scopes_str.split()) if scopes_str else set()


def run_extended_refresh(owner_id: int | None = None) -> None:
    """Public entry point — called by the scheduler or enqueue().

    If *owner_id* is provided, refreshes only that owner (used on SSO login).
    If *owner_id* is None, refreshes every known owner (used by the scheduler).
    """
    from collectors.character.comms import SCOPE_COLLECTORS as _comms, NO_SCOPE_COLLECTORS as _no_comms
    from collectors.character.finance import SCOPE_COLLECTORS as _finance
    from collectors.character.industry import SCOPE_COLLECTORS as _industry
    from collectors.character.social import SCOPE_COLLECTORS as _social, NO_SCOPE_COLLECTORS as _no_social
    from collectors.character.combat import SCOPE_COLLECTORS as _combat
    from collectors.character.identity import SCOPE_COLLECTORS as _identity, NO_SCOPE_COLLECTORS as _no_identity

    all_scope_collectors = (
        _comms + _finance + _industry + _social + _combat + _identity
    )
    all_no_scope_collectors = _no_comms + _no_social + _no_identity

    if owner_id is not None:
        _run_for_owner(owner_id, all_scope_collectors, all_no_scope_collectors)
        return

    con = db.connect()
    try:
        rows = con.execute("SELECT DISTINCT owner_id FROM auth_users").fetchall()
        owner_ids = [r[0] for r in rows]
    finally:
        con.close()

    for owner_id in owner_ids:
        try:
            _run_for_owner(owner_id, all_scope_collectors, all_no_scope_collectors)
        except Exception:
            logger.exception("[extended] failed for owner %s", owner_id)


def _run_for_owner(
    owner_id: int,
    scope_collectors: list,
    no_scope_collectors: list,
) -> None:
    try:
        char_id, token_data = pick_token(owner_id)
        char_id, token_data = fresh_token(owner_id, char_id, token_data)
    except Exception:
        logger.warning("[extended] could not get token for owner %s — skipping", owner_id)
        return

    access_token = token_data["access_token"]
    owner_scopes = _get_scope_set(token_data)

    # No-scope collectors (run regardless of scopes)
    for domain, fn in no_scope_collectors:
        try:
            fn(owner_id, char_id, access_token)
        except Exception:
            logger.exception("[extended] %s failed for owner %s", domain, owner_id)

    # Scope-gated collectors
    for required_scope, domain, fn in scope_collectors:
        if required_scope not in owner_scopes:
            continue
        try:
            fn(owner_id, char_id, access_token)
        except Exception:
            logger.exception("[extended] %s failed for owner %s", domain, owner_id)
