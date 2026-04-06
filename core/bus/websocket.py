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
    from core.auth.identity import get_user_roles
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


# ── Declarative per-endpoint WebSocket registration ──────────────────────────
#
# Applications call ``register_websock(url, topics, ...)`` at import time to
# declare a focused WebSocket endpoint.  ``attach_all_websocks(sock)`` is then
# called once by the Flask app factory (after all blueprints are registered) to
# bind those declarations to real ``flask-sock`` routes.
#
# Each registered endpoint auto-subscribes to its topic list on connect and
# streams ``publish``-type messages to the client.  It does NOT implement the
# full interactive protocol (subscribe/unsubscribe/history) — that is the job
# of the generic ``/bus`` handler above.
#
# ``topics`` may be:
#   - A plain list[str]:  ``["esi/rate", "queue/tasks"]``
#   - A callable that receives the URL keyword arguments and returns list[str]:
#       ``lambda task_id: [f"task/{task_id}/log"]``
#
# ``access_check`` is an optional ``callable(**url_kwargs) -> bool`` for
# extra per-request ownership checks (e.g. task ownership).

import typing as _t

_RouteSpec = _t.TypedDict("_RouteSpec", {
    "url":          str,
    "topics":       "_t.Union[list, _t.Callable]",
    "access_level": str,
    "required_role": "_t.Optional[str]",
    "access_check": "_t.Optional[_t.Callable]",
})

_pending_ws_routes: list[_RouteSpec] = []


def register_websock(
    url: str,
    topics: "_t.Union[list[str], _t.Callable[..., list[str]]]",
    *,
    access_level: str = "user",
    required_role: "_t.Optional[str]" = None,
    access_check: "_t.Optional[_t.Callable[..., bool]]" = None,
) -> None:
    """Declare a focused WebSocket push endpoint.

    Call at module level from an application's ``routes.py``.  The binding to
    ``flask-sock`` happens later when ``attach_all_websocks()`` is invoked.

    :param url:           Flask URL rule (e.g. ``"/queue/<task_id>/ws"``).
    :param topics:        Static list of bus topic strings, OR a callable that
                          accepts the URL kwargs and returns a list of strings.
    :param access_level:  Minimum session access level: ``"public"`` | ``"user"`` | ``"admin"``.
    :param required_role: Named role that the authenticated user must hold
                          (admins bypass this check automatically).
    :param access_check:  Extra callable(**url_kwargs) -> bool for ownership
                          checks.  Returning False sends an Unauthorized error.
    """
    _pending_ws_routes.append({
        "url":           url,
        "topics":        topics,
        "access_level":  access_level,
        "required_role": required_role,
        "access_check":  access_check,
    })


def _make_ws_handler(
    topics_spec: "_t.Union[list[str], _t.Callable[..., list[str]]]",
    access_level: str,
    required_role: "_t.Optional[str]",
    access_check: "_t.Optional[_t.Callable[..., bool]]",
    url_kwargs: dict,
) -> "_t.Callable":
    """Return a flask-sock handler closed over the given parameters."""

    def _handler(ws) -> None:
        # ── Auth ──────────────────────────────────────────────────────────────
        owner_id  = session.get("owner_id")
        is_admin  = session.get("is_admin", False)
        is_owner  = session.get("is_site_owner", False)

        def _deny(msg: str) -> None:
            try:
                ws.send(json.dumps({"type": "error", "message": msg}))
            except Exception:
                pass

        if not is_owner:
            if access_level == "admin" and not is_admin:
                _deny("Unauthorized")
                return
            if access_level == "user" and owner_id is None and not is_admin:
                _deny("Unauthorized")
                return
            if required_role and not is_admin:
                if owner_id is None:
                    _deny("Unauthorized")
                    return
                from core.auth.identity import get_user_roles
                if required_role not in get_user_roles(owner_id):
                    _deny("Forbidden: missing role")
                    return

        if access_check is not None:
            try:
                if not access_check(**url_kwargs):
                    _deny("Forbidden")
                    return
            except Exception:
                _deny("Forbidden")
                return

        # ── Resolve topics ────────────────────────────────────────────────────
        if callable(topics_spec):
            try:
                resolved_topics: list[str] = topics_spec(**url_kwargs)
            except Exception:
                _deny("Failed to resolve topics")
                return
        else:
            resolved_topics = list(topics_spec)

        # ── Outbound queue + sender thread ─────────────────────────────────
        send_q: _queue_module.Queue = _queue_module.Queue(maxsize=500)
        stop_evt = threading.Event()

        def _push(entry: dict) -> None:
            msg_type = "publish" if "data" in entry else "entry"
            try:
                send_q.put_nowait({"type": msg_type, **entry})
            except _queue_module.Full:
                pass

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

        sender = threading.Thread(target=_sender, daemon=True, name="bus-ws-push-sender")
        sender.start()

        # ── Subscribe & push historical snapshots ─────────────────────────────
        from core.bus.handler import bus_handler
        for topic in resolved_topics:
            bus_handler.subscribe(topic, _push)
            # Send recent history so the client has immediate context.
            recent = bus_handler.get_topic_log(topic, limit=50)
            if recent:
                try:
                    send_q.put_nowait({"type": "history", "topic": topic, "entries": recent})
                except _queue_module.Full:
                    pass

        # ── Keep-alive receive loop (drain client frames, watch for close) ──
        try:
            while not stop_evt.is_set():
                try:
                    raw = ws.receive(timeout=_RECV_TIMEOUT)
                except Exception:
                    break
                if raw is None:
                    break
                # Acknowledge pings / ignore unsupported frames silently.
        finally:
            stop_evt.set()
            bus_handler.unsubscribe_all(_push)
            sender.join(timeout=2.0)

    return _handler


def attach_all_websocks(sock: object) -> None:
    """Bind all declared ``register_websock`` routes to *sock* (flask-sock Sock).

    Must be called after all application blueprints have been registered so
    that every ``register_websock()`` call has already executed.
    """
    for spec in _pending_ws_routes:
        url           = spec["url"]
        topics_spec   = spec["topics"]
        access_level  = spec["access_level"]
        required_role = spec["required_role"]
        access_check  = spec["access_check"]

        # Extract static URL kwargs for non-dynamic topics; for dynamic (callable)
        # topics we pass url_kwargs from the real request via a closure-per-route.
        def _make_route(ts, al, rr, ac, url_rule):
            def _route_handler(ws, **url_kwargs):
                _make_ws_handler(ts, al, rr, ac, url_kwargs)(ws)

            # flask-sock requires the function to have a unique __name__
            _route_handler.__name__ = "ws_push_" + url_rule.replace("/", "_").replace("<", "").replace(">", "").strip("_")
            sock.route(url_rule)(_route_handler)

        _make_route(topics_spec, access_level, required_role, access_check, url)
        logger.debug("[websocket] registered push endpoint %s → topics=%s", url, topics_spec)
