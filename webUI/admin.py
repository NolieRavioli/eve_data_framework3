"""
Admin panel blueprint.
- Live console via Server-Sent Events (SSE)
- Database statistics
- User management (promote / demote site admins)
- DuckDB workspace browser (read-only)
"""

import collections
import datetime
import json
import logging
import threading
import time
from functools import wraps

from flask import (
    Blueprint,
    Response,
    abort,
    jsonify,
    render_template,
    request,
    session,
    stream_with_context,
)

from util import sde_store
from util.esi_spec_registry import get_registry_status

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


class _AdminLogHandler(logging.Handler):
    _buffer: collections.deque[tuple[int, str]] = collections.deque(maxlen=500)
    _cursor = 0
    _lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            with _AdminLogHandler._lock:
                _AdminLogHandler._cursor += 1
                _AdminLogHandler._buffer.append((_AdminLogHandler._cursor, line))
        except Exception:
            pass

    @classmethod
    def snapshot(cls, limit: int | None = None) -> list[tuple[int, str]]:
        with cls._lock:
            rows = list(cls._buffer)
        return rows[-limit:] if limit else rows

    @classmethod
    def lines_after(cls, cursor: int) -> list[tuple[int, str]]:
        with cls._lock:
            return [row for row in cls._buffer if row[0] > cursor]


_handler = _AdminLogHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logging.getLogger().addHandler(_handler)


def require_admin(fn):
    @wraps(fn)
    def _inner(*args, **kwargs):
        if not session.get("is_admin"):
            abort(403)
        return fn(*args, **kwargs)

    return _inner


def _is_site_owner(owner_id: int) -> bool:
    row = sde_store.get_site_admin(owner_id)
    return bool(row and row.get("is_site_owner"))


def _db_stats() -> dict[str, int]:
    counts = sde_store.public_table_counts()
    return dict(sorted(counts.items(), key=lambda item: item[1], reverse=True))


def _normalize_user_row(row: dict) -> dict:
    granted_at = row.get("granted_at")
    if isinstance(granted_at, (datetime.datetime, datetime.date)):
        granted_at = granted_at.isoformat()
    return {
        "owner_id": row["owner_id"],
        "character_count": int(row.get("character_count") or 0),
        "is_admin": bool(row.get("is_admin")),
        "is_site_owner": bool(row.get("is_site_owner")),
        "granted_at": granted_at,
    }


def _user_list() -> list[dict]:
    return [_normalize_user_row(row) for row in sde_store.list_public_users()]


@admin_bp.route("/")
@require_admin
def index():
    users = _user_list()
    table_counts = _db_stats()
    sde_status = sde_store.get_warehouse_status()
    esi_status = get_registry_status()
    stats = {
        "table_counts": table_counts,
        "table_count": len(table_counts),
        "table_total_rows": sum(table_counts.values()),
        "users": users,
        "total_owners": len(users),
        "admin_count": sum(1 for row in users if row["is_admin"]),
        "log_lines": [line for _, line in _AdminLogHandler.snapshot(limit=100)],
        "sde_status": sde_status,
        "esi_status": esi_status,
    }
    return render_template(
        "admin.html",
        stats=stats,
        owner_id=session.get("owner_id"),
        is_site_owner=_is_site_owner(session.get("owner_id", 0)),
    )


@admin_bp.route("/stream")
@require_admin
def stream():
    def _generate():
        cursor = 0
        initial = _AdminLogHandler.snapshot(limit=100)
        for cursor, line in initial:
            yield f"data: {json.dumps(line)}\n\n"

        while True:
            new_lines = _AdminLogHandler.lines_after(cursor)
            if new_lines:
                for cursor, line in new_lines:
                    yield f"data: {json.dumps(line)}\n\n"
            else:
                yield ": keep-alive\n\n"
            time.sleep(1.0)

    return Response(
        stream_with_context(_generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@admin_bp.route("/users")
@require_admin
def users():
    return jsonify(_user_list())


@admin_bp.route("/promote", methods=["POST"])
@require_admin
def promote():
    data = request.get_json(force=True, silent=True) or {}
    target_id = data.get("owner_id")
    if not target_id:
        return jsonify({"error": "owner_id required"}), 400

    current_owner = session.get("owner_id")
    existing = sde_store.get_site_admin(int(target_id))
    if existing:
        return jsonify({"ok": True, "note": "already admin"})

    sde_store.upsert_site_admin(
        owner_id=int(target_id),
        is_site_owner=False,
        granted_by=current_owner,
        granted_at=datetime.datetime.utcnow(),
    )
    logger.info("[Admin] Owner %s promoted to admin by %s.", target_id, current_owner)
    return jsonify({"ok": True})


@admin_bp.route("/demote", methods=["POST"])
@require_admin
def demote():
    data = request.get_json(force=True, silent=True) or {}
    target_id = data.get("owner_id")
    if not target_id:
        return jsonify({"error": "owner_id required"}), 400

    row = sde_store.get_site_admin(int(target_id))
    if not row:
        return jsonify({"ok": True, "note": "not an admin"})
    if row.get("is_site_owner"):
        return jsonify({"error": "Cannot demote the site owner."}), 403

    current_owner = session.get("owner_id")
    sde_store.delete_site_admin(int(target_id))
    logger.info("[Admin] Owner %s demoted by %s.", target_id, current_owner)
    return jsonify({"ok": True})


@admin_bp.route("/db_browser")
@require_admin
def db_browser():
    target_owner_id = request.args.get("owner_id", type=int)
    try:
        if target_owner_id is not None:
            tables = sde_store.list_private_browser_tables(target_owner_id)
            db_label = f"owner {target_owner_id} private db"
        else:
            tables = sde_store.list_browser_tables()
            db_label = "public.duckdb"
    except FileNotFoundError:
        abort(404)
    return render_template(
        "db_browser.html",
        tables=tables,
        db_label=db_label,
        browser_owner_id=target_owner_id,
    )


@admin_bp.route("/db_browser/query", methods=["POST"])
@require_admin
def db_browser_query():
    data = request.get_json(force=True, silent=True) or {}
    raw_sql = (data.get("sql") or "").strip()
    target_owner_id = data.get("owner_id")
    if not raw_sql:
        return jsonify({"error": "No SQL provided"}), 400

    try:
        if target_owner_id is not None:
            return jsonify(
                sde_store.query_private_browser_sql(
                    int(target_owner_id),
                    raw_sql,
                    row_limit=500,
                )
            )
        return jsonify(sde_store.query_browser_sql(raw_sql, row_limit=500))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


# ── ESI Explorer ────────────────────────────────────────────────────────────

@admin_bp.route("/esi")
@require_admin
def esi_catalog():
    """Searchable catalog of all 208 ESI operations."""
    from esi.generated.manifest import OPERATIONS, COMPATIBILITY_DATE, OPERATION_COUNT, ALL_SCOPES
    from db.database import get_private_session
    from db.models import Character

    ops = sorted(OPERATIONS.values(), key=lambda o: ((o.get("tags") or [""])[0], o.get("operation_id", "")))

    # Resolve the display name for the active session character so the template
    # can show whether authenticated operations will have a token available.
    char_name: str | None = None
    character_id = session.get("character_id")
    owner_id = session.get("owner_id")
    if character_id and owner_id:
        db = get_private_session(owner_id)
        try:
            char = db.get(Character, character_id)
            if char:
                char_name = char.name
        finally:
            db.close()

    return render_template(
        "admin_esi.html",
        operations=ops,
        compatibility_date=COMPATIBILITY_DATE,
        operation_count=OPERATION_COUNT,
        scope_count=len(ALL_SCOPES),
        active_character_id=character_id,
        active_character_name=char_name,
    )


@admin_bp.route("/esi/<operation_id>")
@require_admin
def esi_detail(operation_id: str):
    """JSON detail for a single operation — used by the explorer JS."""
    from esi.generated.manifest import OPERATIONS
    op = OPERATIONS.get(operation_id)
    if not op:
        abort(404)
    return jsonify(op)


@admin_bp.route("/esi/<operation_id>/run", methods=["POST"])
@require_admin
def esi_run(operation_id: str):
    """
    Execute an ESI operation immediately and return the response as JSON.
    Authenticated routes use the admin's own access token.
    """
    from esi.generated.manifest import OPERATIONS
    from esi.generated.client import execute_operation, fetch_all_pages

    op = OPERATIONS.get(operation_id)
    if not op:
        return jsonify({"error": f"Unknown operation: {operation_id!r}"}), 404

    data = request.get_json(force=True, silent=True) or {}
    path_params = data.get("path_params") or {}
    query_params = data.get("query_params") or {}
    all_pages = bool(data.get("all_pages", False))

    token = None
    if op.get("requires_auth"):
        from util.utils import get_token
        owner_id = session.get("owner_id")
        character_id = session.get("character_id")
        if owner_id and character_id:
            try:
                tokens = get_token(owner_id, character_ids=[character_id])
                row = tokens.get(character_id)
                if row:
                    token = row["access_token"]
            except Exception:
                pass
        if not token:
            return jsonify({"error": "Authentication required but no valid token is available for your session."}), 401

    try:
        if all_pages and op.get("pagination", {}).get("has_page_param"):
            result = fetch_all_pages(
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
            r = execute_operation(
                operation_id,
                path_params=path_params or None,
                query_params=query_params or None,
                token=token,
            )
            return jsonify({
                "ok": True,
                "operation_id": operation_id,
                "status_code": r["status_code"],
                "headers": {k: v for k, v in r["headers"].items() if k.lower().startswith(("x-", "content-", "expires", "etag"))},
                "data": r["body"],
            })
    except Exception as exc:
        logger.exception("[ESI Explorer] Error running %s", operation_id)
        return jsonify({"error": str(exc)}), 500
