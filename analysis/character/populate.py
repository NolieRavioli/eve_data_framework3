"""analysis/character/populate.py — populate_all(owner_id)

Single idempotent entry point for filling (and refreshing) all character-specific
tables in the owner's private SQLite database.

Enqueued async after SSO callback; also run by the scheduler for daily refresh.

Table ownership
---------------
The ``characters`` identity row (name, token, corp) is owned by core/db/models/
and created by PrivateBase.metadata.create_all() — this module must not touch it.

All other tables fetched here are owned by *this* module:
    character_skills    — from /characters/{id}/skills/
    character_wallet    — from /characters/{id}/wallet/
    character_assets    — from /characters/{id}/assets/

Each sub-fetcher calls ensure_tables() for its own table before writing.

Design rules
------------
- Idempotent: upserts everywhere, safe to re-run.
- One fresh token obtained once at the top; all sub-fetchers reuse it.
- Failures in one sub-fetcher are caught and logged; others still run.
- Raw SQLite DDL via engine.connect() — NOT ORM models (collector-owned tables).
"""

from __future__ import annotations

import logging

from core.db.privateDB import get_private_session, initialize_private_database
from core.plugin.adapters import token_resolution

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DDL helpers — each sub-fetcher calls the one it owns
# ---------------------------------------------------------------------------

def _ensure_character_skills(engine) -> None:
    with engine.connect() as con:
        con.execute(__import__("sqlalchemy").text(
            """
            CREATE TABLE IF NOT EXISTS character_skills (
                character_id    INTEGER NOT NULL,
                skill_id        INTEGER NOT NULL,
                trained_level   INTEGER NOT NULL,
                active_level    INTEGER NOT NULL,
                skillpoints_in_skill INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (character_id, skill_id)
            )
            """
        ))
        con.commit()


def _ensure_character_wallet(engine) -> None:
    with engine.connect() as con:
        con.execute(__import__("sqlalchemy").text(
            """
            CREATE TABLE IF NOT EXISTS character_wallet (
                character_id    INTEGER PRIMARY KEY,
                balance         REAL NOT NULL,
                updated_at      TEXT NOT NULL
            )
            """
        ))
        con.commit()


def _ensure_character_assets(engine) -> None:
    with engine.connect() as con:
        con.execute(__import__("sqlalchemy").text(
            """
            CREATE TABLE IF NOT EXISTS character_assets (
                item_id         INTEGER PRIMARY KEY,
                character_id    INTEGER NOT NULL,
                type_id         INTEGER NOT NULL,
                location_id     INTEGER NOT NULL,
                location_type   TEXT NOT NULL,
                location_flag   TEXT NOT NULL,
                quantity        INTEGER NOT NULL DEFAULT 1,
                is_singleton    INTEGER NOT NULL DEFAULT 0,
                is_blueprint_copy INTEGER
            )
            """
        ))
        con.commit()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def populate_all(owner_id: int) -> None:
    """Populate / refresh all character data tables for *owner_id*.

    Obtains a fresh token then calls each sub-fetcher. Partial failures are
    logged and skipped so the remaining sub-fetchers still run.
    """
    logger.info("[CharacterPopulate] Starting for owner %s", owner_id)

    try:
        char_id, token_data = token_resolution.pick_token(owner_id)
        _, token_data = token_resolution.fresh_token(owner_id, char_id, token_data)
        access_token = token_data["access_token"]
    except Exception:
        logger.exception(
            "[CharacterPopulate] Could not obtain token for owner %s — aborting", owner_id
        )
        return

    # Get the SQLAlchemy engine for this owner's private DB.
    engine = initialize_private_database(owner_id)

    sub_fetchers = [
        ("skills",  _fetch_skills,  (engine, char_id, access_token)),
        ("wallet",  _fetch_wallet,  (engine, char_id, access_token)),
        ("assets",  _fetch_assets,  (engine, char_id, access_token)),
    ]

    for label, fn, args in sub_fetchers:
        try:
            fn(*args)
        except Exception:
            logger.exception(
                "[CharacterPopulate] sub-fetcher '%s' failed for owner %s", label, owner_id
            )

    logger.info("[CharacterPopulate] Completed for owner %s (char %s)", owner_id, char_id)


# ---------------------------------------------------------------------------
# Sub-fetchers
# ---------------------------------------------------------------------------

def _fetch_skills(engine, char_id: int, token: str) -> None:
    """Fetch character skills → character_skills table."""
    from core.esi.personal.skills import get_characters_character_id_skills

    _ensure_character_skills(engine)

    data = get_characters_character_id_skills(char_id, token)
    if not data:
        logger.debug("[CharacterPopulate] skills: no data returned for char %s", char_id)
        return

    skills = data.get("skills", [])
    if not skills:
        return

    import sqlalchemy as sa
    with engine.connect() as con:
        for skill in skills:
            con.execute(sa.text(
                """
                INSERT INTO character_skills
                    (character_id, skill_id, trained_level, active_level, skillpoints_in_skill)
                VALUES
                    (:character_id, :skill_id, :trained_level, :active_level, :skillpoints_in_skill)
                ON CONFLICT (character_id, skill_id) DO UPDATE SET
                    trained_level        = excluded.trained_level,
                    active_level         = excluded.active_level,
                    skillpoints_in_skill = excluded.skillpoints_in_skill
                """
            ), {
                "character_id": char_id,
                "skill_id": skill["skill_id"],
                "trained_level": skill.get("trained_skill_level", 0),
                "active_level": skill.get("active_skill_level", 0),
                "skillpoints_in_skill": skill.get("skillpoints_in_skill", 0),
            })
        con.commit()

    logger.info(
        "[CharacterPopulate] skills: upserted %d skills for char %s", len(skills), char_id
    )


def _fetch_wallet(engine, char_id: int, token: str) -> None:
    """Fetch wallet balance → character_wallet table."""
    from core.esi.personal.wallet import get_characters_character_id_wallet
    import datetime

    _ensure_character_wallet(engine)

    balance = get_characters_character_id_wallet(char_id, token)
    if balance is None:
        logger.debug("[CharacterPopulate] wallet: no data returned for char %s", char_id)
        return

    import sqlalchemy as sa
    with engine.connect() as con:
        con.execute(sa.text(
            """
            INSERT INTO character_wallet (character_id, balance, updated_at)
            VALUES (:character_id, :balance, :updated_at)
            ON CONFLICT (character_id) DO UPDATE SET
                balance    = excluded.balance,
                updated_at = excluded.updated_at
            """
        ), {
            "character_id": char_id,
            "balance": float(balance),
            "updated_at": datetime.datetime.utcnow().isoformat(),
        })
        con.commit()

    logger.info(
        "[CharacterPopulate] wallet: balance %.2f ISK for char %s", float(balance), char_id
    )


def _fetch_assets(engine, char_id: int, token: str) -> None:
    """Fetch character assets (all pages) → character_assets table."""
    from core.esi.personal.assets import get_characters_character_id_assets

    _ensure_character_assets(engine)

    assets = get_characters_character_id_assets(char_id, token)
    if not assets:
        logger.debug("[CharacterPopulate] assets: no data returned for char %s", char_id)
        return

    import sqlalchemy as sa
    with engine.connect() as con:
        for asset in assets:
            con.execute(sa.text(
                """
                INSERT INTO character_assets
                    (item_id, character_id, type_id, location_id, location_type,
                     location_flag, quantity, is_singleton, is_blueprint_copy)
                VALUES
                    (:item_id, :character_id, :type_id, :location_id, :location_type,
                     :location_flag, :quantity, :is_singleton, :is_blueprint_copy)
                ON CONFLICT (item_id) DO UPDATE SET
                    type_id          = excluded.type_id,
                    location_id      = excluded.location_id,
                    location_type    = excluded.location_type,
                    location_flag    = excluded.location_flag,
                    quantity         = excluded.quantity,
                    is_singleton     = excluded.is_singleton,
                    is_blueprint_copy = excluded.is_blueprint_copy
                """
            ), {
                "item_id": asset["item_id"],
                "character_id": char_id,
                "type_id": asset["type_id"],
                "location_id": asset["location_id"],
                "location_type": asset.get("location_type", ""),
                "location_flag": asset.get("location_flag", ""),
                "quantity": asset.get("quantity", 1),
                "is_singleton": int(asset.get("is_singleton", False)),
                "is_blueprint_copy": asset.get("is_blueprint_copy"),
            })
        con.commit()

    logger.info(
        "[CharacterPopulate] assets: upserted %d items for char %s", len(assets), char_id
    )
