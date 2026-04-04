"""core/esi/cache.py — Persistent DuckDB-backed ESI response cache.

Ownership
---------
This module owns two DuckDB tables:

``esi_route_specs``
    One row per ESI operation (route pattern).  Populated at startup from the
    auto-generated seed rows in ``core.esi.generated.cache_ddl``.  Also stores
    live rate-limit header values observed at runtime (updated non-blocking via
    the serialised writer thread).

``esi_cache``
    One row per unique URL+params combination ever successfully fetched.  Rows
    whose ``expires_at`` timestamp is in the past are pruned before every write,
    keeping the table bounded to only active/relevant cache entries.

Threading
---------
All writes go through ``core.db.writer.db_write()`` (the serialised writer
thread) so they are non-blocking and thread-safe.  Reads use a fresh
``publicDB.connect()`` per call.

Cache key
---------
``sha256(method + "|" + full_url + "|" + sorted_params_json + "|" + auth_hash)``
truncated to 48 hex characters.  The ``auth_hash`` is the first 16 characters
of ``sha256(Authorization_header)`` so private-route responses are
character-scoped without storing the token itself.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ── Static DDL for esi_cache ──────────────────────────────────────────────────
# This table's schema does NOT depend on routes.json — inline it here so the
# table is always created at startup even when cache_ddl.py hasn't been
# generated yet (i.e. before the first build.py run).
_ESI_CACHE_DDL = """
CREATE TABLE IF NOT EXISTS esi_cache (
    cache_key                 VARCHAR PRIMARY KEY,
    operation_id              VARCHAR,
    method                    VARCHAR,
    full_url                  VARCHAR,
    params_json               VARCHAR,
    etag                      VARCHAR,
    last_modified             VARCHAR,
    response_body             VARCHAR,
    status_code               INTEGER,
    fetched_at                TIMESTAMP,
    expires_at                TIMESTAMP,
    rl_group                  VARCHAR,
    rl_remaining              INTEGER,
    rl_used                   INTEGER,
    rl_limit_str              VARCHAR,
    retry_after               INTEGER,
    x_pages                   INTEGER,
    x_esi_error_limit_remain  INTEGER,
    x_esi_error_limit_reset   INTEGER
)
"""

# ── pre-computed maps from ROUTE_SPECS_SEED_ROWS ─────────────────────────────
# All populated lazily on first call to get_ttl_for_url() / get_static_rate_limit_seeds().
_TTL_MAP: dict[str, int] = {}          # normalized_path -> cache_age
_OP_MAP: dict[str, str] = {}           # normalized_path -> operation_id
_RL_GROUP_MAP: dict[str, str] = {}     # normalized_path -> rate_limit_group name
_RL_LIMITS_MAP: dict[str, dict] = {}   # group_name -> {limit, window_seconds, window_str}
_TTL_MAP_LOADED = False


def _parse_window_size(s: str) -> int:
    """Convert ESI window-size string (e.g. '15m', '1h', '300s') to seconds."""
    s = (s or "").strip()
    if not s:
        return 900  # 15-minute default
    if s.endswith("m"):
        return int(float(s[:-1])) * 60
    if s.endswith("h"):
        return int(float(s[:-1])) * 3600
    if s.endswith("s"):
        return int(float(s[:-1]))
    try:
        return int(s)
    except ValueError:
        return 900


def _load_ttl_map() -> None:
    global _TTL_MAP_LOADED
    if _TTL_MAP_LOADED:
        return
    try:
        from core.esi.generated.cache_ddl import ROUTE_SPECS_SEED_ROWS  # type: ignore[import]
    except (ImportError, Exception) as _exc:
        logger.debug("[ESICache] cache_ddl.py not importable — TTL map empty: %s", _exc)
        _TTL_MAP_LOADED = True
        return

    for row in ROUTE_SPECS_SEED_ROWS:
        path = row.get("path") or ""
        cache_age = row.get("cache_age")
        op_id = row.get("operation_id") or ""
        if path and cache_age:
            norm = _normalize_path(path)
            _TTL_MAP[norm] = int(cache_age)
            _OP_MAP[norm] = op_id

        # Rate-limit group seeding.
        rl_group = row.get("rate_limit_group")
        if path and rl_group:
            norm = _normalize_path(path)
            _RL_GROUP_MAP[norm] = rl_group
            if rl_group not in _RL_LIMITS_MAP:
                max_tokens = row.get("rate_limit_max_tokens") or 0
                window_str = row.get("rate_limit_window_size") or ""
                _RL_LIMITS_MAP[rl_group] = {
                    "remaining": None,           # unknown until first live response
                    "used": None,
                    "limit": int(max_tokens) if max_tokens else 0,
                    "window_seconds": _parse_window_size(window_str),
                    "window_str": window_str,
                }

    _TTL_MAP_LOADED = True
    logger.debug(
        "[ESICache] TTL map loaded: %d cacheable routes, %d rate-limit groups",
        len(_TTL_MAP), len(_RL_LIMITS_MAP),
    )


def get_static_rate_limit_seeds() -> tuple[dict[str, str], dict[str, dict]]:
    """Return ``(path_to_group, group_to_limits)`` dicts pre-seeded from routes.json.

    Used by ``EsiRateLimiter.__init__`` to populate ``_url_to_group`` and
    ``_group_states`` before any live ESI requests have been made.
    """
    _load_ttl_map()
    return dict(_RL_GROUP_MAP), {g: dict(v) for g, v in _RL_LIMITS_MAP.items()}


def _normalize_path(path: str) -> str:
    """Replace path param placeholders with ``{id}`` so runtime URLs match spec paths."""
    # Replace {parameter_name} style placeholders
    return re.sub(r"\{[^}]+\}", "{id}", path)


def _normalize_url_path(url: str) -> str:
    """Extract and normalize just the path segment from a full URL."""
    parsed = urlparse(url)
    path = parsed.path
    # Strip /latest/ prefix if present, keep /<path>
    path = re.sub(r"^/latest", "", path)
    # Replace numeric IDs with {id}
    return re.sub(r"/\d+", "/{id}", path)


def get_ttl_for_url(url: str) -> tuple[int, str] | tuple[None, None]:
    """Return ``(ttl_seconds, operation_id)`` for a URL, or ``(None, None)`` if not cacheable."""
    _load_ttl_map()
    norm = _normalize_url_path(url)
    ttl = _TTL_MAP.get(norm)
    op_id = _OP_MAP.get(norm)
    if ttl:
        return ttl, op_id
    return None, None


def make_cache_key(method: str, url: str, params: dict | None, auth_header: str | None) -> str:
    """Return a deterministic 48-char hex cache key for a request."""
    params_text = json.dumps(sorted((params or {}).items()), separators=(",", ":"))
    auth_hash = hashlib.sha256((auth_header or "").encode()).hexdigest()[:16]
    raw = f"{method.upper()}|{url}|{params_text}|{auth_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()[:48]


# ── Table DDL ─────────────────────────────────────────────────────────────────

def ensure_tables(con) -> None:
    """Create ``esi_route_specs`` and ``esi_cache`` if they don't exist.

    ``esi_cache`` is always created from the inline ``_ESI_CACHE_DDL`` constant
    so it exists even before ``build.py`` has been run.

    ``esi_route_specs`` is created from the generated ``cache_ddl.py`` when
    available.  Uses ``ALTER TABLE ADD COLUMN IF NOT EXISTS`` for every column
    declared in ``SPEC_COLUMN_NAMES`` so that re-running after a ``build.py``
    update automatically adds any new spec columns without dropping existing data.
    """
    # esi_cache is always safe to create — its schema is static.
    con.execute(_ESI_CACHE_DDL)

    try:
        from core.esi.generated.cache_ddl import (  # type: ignore[import]
            ROUTE_SPECS_DDL,
            SPEC_COLUMN_NAMES,
        )
    except ImportError:
        logger.warning(
            "[ESICache] core/esi/generated/cache_ddl.py not found — "
            "esi_route_specs table skipped.  Run 'python build.py' to generate it."
        )
        return

    con.execute(ROUTE_SPECS_DDL)

    # Migration: add any columns that exist in the generated DDL but not yet in
    # the live table (handles re-runs after spec updates add new fields).
    existing_cols: set[str] = set()
    try:
        rows = con.execute("PRAGMA table_info(esi_route_specs)").fetchall()
        existing_cols = {r[1] for r in rows}
    except Exception:
        try:
            rows = con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'esi_route_specs'"
            ).fetchall()
            existing_cols = {r[0] for r in rows}
        except Exception:
            pass

    if existing_cols:
        for col in SPEC_COLUMN_NAMES:
            if col not in existing_cols and col != "operation_id":
                try:
                    con.execute(f"ALTER TABLE esi_route_specs ADD COLUMN IF NOT EXISTS {col} VARCHAR")
                    logger.debug("[ESICache] Added new column esi_route_specs.%s", col)
                except Exception as exc:
                    logger.debug("[ESICache] Could not add column %s: %s", col, exc)


def seed_route_specs(con) -> int:
    """Upsert all seed rows into ``esi_route_specs``.

    Idempotent — safe to call every startup.  Returns the number of rows upserted.
    """
    try:
        from core.esi.generated.cache_ddl import (  # type: ignore[import]
            ROUTE_SPECS_SEED_ROWS,
            SPEC_COLUMN_NAMES,
        )
    except ImportError:
        logger.debug("[ESICache] cache_ddl.py not found — skipping seed.")
        return 0

    if not ROUTE_SPECS_SEED_ROWS:
        return 0

    cols = SPEC_COLUMN_NAMES
    placeholders = ", ".join("?" for _ in cols)
    col_list = ", ".join(cols)
    # Exclude the PK from ON CONFLICT SET clause.
    update_set = ", ".join(
        f"{c} = excluded.{c}" for c in cols if c != "operation_id"
    )

    sql = (
        f"INSERT INTO esi_route_specs ({col_list}) VALUES ({placeholders}) "
        f"ON CONFLICT (operation_id) DO UPDATE SET {update_set}"
    )
    rows = [[row.get(c) for c in cols] for row in ROUTE_SPECS_SEED_ROWS]
    con.executemany(sql, rows)
    return len(rows)


# ── Runtime cache operations ──────────────────────────────────────────────────

def check(cache_key: str) -> dict[str, Any] | None:
    """Return a cached response row (as dict) if it exists and has not expired.

    Uses a fresh DuckDB connection per call (thread-safe read).
    Returns ``None`` on miss, expiry, or any error.
    """
    try:
        from core.db import publicDB
        con = publicDB.connect()
        try:
            row = con.execute(
                "SELECT * FROM esi_cache WHERE cache_key = ? AND expires_at > now()",
                [cache_key],
            ).fetchone()
            if row is None:
                return None
            desc = con.description
            return {desc[i][0]: row[i] for i in range(len(desc))}
        finally:
            con.close()
    except Exception as exc:
        logger.debug("[ESICache] check() error: %s", exc)
        return None


def store(
    cache_key: str,
    operation_id: str | None,
    method: str,
    full_url: str,
    params: dict | None,
    response_body: str,
    status_code: int,
    ttl: int,
    headers: dict,
) -> None:
    """Persist a successful ESI response to ``esi_cache`` via the writer thread.

    Expired rows are pruned in the same write batch before the INSERT.
    Both writes are fire-and-forget so callers (e.g. the ESI rate limiter) are
    not blocked waiting for disk I/O on every cached response.
    """
    from core.db.writer import db_write_nowait

    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(seconds=ttl)).isoformat()
    fetched_at = now.isoformat()
    params_json = json.dumps(sorted((params or {}).items()), separators=(",", ":"))

    etag = headers.get("ETag") or headers.get("etag") or ""
    last_modified = headers.get("Last-Modified") or headers.get("last-modified") or ""
    rl_group = headers.get("X-Ratelimit-Group") or ""
    rl_remaining = _int_header(headers, "X-Ratelimit-Remaining")
    rl_used = _int_header(headers, "X-Ratelimit-Used")
    rl_limit_str = headers.get("X-Ratelimit-Limit") or ""
    retry_after = _int_header(headers, "Retry-After")
    x_pages = _int_header(headers, "X-Pages")
    x_esi_err_remain = _int_header(headers, "X-ESI-Error-Limit-Remain")
    x_esi_err_reset = _int_header(headers, "X-ESI-Error-Limit-Reset")

    # Prune expired rows first (best-effort — ignore errors).
    db_write_nowait("DELETE FROM esi_cache WHERE expires_at < now()", [])

    db_write_nowait(
        """
        INSERT INTO esi_cache (
            cache_key, operation_id, method, full_url, params_json,
            etag, last_modified, response_body, status_code,
            fetched_at, expires_at,
            rl_group, rl_remaining, rl_used, rl_limit_str,
            retry_after, x_pages, x_esi_error_limit_remain, x_esi_error_limit_reset
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (cache_key) DO UPDATE SET
            response_body = excluded.response_body,
            status_code = excluded.status_code,
            fetched_at = excluded.fetched_at,
            expires_at = excluded.expires_at,
            etag = excluded.etag,
            last_modified = excluded.last_modified,
            rl_group = excluded.rl_group,
            rl_remaining = excluded.rl_remaining,
            rl_used = excluded.rl_used,
            rl_limit_str = excluded.rl_limit_str,
            retry_after = excluded.retry_after,
            x_pages = excluded.x_pages,
            x_esi_error_limit_remain = excluded.x_esi_error_limit_remain,
            x_esi_error_limit_reset = excluded.x_esi_error_limit_reset
        """,
        [
            cache_key, operation_id, method, full_url, params_json,
            etag, last_modified, response_body, status_code,
            fetched_at, expires_at,
            rl_group, rl_remaining, rl_used, rl_limit_str,
            retry_after, x_pages, x_esi_err_remain, x_esi_err_reset,
        ],
    )


def refresh_ttl(cache_key: str, ttl: int) -> None:
    """Extend ``expires_at`` for an existing cache row (called on HTTP 304 responses)."""
    from core.db.writer import db_write

    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat()
    db_write(
        "UPDATE esi_cache SET expires_at = ? WHERE cache_key = ?",
        [expires_at, cache_key],
    )


def update_route_rl(operation_id: str, headers: dict) -> None:
    """Update live rate-limit columns on ``esi_route_specs`` from response headers.

    Called after every real ESI response to keep the live state current.
    """
    if not operation_id:
        return
    rl_remaining = _int_header(headers, "X-Ratelimit-Remaining")
    rl_used = _int_header(headers, "X-Ratelimit-Used")
    rl_limit_str = headers.get("X-Ratelimit-Limit") or ""
    if rl_remaining is None and rl_used is None and not rl_limit_str:
        return  # No rate-limit headers on this response — skip update.

    from core.db.writer import db_write

    db_write(
        """
        UPDATE esi_route_specs
        SET rl_remaining = ?,
            rl_used = ?,
            rl_limit_str = ?,
            rl_updated_at = now()
        WHERE operation_id = ?
        """,
        [rl_remaining, rl_used, rl_limit_str, operation_id],
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _int_header(headers: dict, key: str) -> int | None:
    """Parse an integer from an HTTP response header value; return None on failure."""
    value = headers.get(key)
    if value is None:
        return None
    try:
        return int(float(str(value).split(",")[0].split("/")[0].strip()))
    except (ValueError, TypeError):
        return None
