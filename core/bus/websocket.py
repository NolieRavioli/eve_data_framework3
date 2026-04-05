"""flask-sock WebSocket handler for the live bus stream.

Protocol
--------
Client → Server (JSON):
    {"action": "subscribe",   "topics": ["log/*", "esi/rate", ...]}
    {"action": "unsubscribe", "topics": ["log/market"]}
    {"action": "history",     "topic": "log/db", "limit": 100, "after_id": 0}

Server → Client (JSON):
    {"type": "entry",   "id": int, "ts": "...", ...}
    {"type": "publish", "id": int, "ts": "...", "topic": "...", "data": {...}}
    {"type": "history", "topic": "...", "entries": [...]}
    {"type": "error",   "message": "..."}

Access Control
--------------
Each topic has an ``access_level`` and optional ``required_role`` defined in
``core.bus.registry``.  The WebSocket handler checks the Flask session against
these for every subscribe request.

Role hierarchy:
    site_owner > site_admin > user (with role) > user > public
"""
from __future__ import annotations

import json
import logging
import queue as _queue_module
import threading

from flask import session

logger = logging.getLogger(__name__)

_RECV_TIMEOUT = 30.0


def _check_topic_access(topic_or_pattern: str) -> bool:
    """Return True if the current session may subscribe to *topic_or_pattern*.

    For wildcard patterns (``log/*``), we check whether the session has access
    to *any* matching topic based on the most restrictive matching config.
    """
    from core.bus.registry import get_topic_config, get_all_topic_configs

    is_site_owner = session.get("is_site_owner", False)
    is_admin = session.get("is_admin", False)
    owner_id = session.get("owner_id")

    if is_site_owner:
        return True  # site owner bypasses everything

    # For wildcard patterns, check against the pattern family's default access.
    is_wildcard = "*" in topic_or_pattern or "?" in topic_or_pattern
    if is_wildcard:
        # Find all matching topic configs and require access to all of them.
        import fnmatch
        for tc in get_all_topic_configs():
            if fnmatch.fnmatch(tc.name, topic_or_pattern):
                if not _check_single_topic_access(tc.access_level, tc.required_role,
                                                  is_admin, owner_id):
                    return False
        return True  # no matching topics means pattern is vacuously allowed

    config = get_topic_config(topic_or_pattern)
    if config is None:
        # Unknown topic — default to admin-only.
        return is_admin

    return _check_single_topic_access(config.access_level, config.required_role,
                                      is_admin, owner_id)


def _check_single_topic_access(
    access_level: str,
    required_role: str | None,
    is_admin: bool,
    owner_id: int | None,
) -> bool:
    """Check access for a single topic config."""
    if is_admin:
        return True  # admins bypass role checks

    if access_level == "admin":
        return False
    if access_level == "public":
        return True
    # access_level == "user"
    if owner_id is None:
        return False  # not logged in

    if required_role is None:
        return True  # any authenticated user

    # Check named role.
    from core.db.publicDB import get_user_roles
    roles = get_user_roles(owner_id)
    return required_role in roles


def bus_ws(ws) -> None:
    """flask-sock handler — one call per WebSocket connection."""

    owner_id = session.get("owner_id")
    is_admin = session.get("is_admin", False)

    # At minimum the user must be authenticated (public topics are accessible
    # to logged-in users but the WebSocket itself requires a session).
    if owner_id is None and not is_admin:
        try:
            ws.send(json.dumps({"type": "error", "message": "Unauthorized"}))
        except Exception:
            pass
        return

    # ── Per-connection outbound queue ─────────────────────────────────────────
    send_q: _queue_module.Queue = _queue_module.Queue(maxsize=500)
    stop_evt = threading.Event()

    def _push(entry: dict) -> None:
        """Subscriber callback — enqueue an entry for sending (drop if full)."""
        msg_type = "publish" if "data" in entry else "entry"
        try:
            send_q.put_nowait({"type": msg_type, **entry})
        except _queue_module.Full:
            pass

    # ── Sender thread ─────────────────────────────────────────────────────────
    def _sender() -> None:
        while not stop_evt.is_set():
            try:
                msg = send_q.get(timeout=1.0)
                ws.send(json.dumps(msg, default=str))
            except _queue_module.Empty:
                continue
            except Exception:
                stop_evt.set()
                break

    sender = threading.Thread(target=_sender, daemon=True, name="bus-ws-sender")
    sender.start()

    from core.bus.handler import bus_handler

    subscribed: set[str] = set()

    # ── Receive / command loop ────────────────────────────────────────────────
    try:
        while not stop_evt.is_set():
            try:
                raw = ws.receive(timeout=_RECV_TIMEOUT)
            except Exception:
                break

            if raw is None:
                break

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = msg.get("action", "")

            if action == "subscribe":
                for topic in msg.get("topics", []):
                    if topic in subscribed:
                        continue
                    if not _check_topic_access(topic):
                        try:
                            send_q.put_nowait({
                                "type": "error",
                                "message": f"Access denied for topic: {topic}",
                            })
                        except _queue_module.Full:
                            pass
                        continue
                    subscribed.add(topic)
                    bus_handler.subscribe(topic, _push)

            elif action == "unsubscribe":
                for topic in msg.get("topics", []):
                    if topic in subscribed:
                        subscribed.discard(topic)
                        bus_handler.unsubscribe(topic, _push)

            elif action == "history":
                topic = msg.get("topic", "")
                if not _check_topic_access(topic):
                    try:
                        send_q.put_nowait({
                            "type": "error",
                            "message": f"Access denied for topic: {topic}",
                        })
                    except _queue_module.Full:
                        pass
                    continue
                limit = max(1, min(int(msg.get("limit", 100)), 2000))
                after_id = int(msg.get("after_id", 0))
                entries = bus_handler.get_topic_log(
                    topic, limit=limit, after_id=after_id
                )
                try:
                    send_q.put_nowait(
                        {"type": "history", "topic": topic, "entries": entries}
                    )
                except _queue_module.Full:
                    pass

    finally:
        stop_evt.set()
        bus_handler.unsubscribe_all(_push)
        sender.join(timeout=2.0)
