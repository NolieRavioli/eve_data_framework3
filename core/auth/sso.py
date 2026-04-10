"""EVE SSO OAuth2 flow — Blueprint routes and CSRF state management.

Routes: /login, /callback, /logout, /add_toon, /switch_character
"""

import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, Optional

import jwt
import requests as _requests
from jwt import PyJWKClient
from flask import Blueprint, abort, redirect, request, session, url_for
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session


from core.db.entity_db import connect_entity, ensure_character_table
from core.auth.credentials import CredentialManager
from core.auth.tokens import TokenDBManager
from core.auth import identity as _identity
from core.config import RuntimeSettings, get_runtime_settings

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)

# ── SSO endpoint discovery via well-known metadata ────────────────────────────

_WELL_KNOWN_URL = "https://login.eveonline.com/.well-known/oauth-authorization-server"

# Hardcoded fallback values (used if well-known endpoint is unreachable)
_FALLBACK_AUTH_URL  = "https://login.eveonline.com/v2/oauth/authorize"
_FALLBACK_TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
_FALLBACK_JWKS_URI  = "https://login.eveonline.com/oauth/jwks"
_FALLBACK_ISSUER    = "https://login.eveonline.com"

_sso_endpoints: dict | None = None
_sso_endpoints_ts: float = 0.0
_SSO_CACHE_TTL = 86400  # 24 hours
_sso_lock = Lock()


def _discover_sso_endpoints() -> dict:
    """Fetch SSO metadata from the well-known endpoint, cached for 24h."""
    global _sso_endpoints, _sso_endpoints_ts
    now = time.time()

    with _sso_lock:
        if _sso_endpoints and (now - _sso_endpoints_ts) < _SSO_CACHE_TTL:
            return _sso_endpoints

    try:
        resp = _requests.get(_WELL_KNOWN_URL, timeout=10)
        resp.raise_for_status()
        meta = resp.json()
        endpoints = {
            "authorization_endpoint": meta.get("authorization_endpoint", _FALLBACK_AUTH_URL),
            "token_endpoint": meta.get("token_endpoint", _FALLBACK_TOKEN_URL),
            "jwks_uri": meta.get("jwks_uri", _FALLBACK_JWKS_URI),
            "issuer": meta.get("issuer", _FALLBACK_ISSUER),
        }
        with _sso_lock:
            _sso_endpoints = endpoints
            _sso_endpoints_ts = now
        logger.info("[Auth] SSO endpoints refreshed from well-known metadata")
        return endpoints
    except Exception as exc:
        logger.warning("[Auth] Failed to fetch well-known metadata: %s — using fallback", exc)
        fallback = {
            "authorization_endpoint": _FALLBACK_AUTH_URL,
            "token_endpoint": _FALLBACK_TOKEN_URL,
            "jwks_uri": _FALLBACK_JWKS_URI,
            "issuer": _FALLBACK_ISSUER,
        }
        with _sso_lock:
            _sso_endpoints = fallback
            _sso_endpoints_ts = now
        return fallback


def _get_auth_url() -> str:
    return _discover_sso_endpoints()["authorization_endpoint"]


def _get_token_url() -> str:
    return _discover_sso_endpoints()["token_endpoint"]


def _get_jwks_uri() -> str:
    return _discover_sso_endpoints()["jwks_uri"]


def _get_issuer() -> str:
    return _discover_sso_endpoints()["issuer"]


_jwks_client: PyJWKClient | None = None
_jwks_lock = Lock()


def _get_jwks_client() -> PyJWKClient:
    """Lazily initialise the JWKS client with the discovered URI."""
    global _jwks_client
    with _jwks_lock:
        if _jwks_client is None:
            _jwks_client = PyJWKClient(_get_jwks_uri(), cache_keys=True)
    return _jwks_client


# ── Default-role helper ───────────────────────────────────────────────────────

_cached_default_roles: list[str] | None = None


def _get_default_roles() -> list[str]:
    """Return the default roles for new users, read once from config.yaml."""
    global _cached_default_roles
    if _cached_default_roles is None:
        try:
            from core.config import get_auth_config
            _cached_default_roles = list(get_auth_config().get("default_roles", ["dashboard", "database", "sde", "tasks"]))
        except Exception:
            _cached_default_roles = ["dashboard", "database", "sde", "tasks"]
    return _cached_default_roles


# ── OAuth state cache ────────────────────────────────────────────────────────

@dataclass
class OAuthStateRecord:
    value: str
    is_add_toon: bool
    owner_id: Optional[int]
    created: float = field(default_factory=lambda: time.time())


class OAuthStateCache:
    def __init__(self, ttl_seconds: int, debug: bool = False):
        self._ttl = ttl_seconds
        self._store: Dict[str, OAuthStateRecord] = {}
        self._lock = Lock()
        self._debug = debug

    def remember(self, record: OAuthStateRecord) -> None:
        with self._lock:
            self._purge_locked()
            self._store[record.value] = record
            if self._debug:
                print(
                    f"[Auth] Remembered state {record.value} "
                    f"add_toon={record.is_add_toon} owner={record.owner_id}"
                )

    def consume(self, value: str) -> Optional[OAuthStateRecord]:
        with self._lock:
            self._purge_locked()
            record = self._store.pop(value, None)
            if self._debug:
                print(f"[Auth] Consumed state {value}: {record}")
            return record

    def _purge_locked(self) -> None:
        cutoff = time.time() - self._ttl
        expired = [key for key, rec in self._store.items() if rec.created < cutoff]
        for key in expired:
            self._store.pop(key, None)
        if expired and self._debug:
            print(f"[Auth] Purged expired states: {expired}")


def _build_state_cache(settings: RuntimeSettings) -> OAuthStateCache:
    ttl = 600 if settings.debug_mode else 300
    return OAuthStateCache(ttl_seconds=ttl, debug=settings.debug_mode)


_settings     = get_runtime_settings()
_state_cache  = _build_state_cache(_settings)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _issue_state(eve_session: OAuth2Session, *, is_add_toon: bool) -> str:
    manual_state = secrets.token_urlsafe(32)
    auth_url, _ = eve_session.authorization_url(_get_auth_url(), state=manual_state)

    owner_id = session.get("owner_id") if is_add_toon else None
    _state_cache.remember(OAuthStateRecord(manual_state, is_add_toon, owner_id))

    if _settings.debug_mode:
        print(f"[Auth] Issued state={manual_state} add_toon={is_add_toon} owner={owner_id}")

    return auth_url


def _prepare_oauth_session(is_add_toon: bool) -> str:
    client_id, _, redirect_uri, scopes = CredentialManager.load_credentials()
    eve      = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scopes.split())
    auth_url = _issue_state(eve, is_add_toon=is_add_toon)
    if _settings.debug_mode:
        print(f"[Auth] Redirecting to {auth_url}")
    return auth_url


def _validate_state(returned_state: Optional[str]):
    if not returned_state:
        return None, None, ("Missing OAuth state.", 400)

    # OAuthStateCache is the sole authority: 32-byte random token, single-use,
    # 5-minute TTL, server-side only.  This avoids breakage when the login page
    # is accessed via 127.0.0.1 but the EVE redirect_uri uses localhost (or vice
    # versa) — different cookie domains would cause the Flask session lookup to
    # fail even though the request is legitimate.
    cached = _state_cache.consume(returned_state)
    if cached is None:
        return None, None, ("State expired or invalid. Please try logging in again.", 400)

    if _settings.debug_mode:
        print(
            f"[Auth] State validated. add_toon={cached.is_add_toon} "
            f"owner_hint={cached.owner_id}"
        )

    return cached.is_add_toon, cached.owner_id, None


# ── Routes ───────────────────────────────────────────────────────────────────

@auth_bp.route("/login")
def login():
    if _settings.transport != "https":
        if _settings.debug_mode:
            print("[Auth] Login requested; permitting insecure transport for local dev.")
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    return redirect(_prepare_oauth_session(is_add_toon=False))


@auth_bp.route("/add_toon")
def add_toon():
    if not session.get("owner_id"):
        return "Error: No owner session found for adding toon.", 400
    if _settings.transport != "https":
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    return redirect(_prepare_oauth_session(is_add_toon=True))


@auth_bp.route("/switch_character/<int:character_id>")
def switch_character(character_id: int):
    owner_id = session.get("owner_id")
    if not owner_id:
        return redirect(url_for("auth.login"))

    con = connect_entity(owner_id)
    try:
        ensure_character_table(con)
        row = con.execute(
            "SELECT character_id FROM characters WHERE character_id = ?",
            [character_id],
        ).fetchone()
        if not row:
            return "Character not linked to this owner.", 404
    finally:
        con.close()

    session["character_id"] = character_id
    next_key = request.args.get("next", "")
    allowed_next = {
        "dashboard": url_for("dashboard.home"),
        "home": url_for("home.index"),
    }
    next_url = allowed_next.get(next_key, url_for("dashboard.home"))
    return redirect(next_url)


@auth_bp.route("/callback")
def callback():
    try:
        returned_state = request.args.get("state")
        is_add_toon, owner_hint, error = _validate_state(returned_state)
        if error:
            return error

        client_id, client_secret, redirect_uri, _ = CredentialManager.load_credentials()
        eve   = OAuth2Session(client_id, redirect_uri=redirect_uri, state=returned_state)
        token = eve.fetch_token(
            _get_token_url(),
            authorization_response=request.url,
            auth=HTTPBasicAuth(client_id, client_secret),
        )

        try:
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token["access_token"])
            decoded = jwt.decode(
                token["access_token"],
                signing_key.key,
                algorithms=["RS256"],
                issuer=_get_issuer(),
                audience=[client_id, "EVE Online"],
            )
        except jwt.exceptions.PyJWKClientError:
            if _settings.debug_mode:
                logger.warning("[Auth] JWKS fetch failed — falling back to unverified JWT decode (debug mode)")
                decoded = jwt.decode(token["access_token"], options={"verify_signature": False})
            else:
                logger.error("[Auth] JWKS fetch failed — rejecting authentication")
                return "Authentication failed: unable to verify token signature.", 500
        character_id = int(decoded["sub"].split(":")[-1])

        raw_scp = decoded.get("scp", [])
        scopes_str = " ".join(raw_scp) if isinstance(raw_scp, list) else str(raw_scp or "")

        if _settings.debug_mode:
            print(
                f"[Auth] Token received for character {character_id}. "
                f"Scopes={scopes_str[:120]}"
            )

        if is_add_toon:
            owner_id = session.get("owner_id") or owner_hint
            if not owner_id:
                return "Error: No owner session found for adding toon.", 400
        else:
            owner_id = character_id
            session["owner_id"]    = owner_id
            session["character_id"] = character_id

        is_first_owner = (_identity.count_public_owners() == 0) and not is_add_toon

        # Ensure entity DB and characters table exist for this owner
        con = connect_entity(owner_id)
        try:
            ensure_character_table(con)
        finally:
            con.close()

        mgr = TokenDBManager(owner_id)
        mgr.save_tokens(
            character_id,
            token["access_token"],
            token["refresh_token"],
            token["expires_at"],
            scopes_str,
        )

        # Grant default roles to brand-new non-site-owner users
        if not is_add_toon and not is_first_owner:
            if not _identity.get_user_roles(owner_id):
                _identity.grant_user_roles(owner_id, _get_default_roles())

        if is_first_owner:
            _identity.upsert_site_admin(owner_id=owner_id, is_site_owner=True, granted_by=None)
            logger.info("[Auth] Owner %s assigned as site owner (first login).", owner_id)

        if not is_add_toon:
            admin_record = _identity.get_site_admin(owner_id)
            session["is_admin"]      = admin_record is not None
            session["is_site_owner"] = bool(admin_record and admin_record.get("is_site_owner"))
            session["roles"]         = _identity.get_user_roles(owner_id)

        # Kick off full character data collection for this owner
        from core.tasks.queue import enqueue as _enqueue
        from collectors.character.extended import run_extended_refresh
        _enqueue(
            "Character Full Refresh",
            run_extended_refresh,
            owner_id,
            owner_id=owner_id,
            queue="private",
        )

        if _settings.debug_mode:
            print(
                f"[Auth] Session updated owner={owner_id} "
                f"is_admin={session.get('is_admin')} "
                f"characters={[session.get('character_id')]}"
            )

        return redirect(url_for("dashboard.home"))

    except Exception:  # pragma: no cover - diagnostic path
        logger.exception("[Auth] Error during authentication callback")
        return "Authentication failed. Please try again.", 500


@auth_bp.route("/logout")
def logout():
    session.clear()
    if _settings.debug_mode:
        print("[Auth] Session cleared via logout.")
    return redirect(url_for("home.index"))
