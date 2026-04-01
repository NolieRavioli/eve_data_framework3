"""collectors/character — per-character ESI data ingestion.

Owns the lifecycle of character-specific data in private SQLite databases.
Called during SSO onboarding (enqueued async after auth callback) and by
the scheduler for periodic refresh of all known owners.

Public entry points:
    initialize_character(owner_id)  — full onboarding + refresh (idempotent)
"""

from collectors.character.onboarding import initialize_character

__all__ = ["initialize_character"]
