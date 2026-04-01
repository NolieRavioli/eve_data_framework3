"""analysis/character — per-character ESI data population.

Owns the lifecycle of character-specific data in private SQLite databases.
Called async after SSO callback and by the scheduler for daily refresh.

Public entry point:
    populate_all(owner_id)  — idempotent full populate + refresh
"""

from analysis.character.populate import populate_all

__all__ = ["populate_all"]
