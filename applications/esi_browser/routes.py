# applications/esi_browser/routes.py
"""ESI Explorer blueprint — browse, search, and execute ESI operations."""

from __future__ import annotations

import logging

from flask import (
    Blueprint,
    abort,
    jsonify,
    render_template,
    request,
    session,
)

from applications._api import require_admin, base_ctx
from applications._api import esi, esi_manifest, char_data, tokens

logger = logging.getLogger(__name__)
esi_bp = Blueprint("esi_browser", __name__, template_folder="templates", static_folder="static")


@esi_bp.route("/")
@require_admin
def index():
    """Searchable catalog of all ESI operations."""
    ops = esi_manifest.get_operations()
    meta = esi_manifest.get_meta()

    char_name: str | None = None
    character_id = session.get("character_id")
    owner_id = session.get("owner_id")
    if character_id and owner_id:
        info = char_data.get_character(owner_id, character_id)
        if info:
            char_name = info.get("name")

    return render_template(
        "admin_esi.html",
        **base_ctx("esi_browser"),
        operations=ops,
        compatibility_date=meta["compatibility_date"],
        operation_count=meta["operation_count"],
        scope_count=meta["scope_count"],
        active_character_id=character_id,
        active_character_name=char_name,
    )


@esi_bp.route("/<operation_id>")
@require_admin
def detail(operation_id: str):
    """JSON detail for a single operation — used by the explorer JS."""
    op = esi_manifest.get_operation(operation_id)
    if not op:
        abort(404)
    return jsonify(op)


@esi_bp.route("/<operation_id>/run", methods=["POST"])
@require_admin
def run(operation_id: str):
    """Execute an ESI operation and return the response as JSON."""
    op = esi_manifest.get_operation(operation_id)
    if not op:
        return jsonify({"error": f"Unknown operation: {operation_id!r}"}), 404

    data = request.get_json(force=True, silent=True) or {}
    path_params = data.get("path_params") or {}
    query_params = data.get("query_params") or {}
    all_pages = bool(data.get("all_pages", False))

    token = None
    if op.get("requires_auth"):
        owner_id = session.get("owner_id")
        character_id = session.get("character_id")
        if owner_id and character_id:
            try:
                token_map = tokens.get(owner_id, character_ids=[character_id])
                row = token_map.get(character_id)
                if row:
                    token = row["access_token"]
            except Exception:
                pass
        if not token:
            return jsonify({"error": "Authentication required but no valid token is available for your session."}), 401

    try:
        if all_pages and op.get("pagination", {}).get("has_page_param"):
            result = esi.fetch_pages(
                operation_id,
                path_params=path_params or None,
                query_params=query_params or None,
                token=token,
            )
            return jsonify({
                "ok": True,
                "operation_id": operation_id,
                "all_pages": True,
                "count": len(result) if isinstance(result, list) else None,
                "data": result,
            })
        else:
            r = esi.execute(
                operation_id,
                path_params=path_params or None,
                query_params=query_params or None,
                token=token,
            )
            return jsonify({
                "ok": True,
                "operation_id": operation_id,
                "status_code": r["status_code"],
                "headers": {k: v for k, v in r["headers"].items()
                            if k.lower().startswith(("x-", "content-", "expires", "etag"))},
                "data": r["body"],
            })
    except Exception as exc:
        logger.exception("[ESI Explorer] Error running %s", operation_id)
        return jsonify({"error": str(exc)}), 500
