"""collectors/character/comms.py — mail, notifications, contacts, calendar collectors.

Writes to the owner's per-entity DuckDB (`<owner_id>.duckdb`).

Scope → collector registry (SCOPE_COLLECTORS) is declared at the bottom.
"""

from __future__ import annotations

import json
import logging

from core.io.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


# ─────────────────────────────────────────────────────────────────────────────
# DDL
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_mail (
            character_id    BIGINT NOT NULL,
            mail_id         BIGINT NOT NULL,
            from_id         BIGINT,
            subject         TEXT,
            body            TEXT,
            timestamp       TIMESTAMP,
            is_read         BOOLEAN DEFAULT FALSE,
            labels          BIGINT[],
            recipients_json TEXT,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, mail_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_mail_labels (
            character_id    BIGINT NOT NULL,
            label_id        BIGINT NOT NULL,
            name            TEXT,
            color           TEXT,
            unread_count    INTEGER DEFAULT 0,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, label_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_mail_lists (
            character_id    BIGINT NOT NULL,
            mailing_list_id BIGINT NOT NULL,
            name            TEXT,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, mailing_list_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_notifications (
            character_id    BIGINT NOT NULL,
            notification_id BIGINT NOT NULL,
            sender_id       BIGINT,
            sender_type     TEXT,
            type            TEXT,
            text            TEXT,
            timestamp       TIMESTAMP,
            is_read         BOOLEAN DEFAULT FALSE,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, notification_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_notification_contacts (
            character_id        BIGINT NOT NULL,
            notification_id     BIGINT NOT NULL,
            message             TEXT,
            send_date           TIMESTAMP,
            sender_character_id BIGINT,
            standing_level      REAL,
            fetched_at          TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, notification_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_events (
            character_id    BIGINT NOT NULL,
            event_id        INTEGER NOT NULL,
            event_date      TIMESTAMP,
            title           TEXT,
            importance      INTEGER,
            event_response  TEXT,
            owner_id        BIGINT,
            owner_type      TEXT,
            owner_name      TEXT,
            text            TEXT,
            duration        INTEGER,
            attendees_json  TEXT,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, event_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_contacts (
            character_id    BIGINT NOT NULL,
            contact_id      BIGINT NOT NULL,
            contact_type    TEXT,
            standing        REAL,
            is_watched      BOOLEAN DEFAULT FALSE,
            is_blocked      BOOLEAN DEFAULT FALSE,
            label_ids       BIGINT[],
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, contact_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_contact_labels (
            character_id    BIGINT NOT NULL,
            label_id        BIGINT NOT NULL,
            label_name      TEXT,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, label_id)
        )
    """)


# ─────────────────────────────────────────────────────────────────────────────
# Mail
# ─────────────────────────────────────────────────────────────────────────────

def populate_mail(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/mail/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[comms.mail] ESI %s for char %s", resp.status_code, character_id)
        return
    headers_list = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)

        # Fetch mail labels
        labels_url = f"{ESI_BASE}/characters/{character_id}/mail/labels/"
        lr = esi_get(labels_url, headers={"Authorization": f"Bearer {access_token}"})
        if lr.ok:
            for lbl in (lr.json() or {}).get("labels", []):
                con.execute("""
                    INSERT INTO character_mail_labels
                        (character_id, label_id, name, color, unread_count, fetched_at)
                    VALUES (?, ?, ?, ?, ?, now())
                    ON CONFLICT (character_id, label_id) DO UPDATE SET
                        name = excluded.name, color = excluded.color,
                        unread_count = excluded.unread_count, fetched_at = now()
                """, [character_id, lbl["label_id"], lbl.get("name"),
                      lbl.get("color"), lbl.get("unread_count", 0)])

        # Fetch mailing lists
        lists_url = f"{ESI_BASE}/characters/{character_id}/mail/lists/"
        mlr = esi_get(lists_url, headers={"Authorization": f"Bearer {access_token}"})
        if mlr.ok:
            for ml in mlr.json() or []:
                con.execute("""
                    INSERT INTO character_mail_lists
                        (character_id, mailing_list_id, name, fetched_at)
                    VALUES (?, ?, ?, now())
                    ON CONFLICT (character_id, mailing_list_id) DO UPDATE SET
                        name = excluded.name, fetched_at = now()
                """, [character_id, ml["mailing_list_id"], ml.get("name")])

        for m in headers_list:
            mail_id = m["mail_id"]
            # Fetch mail body inline (bounded by mail count)
            body = None
            body_url = f"{ESI_BASE}/characters/{character_id}/mail/{mail_id}/"
            br = esi_get(body_url, headers={"Authorization": f"Bearer {access_token}"})
            if br.ok:
                body = br.json().get("body")
            recipients = json.dumps(m.get("recipients", [])) if m.get("recipients") else None
            label_ids = m.get("labels") or []
            con.execute("""
                INSERT INTO character_mail
                    (character_id, mail_id, from_id, subject, body, timestamp,
                     is_read, labels, recipients_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, mail_id) DO UPDATE SET
                    is_read = excluded.is_read, body = excluded.body, fetched_at = now()
            """, [character_id, mail_id, m.get("from"), m.get("subject"),
                  body, m.get("timestamp"), m.get("is_read", False),
                  label_ids, recipients])
    finally:
        con.close()
    logger.info("[comms.mail] %d headers for char %s", len(headers_list), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────────────────────────────────────

def populate_notifications(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/notifications/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[comms.notifications] ESI %s for char %s", resp.status_code, character_id)
        return
    data = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for n in data:
            con.execute("""
                INSERT INTO character_notifications
                    (character_id, notification_id, sender_id, sender_type, type,
                     text, timestamp, is_read, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, notification_id) DO UPDATE SET
                    is_read = excluded.is_read, fetched_at = now()
            """, [character_id, n["notification_id"], n.get("sender_id"),
                  n.get("sender_type"), n.get("type"), n.get("text"),
                  n.get("timestamp"), n.get("is_read", False)])

        # Contact notifications
        cn_url = f"{ESI_BASE}/characters/{character_id}/notifications/contacts/"
        cnr = esi_get(cn_url, headers=headers)
        if cnr.ok:
            for cn in cnr.json() or []:
                con.execute("""
                    INSERT INTO character_notification_contacts
                        (character_id, notification_id, message, send_date,
                         sender_character_id, standing_level, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, now())
                    ON CONFLICT (character_id, notification_id) DO UPDATE SET
                        message = excluded.message, fetched_at = now()
                """, [character_id, cn["notification_id"], cn.get("message"),
                      cn.get("send_date"), cn.get("sender_character_id"),
                      cn.get("standing_level")])
    finally:
        con.close()
    logger.info("[comms.notifications] %d for char %s", len(data), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Calendar / Events
# ─────────────────────────────────────────────────────────────────────────────

def populate_calendar(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/calendar/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[comms.calendar] ESI %s for char %s", resp.status_code, character_id)
        return
    events = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for e in events:
            event_id = e["event_id"]
            # Fetch event detail + attendees inline (bounded by event count)
            text_val = None
            owner_id_val = None
            owner_type = None
            owner_name = None
            duration = None
            attendees_json = None

            detail_url = f"{ESI_BASE}/characters/{character_id}/calendar/{event_id}/"
            dr = esi_get(detail_url, headers=headers)
            if dr.ok:
                det = dr.json()
                text_val = det.get("text")
                owner_id_val = det.get("owner_id")
                owner_type = det.get("owner_type")
                owner_name = det.get("owner_name")
                duration = det.get("duration")

            att_url = f"{ESI_BASE}/characters/{character_id}/calendar/{event_id}/attendees/"
            ar = esi_get(att_url, headers=headers)
            if ar.ok:
                attendees_json = json.dumps(ar.json() or [])

            con.execute("""
                INSERT INTO character_events
                    (character_id, event_id, event_date, title, importance,
                     event_response, owner_id, owner_type, owner_name, text,
                     duration, attendees_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, event_id) DO UPDATE SET
                    event_response = excluded.event_response,
                    text = excluded.text, fetched_at = now()
            """, [character_id, event_id, e.get("event_date"), e.get("title"),
                  e.get("importance"), e.get("event_response"),
                  owner_id_val, owner_type, owner_name, text_val,
                  duration, attendees_json])
    finally:
        con.close()
    logger.info("[comms.calendar] %d events for char %s", len(events), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Contacts
# ─────────────────────────────────────────────────────────────────────────────

def populate_contacts(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/contacts/"
    headers = {"Authorization": f"Bearer {access_token}"}

    # Paginate contacts
    contacts = []
    resp = esi_get(url, headers=headers, params={"page": 1})
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[comms.contacts] ESI %s for char %s", resp.status_code, character_id)
        return
    contacts.extend(resp.json())
    total_pages = int(resp.headers.get("X-Pages", 1))
    for page in range(2, total_pages + 1):
        r = esi_get(url, headers=headers, params={"page": page})
        if r.ok:
            contacts.extend(r.json())

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)

        # Fetch contact labels (1 call, inline)
        labels_url = f"{ESI_BASE}/characters/{character_id}/contacts/labels/"
        lr = esi_get(labels_url, headers=headers)
        if lr.ok:
            for lbl in lr.json() or []:
                con.execute("""
                    INSERT INTO character_contact_labels
                        (character_id, label_id, label_name, fetched_at)
                    VALUES (?, ?, ?, now())
                    ON CONFLICT (character_id, label_id) DO UPDATE SET
                        label_name = excluded.label_name, fetched_at = now()
                """, [character_id, lbl["label_id"], lbl.get("label_name")])

        for c in contacts:
            con.execute("""
                INSERT INTO character_contacts
                    (character_id, contact_id, contact_type, standing,
                     is_watched, is_blocked, label_ids, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, contact_id) DO UPDATE SET
                    standing = excluded.standing, label_ids = excluded.label_ids,
                    fetched_at = now()
            """, [character_id, c["contact_id"], c.get("contact_type"),
                  c.get("standing"), c.get("is_watched", False),
                  c.get("is_blocked", False), c.get("label_ids") or []])
    finally:
        con.close()
    logger.info("[comms.contacts] %d for char %s", len(contacts), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Scope → Collector registry
# ─────────────────────────────────────────────────────────────────────────────

SCOPE_COLLECTORS: list[tuple[str, str, object]] = [
    ("esi-mail.read_mail.v1",                       "mail",          populate_mail),
    ("esi-characters.read_notifications.v1",        "notifications", populate_notifications),
    ("esi-calendar.read_calendar_events.v1",        "calendar",      populate_calendar),
    ("esi-characters.read_contacts.v1",             "contacts",      populate_contacts),
]
NO_SCOPE_COLLECTORS: list[tuple[str, object]] = []
