# core/web/context.py
"""Shared template context for the base layout (sidebar, character mini-card)."""

from flask import session
from core.io.entity_db import connect_entity, ensure_character_table


def base_ctx(active_page: str = "") -> dict:
    """Return context variables required by base.html for every page."""
    from applications import tool_registry
    ctx = {
        "base_logged_in":  False,
        "base_char_id":    None,
        "base_char_name":  "—",
        "base_wallet":     0.0,
        "base_is_admin":   False,
        "active_page":     active_page,
        "tool_nav":        tool_registry.nav_entries(),
        "tool_scope_ok":   tool_registry.check_scopes([]),
        "tool_access_ok":  tool_registry.check_access(),
    }
    if "character_id" not in session or "owner_id" not in session:
        return ctx

    char_id  = session["character_id"]
    owner_id = session["owner_id"]
    is_admin = bool(session.get("is_admin"))
    is_site_owner = bool(session.get("is_site_owner"))
    con = connect_entity(owner_id)
    try:
        ensure_character_table(con)
        row = con.execute(
            "SELECT name, scopes FROM characters WHERE character_id = ?",
            [char_id],
        ).fetchone()
        granted = (row[1] or "").split() if row else []
        ctx.update({
            "base_logged_in":  True,
            "base_char_id":    char_id,
            "base_char_name":  (row[0] if row else str(char_id)),
            "base_wallet":     0.0,
            "base_is_admin":   is_admin,
            "is_site_owner":   is_site_owner,
            "tool_nav":        tool_registry.nav_entries(),
            "tool_scope_ok":   tool_registry.check_scopes(granted),
            "tool_access_ok":  tool_registry.check_access(
                is_logged_in=True,
                is_admin=is_admin,
                is_site_owner=is_site_owner,
                roles=session.get("roles", []),
            ),
        })
    finally:
        con.close()
    return ctx
