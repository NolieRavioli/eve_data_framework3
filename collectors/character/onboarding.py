"""Character onboarding and periodic refresh collector.

initialize_character(owner_id) is the single idempotent entry point.
It is enqueued to the private task queue immediately after SSO callback
and re-run on whatever schedule the scheduler engine configures.

Design rules:
  - Idempotent: upserts everywhere, safe to re-run for refresh.
  - One fresh ESI token obtained once at the top; all sub-fetchers reuse it.
  - Writes only to private SQLite (via get_private_session).
  - Each sub-fetcher is a standalone function — add new ones as endpoints
    are implemented.  Failures in one sub-fetcher are logged and skipped so
    the others still run.
"""

import logging

from core.db.privateDB import get_private_session
from core.plugin.adapters import token_resolution

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def initialize_character(owner_id: int) -> None:
    """Full character onboarding / periodic refresh for *owner_id*.

    Obtains a fresh token, then calls each sub-fetcher in turn.
    Individual sub-fetcher failures are caught and logged — a partial
    refresh is better than no refresh.
    """
    logger.info("[CharacterCollector] Starting for owner %s", owner_id)

    # Resolve a fresh token for this owner.
    try:
        char_id, token_data = token_resolution.pick_token(owner_id)
        _, token_data = token_resolution.fresh_token(owner_id, char_id, token_data)
        access_token = token_data["access_token"]
    except Exception:
        logger.exception(
            "[CharacterCollector] Could not obtain token for owner %s — skipping", owner_id
        )
        return

    _sub_fetchers = [
        # Each tuple: (label, fn, positional_args)
        # Add new endpoints here as they are implemented.
        ("skills",       _fetch_skills,       (owner_id, char_id, access_token)),
        ("wallet",       _fetch_wallet,        (owner_id, char_id, access_token)),
        ("assets",       _fetch_assets,        (owner_id, char_id, access_token)),
    ]

    for label, fn, args in _sub_fetchers:
        try:
            fn(*args)
        except Exception:
            logger.exception(
                "[CharacterCollector] sub-fetcher '%s' failed for owner %s", label, owner_id
            )

    logger.info("[CharacterCollector] Completed for owner %s (char %s)", owner_id, char_id)


# ---------------------------------------------------------------------------
# Sub-fetchers — implement these as ESI endpoints are wired up
# ---------------------------------------------------------------------------

def _fetch_skills(owner_id: int, char_id: int, token: str) -> None:
    """Fetch character skills and write to private SQLite.

    ESI: GET /characters/{character_id}/skills/
    Requires scope: esi-skills.read_skills.v1
    """
    # TODO: implement when personal_generatedESI skill endpoint is available.
    logger.debug("[CharacterCollector] skills — stub, not yet implemented")


def _fetch_wallet(owner_id: int, char_id: int, token: str) -> None:
    """Fetch wallet balance and write to private SQLite.

    ESI: GET /characters/{character_id}/wallet/
    Requires scope: esi-wallet.read_character_wallet.v1
    """
    # TODO: implement when personal_generatedESI wallet endpoint is available.
    logger.debug("[CharacterCollector] wallet — stub, not yet implemented")


def _fetch_assets(owner_id: int, char_id: int, token: str) -> None:
    """Fetch character assets and write to private SQLite.

    ESI: GET /characters/{character_id}/assets/
    Requires scope: esi-assets.read_assets.v1
    """
    # TODO: implement when personal_generatedESI assets endpoint is available.
    logger.debug("[CharacterCollector] assets — stub, not yet implemented")
