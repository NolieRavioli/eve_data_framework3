"""collectors/alliance/contacts.py — alliance contacts and contact labels."""

from __future__ import annotations

import logging

from core.db.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"
REQUIRED_SCOPE = "esi-alliances.read_contacts.v1"


def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS alliance_contact_labels (
            label_id    BIGINT PRIMARY KEY,
            label_name  TEXT NOT NULL,
            fetched_at  TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS alliance_contacts (
            contact_id      BIGINT NOT NULL,
            contact_type    TEXT NOT NULL,
            standing        FLOAT,
            label_ids_json  TEXT,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (contact_id, contact_type)
        )
    """)


def fetch_alliance_contacts(alliance_id: int, char_id: int, access_token: str) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}
    con = connect_entity(alliance_id)
    try:
        _ensure_tables(con)

        # Labels
        lbl_resp = esi_get(f"{ESI_BASE}/alliances/{alliance_id}/contacts/labels/", headers=headers)
        label_map: dict[int, str] = {}
        if lbl_resp.ok:
            labels = lbl_resp.json()
            label_map = {lbl["label_id"]: lbl["label_name"] for lbl in labels}
            con.execute("DELETE FROM alliance_contact_labels")
            con.executemany("""
                INSERT INTO alliance_contact_labels (label_id, label_name, fetched_at)
                VALUES (?, ?, now())
            """, [(lid, name) for lid, name in label_map.items()])

        # Contacts (paginated)
        resp = esi_get(f"{ESI_BASE}/alliances/{alliance_id}/contacts/",
                       params={"page": 1}, headers=headers)
        if not resp.ok:
            if resp.status_code == 403:
                return
            logger.warning("[alliance.contacts] ESI %s for alliance %s", resp.status_code, alliance_id)
            return
        contacts = resp.json()
        total = int(resp.headers.get("X-Pages", 1))
        for page in range(2, total + 1):
            r = esi_get(f"{ESI_BASE}/alliances/{alliance_id}/contacts/",
                        params={"page": page}, headers=headers)
            if r.ok:
                contacts.extend(r.json())

        import json
        con.execute("DELETE FROM alliance_contacts")
        con.executemany("""
            INSERT INTO alliance_contacts
                (contact_id, contact_type, standing, label_ids_json, fetched_at)
            VALUES (?, ?, ?, ?, now())
        """, [(c["contact_id"], c["contact_type"], c.get("standing"),
               json.dumps(c.get("label_ids", [])) if c.get("label_ids") else None)
              for c in contacts])
    finally:
        con.close()
    logger.info("[alliance.contacts] updated for alliance %s", alliance_id)


def run_for_all_alliances() -> None:
    from collectors.alliance import get_alliance_token_map
    token_map = get_alliance_token_map()
    for alliance_id, (char_id, access_token) in token_map.items():
        try:
            fetch_alliance_contacts(alliance_id, char_id, access_token)
        except Exception:
            logger.exception("[alliance.contacts] failed for alliance %s", alliance_id)
