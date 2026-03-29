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
    from util.data_collection_queue import get_collection_queue

    queue = get_collection_queue()
    users = _user_list()
    table_counts = _db_stats()
    sde_status = sde_store.get_warehouse_status()
    esi_status = get_registry_status()
    stats = {
        "queue_depth": queue.queue_depth(),
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
