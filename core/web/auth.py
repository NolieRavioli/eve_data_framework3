# core/web/auth.py
"""SSO authentication blueprint and shared access-control decorators.

This module is *infrastructure*, not an application:
  - ``auth_bp`` handles the OAuth2 flow (/login, /callback, /logout, /add_toon,
    /switch_character).
  - ``require_admin`` and ``require_login`` decorators are imported by
    application blueprints that need access control.
"""

import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from functools import wraps
from threading import Lock
from typing import Dict, Optional

import jwt
from flask import Blueprint, abort, redirect, request, session, url_for
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session

from core.db.privateDB import get_private_session
from core.db.models import Character
import core.db.publicDB as sde_store
from core.esi.auth import CredentialManager, TokenDBManager
from config import RuntimeSettings, get_runtime_settings

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)

TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
AUTH_URL  = "https://login.eveonline.com/v2/oauth/authorize"


# ── Access-control decorators ────────────────────────────────────────────────

def require_login(fn):
    """Redirect unauthenticated users to the login page."""
    @wraps(fn)
    def _inner(*args, **kwargs):
        if "owner_id" not in session:
            return redirect(url_for("auth.login"))
        return fn(*args, **kwargs)
    return _inner


def require_admin(fn):
    """Return 403 for non-admin users."""
    @wraps(fn)
    def _inner(*args, **kwargs):
        if not session.get("is_admin"):
            abort(403)
        return fn(*args, **kwargs)
    return _inner


def require_role(role: str):
    """Require an authenticated session with the named role (or admin privilege).

    - site_owner / site_admin bypass the role check entirely.
    - Users must hold *role* in their session roles to proceed.
    - Page requests (Accept: text/html) are redirected to login when unauthenticated;
      API/SSE requests receive HTTP 401.
    """
    def decorator(fn):
        @wraps(fn)
        def _inner(*args, **kwargs):
            if "owner_id" not in session:
                from flask import request as _req
                if "text/html" in _req.headers.get("Accept", ""):
                    return redirect(url_for("auth.login"))
                abort(401)
            # site_admin and site_owner bypass named-role checks
            if session.get("is_admin"):
                return fn(*args, **kwargs)
            # Lazy-load roles from DB for sessions predating this system
            if "roles" not in session:
                session["roles"] = sde_store.get_user_roles(session["owner_id"])
            if not role or role in session.get("roles", []):
                return fn(*args, **kwargs)
            abort(403)
        return _inner
    return decorator


# ── Default-role helper ───────────────────────────────────────────────────────

_cached_default_roles: list[str] | None = None


def _get_default_roles() -> list[str]:
    """Return the default roles for new users, read once from config.yaml."""
    global _cached_default_roles
    if _cached_default_roles is None:
        try:
            from config import load_config, CONFIG_PATH
            cfg = load_config(CONFIG_PATH)
            _cached_default_roles = list(cfg.get("Auth", {}).get("default_roles", ["dashboard", "queue"]))
        except Exception:
            _cached_default_roles = ["dashboard", "queue"]
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
    auth_url, _ = eve_session.authorization_url(AUTH_URL, state=manual_state)
    session["oauth_state"] = manual_state
    session["add_toon"]    = is_add_toon

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

    session_state = session.pop("oauth_state", None)
    cached        = _state_cache.consume(returned_state)

    if session_state and session_state != returned_state:
        return None, None, ("State mismatch detected.", 400)

    if not session_state and not cached:
        return None, None, ("Session expired or missing state.", 400)

    is_add_toon = session.pop("add_toon", False)
    owner_hint  = None
    if cached is not None:
        is_add_toon = cached.is_add_toon
        owner_hint  = cached.owner_id

    if _settings.debug_mode:
        print(
            f"[Auth] State validated. add_toon={is_add_toon} "
            f"owner_hint={owner_hint} session_state={session_state}"
        )

    return is_add_toon, owner_hint, None


# ── Routes ───────────────────────────────────────────────────────────────────

@auth_bp.route("/login")
def login():
    if _settings.debug_mode:
        print("[Auth] Login requested; permitting insecure transport for local dev.")
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    return redirect(_prepare_oauth_session(is_add_toon=False))


@auth_bp.route("/add_toon")
def add_toon():
    if not session.get("owner_id"):
        return "Error: No owner session found for adding toon.", 400
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    return redirect(_prepare_oauth_session(is_add_toon=True))


@auth_bp.route("/switch_character/<int:character_id>")
def switch_character(character_id: int):
    owner_id = session.get("owner_id")
    if not owner_id:
        return redirect(url_for("auth.login"))

    db = get_private_session(owner_id)
    try:
        char = db.get(Character, character_id)
        if not char:
            return "Character not linked to this owner.", 404
    finally:
        db.close()

    session["character_id"] = character_id
    next_url = request.args.get("next") or url_for("dashboard.home")
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
            TOKEN_URL,
            authorization_response=request.url,
            auth=HTTPBasicAuth(client_id, client_secret),
        )

        decoded      = jwt.decode(token["access_token"], options={"verify_signature": False})
        character_id = int(decoded["sub"].split(":")[-1])

        if _settings.debug_mode:
            print(
                f"[Auth] Token received for character {character_id}. "
                f"Scopes={token.get('scope')}"
            )

        if is_add_toon:
            owner_id = session.get("owner_id") or owner_hint
            if not owner_id:
                return "Error: No owner session found for adding toon.", 400
        else:
            owner_id = character_id
            session["owner_id"]    = owner_id
            session["character_id"] = character_id

        is_first_owner = (sde_store.count_public_owners() == 0) and not is_add_toon

        db = get_private_session(owner_id)
        try:
            db.get(Character, character_id)  # validates character exists
        finally:
            db.close()

        mgr = TokenDBManager(owner_id)
        mgr.save_tokens(
            character_id,
            token["access_token"],
            token["refresh_token"],
            token["expires_at"],
            token.get("scope", ""),
        )

        session["access_token"]  = token["access_token"]
        session["refresh_token"] = token["refresh_token"]

        # Grant default roles to brand-new non-site-owner users
        if not is_add_toon and not is_first_owner:
            if not sde_store.get_user_roles(owner_id):
                sde_store.grant_user_roles(owner_id, _get_default_roles())

        if is_first_owner:
            sde_store.upsert_site_admin(owner_id=owner_id, is_site_owner=True, granted_by=None)
            logger.info("[Auth] Owner %s assigned as site owner (first login).", owner_id)

        if not is_add_toon:
            admin_record = sde_store.get_site_admin(owner_id)
            session["is_admin"]      = admin_record is not None
            session["is_site_owner"] = bool(admin_record and admin_record.get("is_site_owner"))
            session["roles"]         = sde_store.get_user_roles(owner_id)

        if _settings.debug_mode:
            print(
                f"[Auth] Session updated owner={owner_id} "
                f"is_admin={session.get('is_admin')} "
                f"characters={[session.get('character_id')]}"
            )

        return redirect(url_for("dashboard.home"))

    except Exception as exc:  # pragma: no cover - diagnostic path
        logger.exception("[Auth] Error during authentication callback")
        return f"Authentication failed: {exc}", 500


@auth_bp.route("/logout")
def logout():
    session.clear()
    if _settings.debug_mode:
        print("[Auth] Session cleared via logout.")
    return redirect(url_for("dashboard.home"))
