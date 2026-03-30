import logging
import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from db.models import (
    Character,
    PrivateBase,
    PublicBase,
)
from db import sde_store

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


def initialize_public_database():
    logger.info("Public SQLite has been retired; ensuring DuckDB public schema instead.")
    return sde_store.ensure_public_database()


def initialize_private_database(owner_id: int):
    toon_folder = os.path.join(PRIVATE_DATA_FOLDER, str(owner_id))
    os.makedirs(toon_folder, exist_ok=True)
    db_path = os.path.join(toon_folder, f"{owner_id}.db")
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


def get_public_session():
    raise RuntimeError(
        "Public SQLite sessions have been retired. Use util.sde_store helpers against _publicData/sde.duckdb."
    )


def get_private_session(owner_id: int):
    if owner_id not in _PrivateSessions:
        initialize_private_database(owner_id)
    return _PrivateSessions[owner_id]()
