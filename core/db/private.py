"""Per-character SQLite database management."""

import logging
import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from core.db.models import Character, PrivateBase

logger = logging.getLogger(__name__)

PRIVATE_DATA_FOLDER = os.getenv("EVE_PRIVATE_DATABASE_FOLDER", "_privateData/")

_private_engines = {}
_PrivateSessions = {}


def _configure_private_sqlite(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def initialize_private_database(owner_id: int):
    # Validate owner_id to prevent path traversal
    if not isinstance(owner_id, int) or owner_id <= 0:
        raise ValueError("owner_id must be a positive integer")
    safe_id = str(int(owner_id))  # re-cast to ensure no injection
    toon_folder = os.path.join(PRIVATE_DATA_FOLDER, safe_id)
    # Verify the resolved path stays inside the private data folder
    abs_base = os.path.abspath(PRIVATE_DATA_FOLDER)
    abs_folder = os.path.abspath(toon_folder)
    if not abs_folder.startswith(abs_base):
        raise ValueError("Invalid owner_id: path traversal detected")
    os.makedirs(toon_folder, exist_ok=True)
    db_path = os.path.join(toon_folder, f"{safe_id}.db")
    abs_path = os.path.abspath(db_path).replace("\\", "/")
    db_url = f"sqlite:///{abs_path}"
    if owner_id not in _private_engines:
        engine = create_engine(
            db_url,
            echo=False,
            future=True,
            connect_args={"timeout": 30, "check_same_thread": False},
            pool_pre_ping=True,
        )
        event.listen(engine, "connect", _configure_private_sqlite)
        PrivateBase.metadata.create_all(engine)
        logger.info("Initialized private database for owner %s at %s", owner_id, abs_path)
        _private_engines[owner_id] = engine
        _PrivateSessions[owner_id] = sessionmaker(bind=engine)
    return _private_engines[owner_id]

def get_private_session(owner_id: int):
    if owner_id not in _PrivateSessions:
        initialize_private_database(owner_id)
    return _PrivateSessions[owner_id]()


# ═══════════════════════════════════════════════════════════════════════════════
# Private reads (absorbed from core/queue/db.py)
# ═══════════════════════════════════════════════════════════════════════════════


def read_private(
    owner_id: int, sql: str, params: list | None = None
) -> list[dict]:
    """Query *owner_id*'s private SQLite and return all rows as dicts."""
    from sqlalchemy import text as sa_text
    session = get_private_session(owner_id)
    try:
        result = session.execute(sa_text(sql), params or {})
        columns = list(result.keys())
        return [dict(zip(columns, row)) for row in result.fetchall()]
    finally:
        session.close()


def read_private_one(
    owner_id: int, sql: str, params: list | None = None
) -> dict | None:
    """Query *owner_id*'s private SQLite and return the first row or None."""
    rows = read_private(owner_id, sql, params)
    return rows[0] if rows else None
