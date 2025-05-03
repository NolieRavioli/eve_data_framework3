# webUI/auth.py

import os
import requests
import logging
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

@auth_bp.route("/login")
def login():
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    client_id, _, redirect_uri, scopes = CredentialManager.load_credentials()
    eve = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scopes.split())
    auth_url, state = eve.authorization_url(AUTH_URL)
    session["oauth_state"] = state
    return redirect(auth_url)

@auth_bp.route("/add_toon")
def add_toon():
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    client_id, _, redirect_uri, scopes = CredentialManager.load_credentials()
    eve = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scopes.split())
    auth_url, state = eve.authorization_url(AUTH_URL)
    session["oauth_state"] = state
    session["add_toon"] = True
    return redirect(auth_url)

@auth_bp.route("/callback")
def callback():
    try:
        client_id, client_secret, redirect_uri, scopes = CredentialManager.load_credentials()
        state = session.pop("oauth_state", None)
        if not state:
            return "Session expired or missing state.", 400

        is_add_toon = session.pop("add_toon", False)
        eve = OAuth2Session(client_id, redirect_uri=redirect_uri, state=state)

        token = eve.fetch_token(
            TOKEN_URL,
            authorization_response=request.url,
            auth=HTTPBasicAuth(client_id, client_secret)
        )

        decoded = jwt.decode(token["access_token"], options={"verify_signature": False})
        character_id = int(decoded["sub"].split(":")[-1])

        if is_add_toon:
            owner_id = session.get("owner_id")
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
