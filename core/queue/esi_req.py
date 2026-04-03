"""Centralised ESI request buffering with floating window rate limiting support."""

import logging
import re
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests
from requests import Request, Response
from requests.structures import CaseInsensitiveDict

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_SECONDS = 15 * 60  # 15 minutes — fallback when no X-Ratelimit-Limit header received yet.
_CACHE_LOCK = threading.Lock()

_CacheKey = Tuple[str, str, bytes, Optional[str]]
_CACHE: dict[_CacheKey, tuple[float, dict]] = {}


def _resolve_cache_ttl(method: str, url: str) -> Optional[int]:
    """Return cache TTL in seconds for a URL using spec-driven data, or None if not cacheable.

    Delegates to ``core.esi.cache.get_ttl_for_url`` which reads from the
    generated ``ROUTE_SPECS_SEED_ROWS``.  Falls back gracefully when the
    generated file is missing (pre-build.py state).
    """
    if method.upper() != "GET":
        return None
    try:
        from core.esi import cache as _esi_cache  # lazy import — avoids circular startup
        ttl, _ = _esi_cache.get_ttl_for_url(url)
        return ttl
    except Exception:
        return None


def _prepare_cache_key(method: str, url: str, kwargs: dict) -> tuple[requests.PreparedRequest, Optional[_CacheKey], Optional[int]]:
    headers = kwargs.get("headers") or {}
    req = Request(
        method=method,
        url=url,
        headers=headers,
        params=kwargs.get("params"),
        data=kwargs.get("data"),
        json=kwargs.get("json"),
    )
    prepared = req.prepare()
    ttl = _resolve_cache_ttl(prepared.method, prepared.url)
    if not ttl:
        return prepared, None, None

    body = prepared.body or b""
    if isinstance(body, str):
        body = body.encode("utf-8")

    cache_key: _CacheKey = (
        prepared.method,
        prepared.url,
        body,
        headers.get("Authorization"),
    )
    return prepared, cache_key, ttl


def _build_cached_response(payload: dict, prepared: requests.PreparedRequest) -> Response:
    resp = Response()
    resp.status_code = payload.get("status_code", 0)
    resp._content = payload.get("content", b"")
    resp.headers = CaseInsensitiveDict(payload.get("headers", {}))
    resp.encoding = payload.get("encoding")
    resp.reason = payload.get("reason")
    resp.url = payload.get("url", prepared.url)
    resp.request = prepared
    return resp


def _get_cached_response(key: _CacheKey, prepared: requests.PreparedRequest) -> Optional[Response]:
    now = time.time()
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if not entry:
            return None
        expiry, payload = entry
        if expiry <= now:
            return None   # stale entry kept in _CACHE for ETag revalidation via _get_cache_entry
    return _build_cached_response(payload, prepared)


def _store_cached_response(
    key: _CacheKey,
    response: requests.Response,
    ttl: int,
    prepared: requests.PreparedRequest,
) -> None:
    payload = {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "content": response.content,
        "encoding": response.encoding,
        "reason": response.reason,
        "url": response.url or prepared.url,
    }
    expires = time.time() + ttl
    with _CACHE_LOCK:
        _CACHE[key] = (expires, payload)


def _get_cache_entry(key: _CacheKey) -> Optional[tuple[float, dict]]:
    """Return the raw cache entry for *key* even if expired (used for ETag harvesting)."""
    with _CACHE_LOCK:
        return _CACHE.get(key)


def _refresh_cache_ttl(key: _CacheKey, ttl: int) -> None:
    """Reset the expiry on an existing cache entry without changing its payload (called on 304)."""
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if entry:
            _CACHE[key] = (time.time() + ttl, entry[1])


def _effective_ttl(headers: dict, fallback_ttl: int) -> int:
    """Return the best cache TTL in seconds derived from the ``Expires`` response
    header.  Falls back to *fallback_ttl* (from routes.json ``cache_age``) when
    the header is absent, unparseable, or already in the past."""
    expires_str = headers.get("Expires") or headers.get("expires")
    if expires_str:
        try:
            expires_dt = parsedate_to_datetime(expires_str)
            delta = int((expires_dt - datetime.now(timezone.utc)).total_seconds())
            if delta > 0:
                return delta
        except Exception:
            pass
    return fallback_ttl





# ESI endpoints that never return an X-Ratelimit-Group header are statically
# mapped here so they appear under a named group in get_stats() rather than
# being lumped into the catch-all "(ungrouped)" default bucket.
_STATIC_URL_GROUPS: tuple[tuple[str, str], ...] = (
    ("/latest/markets/structures/{id}/",  "esi-markets.structure_markets.v1"),
    ("/latest/universe/structures/{id}/", "esi-universe.read_structures.v1"),
)


class EsiRateLimiter:
    """Serialize ESI requests through a single floating-window token bucket."""

    def __init__(
        self,
        *,
        max_retries: int = 5,
        default_retry_after: int = 2,
    ) -> None:
        self._max_retries = max(1, max_retries)
        self._default_retry_after = max(1, default_retry_after)
        self._requests_total = 0
        # Per-group rate-limit state keyed by X-Ratelimit-Group header value.
        # Each entry: {"remaining": int|None, "used": int|None, "limit": int, "window_seconds": int, "window_str": str}
        self._groups_lock = threading.Lock()
        self._group_states: Dict[str, dict] = {}
        self._url_to_group: Dict[str, str] = {}   # normalised URL path → group name

        # Error-limit tracking (fixed-window, X-ESI-Error-Limit-Remain / X-ESI-Error-Limit-Reset)
        self._error_limit_lock = threading.Lock()
        self._error_limit_remain: Optional[int] = None
        self._error_limit_reset: Optional[int] = None

        # Pre-seed URL→group and group→limits from routes.json static data so
        # throttling is accurate from the very first request in each group.
        try:
            from core.esi.cache import get_static_rate_limit_seeds
            _path_to_group, _group_limits = get_static_rate_limit_seeds()
            for norm_path, group_name in _path_to_group.items():
                if norm_path not in self._url_to_group:
                    self._url_to_group[norm_path] = group_name
            for gname, gdata in _group_limits.items():
                if gname not in self._group_states:
                    self._group_states[gname] = gdata
            logger.debug(
                "[RateLimiter] Pre-seeded %d URL→group mappings, %d groups from routes.json",
                len(_path_to_group), len(_group_limits),
            )
        except Exception as _seed_exc:
            logger.debug("[RateLimiter] Rate-limit pre-seed skipped: %s", _seed_exc)

        # Pre-seed URL→group mapping for endpoints that don't return X-Ratelimit-Group headers.
        for norm_path, group_name in _STATIC_URL_GROUPS:
            self._url_to_group[norm_path] = group_name

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Perform an HTTP request against ESI obeying rate limits and retries."""

        attempt = 0
        lane = getattr(_request_lane, "lane", None)

        prepared, cache_key, ttl = _prepare_cache_key(method, url, kwargs)

        # Resolve operation_id for DuckDB cache bookkeeping.
        _duckdb_op_id: Optional[str] = None
        try:
            from core.esi import cache as _esi_cache
            _duckdb_op_id = _esi_cache._OP_MAP.get(_esi_cache._normalize_url_path(url))
        except Exception:
            pass

        if ttl and cache_key:
            # L1: in-memory cache check.
            cached = _get_cached_response(cache_key, prepared)
            if cached is not None:
                logger.debug("[RateLimiter] L1 cache hit for %s", prepared.url)
                return cached

            # L2: DuckDB persistent cache check.
            try:
                from core.esi import cache as _esi_cache
                _db_cache_key = _esi_cache.make_cache_key(
                    method, prepared.url,
                    kwargs.get("params"),
                    (kwargs.get("headers") or {}).get("Authorization"),
                )
                cached_row = _esi_cache.check(_db_cache_key)
                if cached_row is not None:
                    body_text = cached_row.get("response_body") or ""
                    payload = {
                        "status_code": cached_row.get("status_code", 200),
                        "headers": {
                            "ETag": cached_row.get("etag") or "",
                            "Last-Modified": cached_row.get("last_modified") or "",
                            "X-Pages": str(cached_row.get("x_pages") or ""),
                        },
                        "content": body_text.encode("utf-8") if isinstance(body_text, str) else body_text,
                        "encoding": "utf-8",
                        "reason": "OK (ESI Cache)",
                        "url": cached_row.get("full_url", prepared.url),
                    }
                    # Also warm the L1 in-memory cache for the remainder of this session.
                    _store_cached_response(cache_key, _build_cached_response(payload, prepared), ttl, prepared)
                    resp = _build_cached_response(payload, prepared)
                    logger.debug("[RateLimiter] L2 DuckDB cache hit for %s", prepared.url)
                    return resp
            except Exception as _dbc_exc:
                logger.debug("[RateLimiter] DuckDB cache check skipped: %s", _dbc_exc)

        retry_sleep: float = 0
        while True:
            attempt += 1
            if retry_sleep:
                time.sleep(retry_sleep)
                retry_sleep = 0

            if lane:
                _ALTERNATING_GATE.acquire(lane)
            try:
                # Throttle if the server last reported remaining == 0 for this URL's group.
                norm = self._normalize_url_path(url)
                with self._groups_lock:
                    gname = self._url_to_group.get(norm)
                    gstate = self._group_states.get(gname) if gname else None

                if gstate is not None and gstate.get("remaining") == 0:
                    limit = max(gstate.get("limit") or 1, 1)
                    window = gstate.get("window_seconds") or DEFAULT_WINDOW_SECONDS
                    time.sleep(window / limit)

                # Inject If-None-Match from a stale cache entry when available.
                if cache_key:
                    stale = _get_cache_entry(cache_key)
                    if stale:
                        _, stale_payload = stale
                        etag = (
                            stale_payload.get("headers", {}).get("ETag")
                            or stale_payload.get("headers", {}).get("etag")
                        )
                        if etag:
                            req_hdrs = dict(kwargs.get("headers") or {})
                            if "If-None-Match" not in req_hdrs:
                                req_hdrs["If-None-Match"] = etag
                                kwargs["headers"] = req_hdrs

                # Inject a default User-Agent if the caller did not supply one.
                req_hdrs = dict(kwargs.get("headers") or {})
                if not req_hdrs.get("User-Agent") and not req_hdrs.get("X-User-Agent"):
                    req_hdrs["User-Agent"] = "EVE-Data-Framework/4.0"
                    kwargs["headers"] = req_hdrs

                kwargs.setdefault("timeout", 30)
                response = requests.request(method, url, **kwargs)

                self._update_limits_from_headers(response.headers, url)

                if ttl and cache_key and 200 <= response.status_code < 300:
                    actual_ttl = _effective_ttl(dict(response.headers), ttl)
                    _store_cached_response(cache_key, response, actual_ttl, prepared)
                    # L2: persist to DuckDB (non-blocking via writer thread).
                    try:
                        from core.esi import cache as _esi_cache
                        _db_cache_key = _esi_cache.make_cache_key(
                            method, prepared.url,
                            kwargs.get("params"),
                            (kwargs.get("headers") or {}).get("Authorization"),
                        )
                        _esi_cache.store(
                            cache_key=_db_cache_key,
                            operation_id=_duckdb_op_id,
                            method=method,
                            full_url=prepared.url,
                            params=kwargs.get("params"),
                            response_body=response.text,
                            status_code=response.status_code,
                            ttl=actual_ttl,
                            headers=dict(response.headers),
                        )
                    except Exception as _dbs_exc:
                        logger.debug("[RateLimiter] DuckDB cache store skipped: %s", _dbs_exc)

                # 304 Not Modified: refresh cache TTL and return stored payload (1 token, already adjusted).
                if response.status_code == 304 and cache_key and ttl:
                    actual_ttl = _effective_ttl(dict(response.headers), ttl)
                    _refresh_cache_ttl(cache_key, actual_ttl)
                    # Also refresh DuckDB TTL.
                    try:
                        from core.esi import cache as _esi_cache
                        _db_cache_key = _esi_cache.make_cache_key(
                            method, prepared.url,
                            kwargs.get("params"),
                            (kwargs.get("headers") or {}).get("Authorization"),
                        )
                        _esi_cache.refresh_ttl(_db_cache_key, actual_ttl)
                    except Exception:
                        pass
                    stale = _get_cache_entry(cache_key)
                    if stale:
                        self._requests_total += 1
                        if _post_request_hook is not None:
                            try:
                                _post_request_hook(self.get_stats())
                            except Exception:
                                pass
                        return _build_cached_response(stale[1], prepared)

                if response.status_code == 429 and attempt < self._max_retries:
                    retry_after = self._parse_retry_after(response.headers.get("Retry-After"))
                    logger.warning(
                        "[RateLimiter] 429 received for %s %s. Sleeping %ss (attempt %s/%s)",
                        method.upper(),
                        url,
                        retry_after,
                        attempt,
                        self._max_retries,
                    )
                    retry_sleep = retry_after   # sleep AFTER releasing the gate
                    continue

                if response.status_code == 420 and attempt < self._max_retries:
                    reset_after = self._parse_retry_after(response.headers.get("X-ESI-Error-Limit-Reset"))
                    logger.warning(
                        "[RateLimiter] 420 error limit breach for %s %s. Sleeping %ss (attempt %s/%s)",
                        method.upper(),
                        url,
                        reset_after,
                        attempt,
                        self._max_retries,
                    )
                    retry_sleep = reset_after
                    continue

                self._requests_total += 1
                if _post_request_hook is not None:
                    try:
                        _post_request_hook(self.get_stats())
                    except Exception:
                        pass

                # Update live rate-limit columns in esi_route_specs (non-blocking).
                if _duckdb_op_id:
                    try:
                        from core.esi import cache as _esi_cache
                        _esi_cache.update_route_rl(_duckdb_op_id, dict(response.headers))
                    except Exception:
                        pass

                return response
            finally:
                if lane:
                    _ALTERNATING_GATE.release(lane)

    def _parse_retry_after(self, header_value: Optional[str]) -> int:
        if not header_value:
            return self._default_retry_after
        try:
            delay = int(float(header_value))
            return max(self._default_retry_after, delay)
        except (TypeError, ValueError):
            return self._default_retry_after

    def get_stats(self) -> dict:
        """Return per-group rate-limit stats sourced directly from ESI response headers."""
        with self._groups_lock:
            groups: dict = {
                gname: {
                    "group": gname,
                    "tokens_limit": gstate.get("limit") or 0,
                    "tokens_remaining": gstate.get("remaining"),
                    "tokens_used": gstate.get("used"),
                    "window_seconds": gstate.get("window_seconds", DEFAULT_WINDOW_SECONDS),
                    "window_str": gstate.get("window_str", ""),
                }
                for gname, gstate in self._group_states.items()
            }

        summary: dict = {}
        if groups:
            worst = min(
                groups.values(),
                key=lambda g: (g["tokens_remaining"] or 0) / max(g["tokens_limit"], 1) if g["tokens_limit"] else 1.0,
            )
            summary = dict(worst)

        summary["requests_total"] = self._requests_total
        summary["groups"] = groups
        with self._error_limit_lock:
            summary["error_limit_remain"] = self._error_limit_remain
            summary["error_limit_reset"] = self._error_limit_reset
        return summary

    @staticmethod
    def _normalize_url_path(url: str) -> str:
        """Return the URL path with numeric ID segments replaced by {id}."""
        return re.sub(r"/\d+", "/{id}", urlparse(url).path)

    @staticmethod
    def _parse_limit_header(value: str) -> "tuple[Optional[int], Optional[int]]":
        """Parse ESI's 'limit/window' header format, e.g. '150/15m' -> (150, 900)."""
        try:
            parts = value.strip().split("/", 1)
            limit = int(float(parts[0]))
            window_str = parts[1].strip() if len(parts) > 1 else ""
            if not window_str:
                return limit, DEFAULT_WINDOW_SECONDS
            if window_str.endswith("m"):
                return limit, int(window_str[:-1]) * 60
            if window_str.endswith("h"):
                return limit, int(window_str[:-1]) * 3600
            if window_str.endswith("s"):
                return limit, int(window_str[:-1])
            return limit, int(window_str)
        except (ValueError, IndexError):
            return None, None

    def _update_limits_from_headers(self, headers: Dict[str, str], url: Optional[str] = None) -> None:
        """Update per-group and error-limit state from ESI response headers."""

        # Error limit (fixed-window; headers are mutually exclusive with rate-limit bucket headers).
        err_remain = self._extract_int(headers, "X-ESI-Error-Limit-Remain")
        err_reset = self._extract_int(headers, "X-ESI-Error-Limit-Reset")
        if err_remain is not None or err_reset is not None:
            with self._error_limit_lock:
                if err_remain is not None:
                    self._error_limit_remain = err_remain
                if err_reset is not None:
                    self._error_limit_reset = err_reset
            if err_remain is not None and err_remain < 20:
                logger.warning(
                    "[RateLimiter] ESI error limit low: %s remaining (resets in %ss)",
                    err_remain, err_reset,
                )

        group = headers.get("X-Ratelimit-Group") or headers.get("X-Esi-Rate-Limit-Group")
        limit_str = (
            headers.get("X-Ratelimit-Limit")
            or headers.get("X-Esi-Rate-Limit-Limit")
        )
        if not group or not limit_str:
            return

        limit, window_seconds = self._parse_limit_header(limit_str)
        if limit is None:
            return

        remaining = self._extract_int(headers, "X-Ratelimit-Remaining")
        used = self._extract_int(headers, "X-Ratelimit-Used")
        parts = limit_str.strip().split("/", 1)
        window_str = parts[1].strip() if len(parts) > 1 else ""

        with self._groups_lock:
            is_new = group not in self._group_states
            self._group_states[group] = {
                "remaining": remaining,
                "used": used,
                "limit": limit,
                "window_seconds": window_seconds or DEFAULT_WINDOW_SECONDS,
                "window_str": window_str,
            }
            if is_new:
                logger.debug(
                    "[RateLimiter] New group: %s  limit=%s  window=%s",
                    group, limit, window_str or f"{window_seconds}s",
                )

            if url:
                norm = self._normalize_url_path(url)
                if self._url_to_group.get(norm) != group:
                    self._url_to_group[norm] = group
                    logger.debug("[RateLimiter] URL pattern %s -> group %s", norm, group)

    @staticmethod
    def _extract_int(headers: Dict[str, str], key: str) -> Optional[int]:
        value = headers.get(key)
        if value is None:
            return None
        try:
            # Some providers may supply comma-delimited values; use the first token.
            value = value.split(",")[0]
            # ESI may include a window suffix like "600/15m"; strip it.
            value = value.split("/")[0]
            return int(float(value.strip()))
        except (ValueError, TypeError):
            logger.debug("[RateLimiter] Failed to parse header %s=%s", key, value)
            return None


# ── Fair-alternating gate ────────────────────────────────────────────────────

class _FairAlternatingLock:
    """Ensures that when both 'public' and 'private' ESI threads are active
    simultaneously they take strict alternating turns.  When only one lane is
    active it proceeds without blocking."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last: Optional[str] = None            # lane that last completed
        self._active: dict = {"public": False, "private": False}
        self._ready: dict = {                       # signalled when other lane releases
            "public":  threading.Event(),
            "private": threading.Event(),
        }
        self._ready["public"].set()
        self._ready["private"].set()

    def acquire(self, lane: str) -> None:
        other = "private" if lane == "public" else "public"
        with self._lock:
            self._active[lane] = True
        while True:
            with self._lock:
                # Go freely if the other lane is idle or if we didn't go last
                if not self._active[other] or self._last != lane:
                    return
                self._ready[lane].clear()
            self._ready[lane].wait(timeout=2.0)   # other lane is waiting AND we went last

    def release(self, lane: str) -> None:
        other = "private" if lane == "public" else "public"
        with self._lock:
            self._last = lane
            self._active[lane] = False
            self._ready[other].set()


_ALTERNATING_GATE = _FairAlternatingLock()

# Thread-local used by task workers to declare which queue they belong to.
_request_lane: threading.local = threading.local()


def set_request_lane(lane: Optional[str]) -> None:
    """Declare the ESI lane for the current thread ('public', 'private', or None).
    Call once at the start of each worker thread before making any ESI requests."""
    _request_lane.lane = lane


_GLOBAL_LIMITER: Optional[EsiRateLimiter] = None
_GLOBAL_LOCK = threading.Lock()

# Optional callback fired after every real ESI request: fn(stats: dict) -> None
_post_request_hook: Optional[Callable] = None


def set_post_request_hook(fn) -> None:
    global _post_request_hook
    _post_request_hook = fn


def get_esi_rate_limiter() -> EsiRateLimiter:
    global _GLOBAL_LIMITER
    if _GLOBAL_LIMITER is None:
        with _GLOBAL_LOCK:
            if _GLOBAL_LIMITER is None:
                _GLOBAL_LIMITER = EsiRateLimiter()
    return _GLOBAL_LIMITER


def esi_request(method: str, url: str, **kwargs) -> requests.Response:
    """Execute an HTTP request routed through the shared ESI rate limiter."""

    limiter = get_esi_rate_limiter()
    return limiter.request(method, url, **kwargs)


def esi_get(url: str, **kwargs) -> requests.Response:
    return esi_request("GET", url, **kwargs)


def esi_post(url: str, **kwargs) -> requests.Response:
    return esi_request("POST", url, **kwargs)

