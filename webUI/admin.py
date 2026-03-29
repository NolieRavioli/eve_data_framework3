# webUI/admin.py
"""
Admin panel blueprint.
- Live console via Server-Sent Events (SSE)
- Database statistics
- User management (promote / demote site admins)
- SQL database browser (read-only)
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
from sqlalchemy import inspect, text

from db.database import get_public_session, initialize_public_database
from db.models import SiteAdmin, User
from util import sde_store
from util.esi_spec_registry import get_registry_status

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


class _AdminLogHandler(logging.Handler):
    """Capture formatted log records into a shared ring buffer for SSE."""

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
    """Decorator: 403 if the session owner is not a site admin."""

    @wraps(fn)
    def _inner(*args, **kwargs):
        if not session.get("is_admin"):
            abort(403)
        return fn(*args, **kwargs)

    return _inner


def _is_site_owner(owner_id: int) -> bool:
    db = get_public_session()
    try:
        row = db.get(SiteAdmin, owner_id)
        return bool(row and row.is_site_owner)
    finally:
        db.close()


def _db_stats() -> dict[str, int]:
    """Return row counts for the public database tables."""

    engine = initialize_public_database()
    db = get_public_session()
    try:
        inspector = inspect(engine)
        table_counts: dict[str, int] = {}
        for table_name in inspector.get_table_names():
            result = db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
            table_counts[table_name] = int(result.scalar() or 0)
        return dict(sorted(table_counts.items(), key=lambda item: item[1], reverse=True))
    finally:
        db.close()


def _user_list() -> list[dict]:
    """Return every owner_id with character count and admin status."""

    db = get_public_session()
    try:
        rows = db.query(User.owner_id).distinct().all()
        owner_ids = [row.owner_id for row in rows]
        result = []
        for owner_id in owner_ids:
            char_count = db.query(User).filter(User.owner_id == owner_id).count()
            admin_row = db.get(SiteAdmin, owner_id)
            result.append(
                {
                    "owner_id": owner_id,
                    "character_count": char_count,
                    "is_admin": admin_row is not None,
                    "is_site_owner": bool(admin_row and admin_row.is_site_owner),
                    "granted_at": (
                        admin_row.granted_at.isoformat()
                        if admin_row and admin_row.granted_at
                        else None
                    ),
                }
            )
        return sorted(
            result,
            key=lambda row: (
                not row["is_site_owner"],
                not row["is_admin"],
                row["owner_id"],
            ),
        )
    finally:
        db.close()


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
    """SSE endpoint that streams live log lines to the admin console."""

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
    """Promote an owner to site admin. Body: {"owner_id": <int>}"""

    data = request.get_json(force=True, silent=True) or {}
    target_id = data.get("owner_id")
    if not target_id:
        return jsonify({"error": "owner_id required"}), 400

    current_owner = session.get("owner_id")
    db = get_public_session()
    try:
        existing = db.get(SiteAdmin, target_id)
        if existing:
            return jsonify({"ok": True, "note": "already admin"})
        db.add(
            SiteAdmin(
                owner_id=target_id,
                is_site_owner=False,
                granted_by=current_owner,
                granted_at=datetime.datetime.utcnow(),
            )
        )
        db.commit()
        logger.info("[Admin] Owner %s promoted to admin by %s.", target_id, current_owner)
        return jsonify({"ok": True})
    finally:
        db.close()


@admin_bp.route("/demote", methods=["POST"])
@require_admin
def demote():
    """Remove admin role. Body: {"owner_id": <int>}"""

    data = request.get_json(force=True, silent=True) or {}
    target_id = data.get("owner_id")
    if not target_id:
        return jsonify({"error": "owner_id required"}), 400

    current_owner = session.get("owner_id")
    db = get_public_session()
    try:
        row = db.get(SiteAdmin, target_id)
        if not row:
            return jsonify({"ok": True, "note": "not an admin"})
        if row.is_site_owner:
            return jsonify({"error": "Cannot demote the site owner."}), 403
        db.delete(row)
        db.commit()
        logger.info("[Admin] Owner %s demoted by %s.", target_id, current_owner)
        return jsonify({"ok": True})
    finally:
        db.close()


@admin_bp.route("/db_browser")
@require_admin
def db_browser():
    inspector = inspect(initialize_public_database())
    tables = {}
    for table_name in inspector.get_table_names():
        tables[table_name] = [column["name"] for column in inspector.get_columns(table_name)]
    return render_template("db_browser.html", tables=tables, db_label="public.db")


@admin_bp.route("/db_browser/query", methods=["POST"])
@require_admin
def db_browser_query():
    """Execute a read-only SQL query against the public DB."""

    data = request.get_json(force=True, silent=True) or {}
    raw_sql = (data.get("sql") or "").strip()
    if not raw_sql:
        return jsonify({"error": "No SQL provided"}), 400

    normalized = raw_sql.lstrip().upper()
    if not normalized.startswith("SELECT") and not normalized.startswith("PRAGMA"):
        return jsonify({"error": "Only SELECT and PRAGMA statements are allowed."}), 403

    db = get_public_session()
    try:
        result = db.execute(text(raw_sql))
        keys = list(result.keys())
        rows = [dict(zip(keys, row)) for row in result.fetchmany(500)]
        return jsonify({"columns": keys, "rows": rows})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    finally:
        db.close()
