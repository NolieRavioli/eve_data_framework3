# webUI/context.py
"""Shared template context for the base layout (sidebar, character mini-card)."""

from flask import session
from db.database import get_private_session
from db.models import Character, WalletBalance


def base_ctx(active_page: str = "") -> dict:
    """Return context variables required by base.html for every page."""
    ctx = {
        "base_logged_in": False,
        "base_char_id": None,
        "base_char_name": "—",
        "base_wallet": 0.0,
        "base_is_admin": False,
        "active_page": active_page,
    }
    if "character_id" not in session or "owner_id" not in session:
        return ctx

    char_id = session["character_id"]
    owner_id = session["owner_id"]
    db = get_private_session(owner_id)
    try:
        char = db.get(Character, char_id)
        bal = db.query(WalletBalance).filter_by(character_id=char_id).first()
        ctx.update({
            "base_logged_in": True,
            "base_char_id": char_id,
            "base_char_name": (char.name if char else str(char_id)),
            "base_wallet": (bal.balance if bal else 0.0),
            "base_is_admin": bool(session.get("is_admin")),
        })
    finally:
        db.close()
    return ctx
