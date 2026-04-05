# applications/dashboard/routes.py
"""Dashboard blueprint — character overview page."""

from __future__ import annotations

import logging

import jwt
from flask import Blueprint, redirect, render_template, session, url_for

from applications._api import base_ctx, require_role
from applications._api import char_data, esi_registry

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__, template_folder="templates", static_folder="static")


def _decode_scope(access_token: str) -> str:
    """Extract scope claim from a JWT access token without verifying the signature."""
    try:
        decoded = jwt.decode(access_token, options={"verify_signature": False})
        scp = decoded.get("scp", "")
        return scp if isinstance(scp, str) else " ".join(scp or [])
    except Exception:
        return ""


@dashboard_bp.route("/", strict_slashes=False)
@require_role("dashboard")
def home():
    owner_id = session.get("owner_id")
    if not owner_id or owner_id <= 0:
        session.clear()
        return redirect(url_for("auth.login"))

    # Validate that this owner still has at least one character in our DB.
    # Stale cookies from old sessions / test runs can have non-existent owner IDs.
    try:
        char_exists = char_data.get_character(owner_id, owner_id) is not None
    except Exception:
        char_exists = False

    if not char_exists:
        session.clear()
        return redirect(url_for("auth.login"))

    esi_status = esi_registry.get_status()

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
