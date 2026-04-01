# applications/dashboard/routes.py
"""Dashboard blueprint — character overview page."""

from __future__ import annotations

import logging

import jwt
from flask import Blueprint, redirect, render_template, session, url_for

from core.db.privateDB import get_private_session
from core.db.models import Character
from core.esi.registry import get_registry_status
from core.web.context import base_ctx

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__)


def _decode_scope(access_token: str) -> str:
    """Extract scope claim from a JWT access token without verifying the signature."""
    try:
        decoded = jwt.decode(access_token, options={"verify_signature": False})
        scp = decoded.get("scp", "")
        return scp if isinstance(scp, str) else " ".join(scp or [])
    except Exception:
        return ""


@dashboard_bp.route("/")
def home():
    owner_id = session.get("owner_id")
    if not owner_id or owner_id <= 0:
        session.clear()
        return redirect(url_for("auth.login"))

    # Validate that this owner still has at least one character in our DB.
    # Stale cookies from old sessions / test runs can have non-existent owner IDs.
    try:
        db = get_private_session(owner_id)
        try:
            char_exists = db.query(Character).filter_by(character_id=owner_id).first() is not None
        finally:
            db.close()
    except Exception:
        char_exists = False

    if not char_exists:
        session.clear()
        return redirect(url_for("auth.login"))

    esi_status = get_registry_status()

    granted_scopes: list[str] = []
    access_token = session.get("access_token")
    if access_token:
        raw = _decode_scope(access_token)
        if raw:
            granted_scopes = sorted(raw.split())

    return render_template(
        "dashboard.html",
        **base_ctx("dashboard"),
        owner_id=session["owner_id"],
        character_id=session.get("character_id"),
        esi_status=esi_status,
        granted_scopes=granted_scopes,
        granted_scope_count=len(granted_scopes),
    )
