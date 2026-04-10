"""collectors/corp/contacts.py — corp_contacts, corp_contact_labels, corp_standings."""

from __future__ import annotations

import logging

from core.db.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_contacts (
            contact_id      BIGINT PRIMARY KEY,
            contact_type    TEXT,
            standing        REAL,
            is_watched      BOOLEAN DEFAULT FALSE,
            label_ids       BIGINT[],
            fetched_at      TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_contact_labels (
            label_id    BIGINT PRIMARY KEY,
            label_name  TEXT,
            fetched_at  TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_standings (
            from_id     BIGINT NOT NULL,
            from_type   TEXT NOT NULL,
            standing    REAL NOT NULL,
            fetched_at  TIMESTAMP DEFAULT now(),
            PRIMARY KEY (from_id, from_type)
        )
    """)


def fetch_corp_contacts(corporation_id: int, character_id: int, access_token: str) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}
    con = connect_entity(corporation_id)
    try:
        _ensure_tables(con)

        # Contacts (paginated)
        resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/contacts/",
                       params={"page": 1}, headers=headers)
        if resp.ok:
            data = resp.json()
            total = int(resp.headers.get("X-Pages", 1))
            for page in range(2, total + 1):
                r = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/contacts/",
                            params={"page": page}, headers=headers)
                if r.ok:
                    data.extend(r.json())
            con.execute("DELETE FROM corp_contacts")
            con.executemany("""
                INSERT INTO corp_contacts (contact_id, contact_type, standing, is_watched, label_ids, fetched_at)
                VALUES (?, ?, ?, ?, ?, now())
            """, [(c["contact_id"], c.get("contact_type"), c.get("standing"),
                   c.get("is_watched", False), c.get("label_ids", [])) for c in data])
            logger.info("[corp.contacts] %d contacts for corp %s", len(data), corporation_id)

        # Contact labels (inline enrichment)
        label_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/contacts/labels/",
                             headers=headers)
        if label_resp.ok:
            labels = label_resp.json()
            con.execute("DELETE FROM corp_contact_labels")
            con.executemany("""
                INSERT INTO corp_contact_labels (label_id, label_name, fetched_at)
                VALUES (?, ?, now())
            """, [(lbl["label_id"], lbl.get("label_name")) for lbl in labels])

        # Standings
        stand_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/standings/",
                             headers=headers)
        if stand_resp.ok:
            for s in stand_resp.json():
                con.execute("""
                    INSERT INTO corp_standings (from_id, from_type, standing, fetched_at)
                    VALUES (?, ?, ?, now())
                    ON CONFLICT (from_id, from_type) DO UPDATE SET
                        standing = excluded.standing, fetched_at = now()
                """, [s["from_id"], s.get("from_type", ""), s.get("standing", 0)])
    finally:
        con.close()


def run_for_all_corps() -> None:
    from collectors.corp import get_corp_token_map
    token_map = get_corp_token_map()
    for corp_id, (char_id, access_token) in token_map.items():
        try:
            fetch_corp_contacts(corp_id, char_id, access_token)
        except Exception:
            logger.exception("[corp.contacts] failed for corp %s", corp_id)
