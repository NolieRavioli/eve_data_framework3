"""User, admin, and role CRUD — extracted from publicDB.py.

These functions operate on the ``auth_users``, ``auth_siteAdmins``, and ``auth_userRoles``
DuckDB tables.  They still call ``core.db.public.connect()`` internally — they
*use* the database but don't *own* the connection infrastructure.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _query_to_dicts(con, sql: str, params=None) -> list[dict]:
    result = con.execute(sql, params or [])
    columns = [desc[0] for desc in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def _query_one(con, sql: str, params=None) -> dict | None:
    rows = _query_to_dicts(con, sql, params)
    return rows[0] if rows else None


def _connect(database_file=None):
    from core.db.public import connect, get_database_path
    return connect(database_file or get_database_path(), read_only=False)


def _ensure_schema(con) -> None:
    from core.db.public import _ensure_public_schema
    _ensure_public_schema(con)


# ── User registration ────────────────────────────────────────────────────────


def link_public_user(owner_id: int, character_id: int, database_file: str | Path | None = None) -> None:
    con = _connect(database_file)
    try:
        _ensure_schema(con)
        con.execute(
            "INSERT OR REPLACE INTO auth_users (owner_id, character_id) VALUES (?, ?)",
            [owner_id, character_id],
        )
    finally:
        con.close()


def count_public_owners(database_file: str | Path | None = None) -> int:
    con = _connect(database_file)
    try:
        _ensure_schema(con)
        row = con.execute("SELECT COUNT(DISTINCT owner_id) FROM auth_users").fetchone()
        return int(row[0] or 0)
    finally:
        con.close()


def list_public_users(database_file: str | Path | None = None) -> list[dict]:
    con = _connect(database_file)
    try:
        _ensure_schema(con)
        return _query_to_dicts(
            con,
            """
            SELECT
                u.owner_id,
                COUNT(*) AS character_count,
                a.owner_id IS NOT NULL AS is_admin,
                COALESCE(a.is_site_owner, FALSE) AS is_site_owner,
                a.granted_at
            FROM auth_users AS u
            LEFT JOIN auth_siteAdmins AS a
              ON a.owner_id = u.owner_id
            GROUP BY u.owner_id, a.owner_id, a.is_site_owner, a.granted_at
            ORDER BY is_site_owner DESC, is_admin DESC, u.owner_id
            """,
        )
    finally:
        con.close()


# ── Site admin CRUD ──────────────────────────────────────────────────────────


def get_site_admin(owner_id: int, database_file: str | Path | None = None) -> dict | None:
    con = _connect(database_file)
    try:
        _ensure_schema(con)
        return _query_one(
            con,
            """
            SELECT owner_id, is_site_owner, granted_by, granted_at
            FROM auth_siteAdmins
            WHERE owner_id = ?
            """,
            [owner_id],
        )
    finally:
        con.close()


def upsert_site_admin(
    owner_id: int,
    *,
    is_site_owner: bool = False,
    granted_by: int | None = None,
    granted_at: datetime | None = None,
    database_file: str | Path | None = None,
) -> None:
    con = _connect(database_file)
    try:
        _ensure_schema(con)
        con.execute(
            """
            INSERT OR REPLACE INTO auth_siteAdmins (owner_id, is_site_owner, granted_by, granted_at)
            VALUES (?, ?, ?, ?)
            """,
            [owner_id, is_site_owner, granted_by, granted_at or _utc_now()],
        )
    finally:
        con.close()


def delete_site_admin(owner_id: int, database_file: str | Path | None = None) -> bool:
    if not get_site_admin(owner_id, database_file):
        return False
    con = _connect(database_file)
    try:
        _ensure_schema(con)
        con.execute("DELETE FROM auth_siteAdmins WHERE owner_id = ?", [owner_id])
    finally:
        con.close()
    return True


def delete_user(owner_id: int, database_file: str | Path | None = None) -> None:
    """Remove a user from auth_users, auth_userRoles, and auth_siteAdmins."""
    con = _connect(database_file)
    try:
        _ensure_schema(con)
        con.execute("DELETE FROM auth_userRoles WHERE owner_id = ?", [owner_id])
        con.execute("DELETE FROM auth_siteAdmins WHERE owner_id = ?", [owner_id])
        con.execute("DELETE FROM auth_users WHERE owner_id = ?", [owner_id])
    finally:
        con.close()


# ── Role management ──────────────────────────────────────────────────────────


def get_user_roles(owner_id: int, database_file: str | Path | None = None) -> list[str]:
    """Return the list of named role strings assigned to an owner."""
    con = _connect(database_file)
    try:
        _ensure_schema(con)
        rows = con.execute(
            "SELECT role_name FROM auth_userRoles WHERE owner_id = ? ORDER BY role_name",
            [owner_id],
        ).fetchall()
        return [row[0] for row in rows]
    finally:
        con.close()


def grant_user_roles(
    owner_id: int,
    roles: list[str],
    granted_by: int | None = None,
    database_file: str | Path | None = None,
) -> None:
    """Grant one or more named roles to an owner."""
    if not roles:
        return
    con = _connect(database_file)
    try:
        _ensure_schema(con)
        now = _utc_now()
        for role in roles:
            con.execute(
                """
                INSERT INTO auth_userRoles (owner_id, role_name, granted_by, granted_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (owner_id, role_name) DO NOTHING
                """,
                [owner_id, role, granted_by, now],
            )
    finally:
        con.close()


def revoke_user_role(
    owner_id: int,
    role_name: str,
    database_file: str | Path | None = None,
) -> None:
    """Remove a named role from an owner."""
    con = _connect(database_file)
    try:
        _ensure_schema(con)
        con.execute(
            "DELETE FROM auth_userRoles WHERE owner_id = ? AND role_name = ?",
            [owner_id, role_name],
        )
    finally:
        con.close()


def list_all_user_roles(database_file: str | Path | None = None) -> list[dict]:
    """Return every (owner_id, role_name, granted_by, granted_at) row."""
    con = _connect(database_file)
    try:
        _ensure_schema(con)
        return _query_to_dicts(
            con,
            "SELECT owner_id, role_name, granted_by, granted_at FROM auth_userRoles ORDER BY owner_id, role_name",
        )
    finally:
        con.close()
