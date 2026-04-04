"""flask-sock WebSocket handler for the live telemetry stream.

Protocol
--------
Client → Server (JSON):
    {"action": "subscribe",   "topics": ["db", "market", ...]}
    {"action": "unsubscribe", "topics": ["market"]}
    {"action": "history",     "topic": "db", "limit": 100, "after_id": 0}

Server → Client (JSON):
    {"type": "entry",   "id": int, "ts": "...", "level": "...",
     "logger": "...", "topic": "...", "message": "..."}
    {"type": "history", "topic": "...", "entries": [...]}
    {"type": "error",   "message": "..."}

Authentication
--------------
Reads ``flask.session["is_admin"]`` — the same flag set by the SSO auth flow
and checked by ``@require_admin``.  Non-admin connections receive an error
message and are immediately closed.
"""
from __future__ import annotations

import json
import logging
import queue as _queue_module
import threading

from flask import session

logger = logging.getLogger(__name__)

_RECV_TIMEOUT = 30.0  # seconds; prevents blocking forever on idle connections


def telemetry_ws(ws) -> None:
    """flask-sock handler — one call per WebSocket connection."""

    # ── Auth check ────────────────────────────────────────────────────────────
    if not session.get("is_admin"):
        try:
            ws.send(json.dumps({"type": "error", "message": "Unauthorized"}))
        except Exception:
            pass
        return

    # ── Per-connection outbound queue ─────────────────────────────────────────
    # Subscriber callbacks push entries here; the sender thread drains it.
    send_q: _queue_module.Queue = _queue_module.Queue(maxsize=500)
    stop_evt = threading.Event()

    def _push(entry: dict) -> None:
        """Subscriber callback — enqueue an entry for sending (drop if full)."""
        try:
            send_q.put_nowait({"type": "entry", **entry})
        except _queue_module.Full:
            pass  # slow client: drop rather than back-pressure

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

    sender = threading.Thread(target=_sender, daemon=True, name="telem-ws-sender")
    sender.start()

    from core.telemetry.handler import telemetry_handler

    subscribed: set[str] = set()

    # ── Receive / command loop ────────────────────────────────────────────────
    try:
        while not stop_evt.is_set():
            try:
                raw = ws.receive(timeout=_RECV_TIMEOUT)
            except Exception:
                break  # connection closed or timeout

            if raw is None:
                break

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = msg.get("action", "")

            if action == "subscribe":
                for topic in msg.get("topics", []):
                    if topic not in subscribed:
                        subscribed.add(topic)
                        telemetry_handler.subscribe(topic, _push)

            elif action == "unsubscribe":
                for topic in msg.get("topics", []):
                    if topic in subscribed:
                        subscribed.discard(topic)
                        telemetry_handler.unsubscribe(topic, _push)

            elif action == "history":
                topic = msg.get("topic", "")
                limit = max(1, min(int(msg.get("limit", 100)), 2000))
                after_id = int(msg.get("after_id", 0))
                entries = telemetry_handler.get_topic_log(
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
        telemetry_handler.unsubscribe_all(_push)
        sender.join(timeout=2.0)
