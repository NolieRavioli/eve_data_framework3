# webUI/auth.py

import os
import time
import secrets
import requests
import logging
from threading import Lock
from typing import Optional
from flask import Blueprint, redirect, request, session, url_for
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session
import jwt

from util.auth import CredentialManager, TokenDBManager

from db.database import (
    initialize_private_database,
    initialize_public_database,
    get_private_session
)
from db.models import User, Character

# ─────── Globals ─────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)

TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
AUTH_URL = "https://login.eveonline.com/v2/oauth/authorize"

# ─────── Routes ──────────────────────────────────────────────────────────────

# Simple in-memory cache for issued OAuth states. This keeps callbacks working
# even if the user's browser does not resend the Flask session cookie (for
# example when switching between 127.0.0.1 and localhost).
_state_store = {}
_state_lock = Lock()
_STATE_TTL = 300  # seconds


def _store_state(state: str, *, is_add_toon: bool, owner_id: Optional[int]):
    with _state_lock:
        _state_store[state] = {
            "created": time.time(),
            "is_add_toon": is_add_toon,
            "owner_id": owner_id,
        }


def _pop_state(state: str):
    cutoff = time.time() - _STATE_TTL
    with _state_lock:
        # prune expired entries
        expired = [key for key, value in _state_store.items() if value["created"] < cutoff]
        for key in expired:
            _state_store.pop(key, None)
        return _state_store.pop(state, None)


def _issue_state(eve_session: OAuth2Session, *, is_add_toon: bool):
    # Create our own state token so we can look it up later even without the
    # client returning a Flask session cookie.
    manual_state = secrets.token_urlsafe(32)
    auth_url, _ = eve_session.authorization_url(AUTH_URL, state=manual_state)
    session["oauth_state"] = manual_state
    session["add_toon"] = is_add_toon

    owner_id = session.get("owner_id") if is_add_toon else None
    _store_state(manual_state, is_add_toon=is_add_toon, owner_id=owner_id)
    return auth_url, manual_state


@auth_bp.route("/login")
def login():
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    client_id, _, redirect_uri, scopes = CredentialManager.load_credentials()
    eve = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scopes.split())
    auth_url, _ = _issue_state(eve, is_add_toon=False)
    return redirect(auth_url)

@auth_bp.route("/add_toon")
def add_toon():
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    if not session.get("owner_id"):
        return "Error: No owner session found for adding toon.", 400

    client_id, _, redirect_uri, scopes = CredentialManager.load_credentials()
    eve = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scopes.split())
    auth_url, _ = _issue_state(eve, is_add_toon=True)
    return redirect(auth_url)

@auth_bp.route("/callback")
def callback():
    try:
        client_id, client_secret, redirect_uri, scopes = CredentialManager.load_credentials()
        returned_state = request.args.get("state")
        if not returned_state:
            return "Missing OAuth state.", 400

        session_state = session.pop("oauth_state", None)
        if session_state and session_state != returned_state:
            return "State mismatch detected.", 400

        cached_state = _pop_state(returned_state)
        if not session_state and not cached_state:
            return "Session expired or missing state.", 400

        is_add_toon = session.pop("add_toon", False)
        if cached_state:
            is_add_toon = cached_state["is_add_toon"]
            cached_owner = cached_state.get("owner_id")
        else:
            cached_owner = None

        eve = OAuth2Session(client_id, redirect_uri=redirect_uri, state=returned_state)

        token = eve.fetch_token(
            TOKEN_URL,
            authorization_response=request.url,
            auth=HTTPBasicAuth(client_id, client_secret)
        )

        decoded = jwt.decode(token["access_token"], options={"verify_signature": False})
        character_id = int(decoded["sub"].split(":")[-1])

        if is_add_toon:
            owner_id = session.get("owner_id") or cached_owner
            if not owner_id:
                return "Error: No owner session found for adding toon.", 400
        else:
            owner_id = character_id
            session["owner_id"] = owner_id
            session["character_id"] = character_id

        mgr = TokenDBManager(owner_id)
        mgr.save_tokens(
            character_id,
            token["access_token"],
            token["refresh_token"],
            token["expires_at"],
            token.get("scope", "")
        )

        session["access_token"] = token["access_token"]
        session["refresh_token"] = token["refresh_token"]

        return redirect(url_for("dashboard.home"))

    except Exception as e:
        logger.exception("[Auth] Error during authentication callback")
        return f"Authentication failed: {e}", 500

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("dashboard.home"))
