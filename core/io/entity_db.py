"""core/io/entity_db.py — DuckDB connection manager for per-entity databases.

Provides fresh DuckDB connections to per-entity database files stored at
`_privateData/<entity_id>/<entity_id>.duckdb`.

Entities can be characters (owner_id), corporations, or alliances.
All per-owner data — including auth tokens — is stored in DuckDB.

Usage:
    from core.io.entity_db import connect_entity

    con = connect_entity(owner_id)
    try:
        con.execute("SELECT * FROM character_skills WHERE character_id = ?", [char_id])
    finally:
        con.close()
"""

from __future__ import annotations

import logging
import os

import duckdb

logger = logging.getLogger(__name__)


def _private_data_folder() -> str:
    return os.environ.get("EVE_PRIVATE_DATABASE_FOLDER", "_privateData")


def connect_entity(entity_id: int) -> duckdb.DuckDBPyConnection:
    """Return a fresh DuckDB connection for a per-entity database.

    The database file is located at:
        `_privateData/<entity_id>/<entity_id>.duckdb`

    The parent directory is created automatically if it does not exist.
    Each call returns a new, independent connection — do not share connections
    across threads.

    :param entity_id: The entity identifier (owner_id, corporation_id, or
        alliance_id). Must be a positive integer.
    :returns: An open DuckDB connection. The caller is responsible for closing it.
    :raises ValueError: If entity_id is not a positive integer.
    """
    if not isinstance(entity_id, int) or entity_id <= 0:
        raise ValueError(f"entity_id must be a positive integer, got {entity_id!r}")

    private_root = _private_data_folder()
    entity_dir = os.path.join(private_root, str(entity_id))

    # Verify the resolved path stays within the private data root (path-traversal guard).
    abs_root = os.path.abspath(private_root)
    abs_dir = os.path.abspath(entity_dir)
    if not abs_dir.startswith(abs_root):
        raise ValueError(f"Invalid entity_id: path traversal detected for {entity_id!r}")

    os.makedirs(abs_dir, exist_ok=True)
    db_path = os.path.join(abs_dir, f"{entity_id}.duckdb")

    con = duckdb.connect(db_path)
    con.execute("PRAGMA threads=4")
    return con


def ensure_character_table(con) -> None:
    """Create the characters table if it does not exist.  Idempotent.

    This table stores ESI OAuth tokens and basic character metadata
    for every character linked to the entity (owner).
    """
    con.execute("""
        CREATE TABLE IF NOT EXISTS characters (
            character_id    BIGINT PRIMARY KEY,
            name            VARCHAR,
            corporation_id  BIGINT,
            birthday        VARCHAR,
            security_status DOUBLE,
            alliance_id     BIGINT,
            access_token    VARCHAR,
            refresh_token   VARCHAR,
            expires_at      DOUBLE,
            scopes          VARCHAR
        )
    """)
