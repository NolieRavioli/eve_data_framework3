"""collectors/corp/members.py — corp_members with inline tracking/roles/titles enrichment, corp_shareholders."""

from __future__ import annotations

import json
import logging

from core.io.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_members (
            character_id            BIGINT PRIMARY KEY,
            start_date              TIMESTAMP,
            base_id                 BIGINT,
            location_id             BIGINT,
            logoff_date             TIMESTAMP,
            logon_date              TIMESTAMP,
            ship_type_id            INTEGER,
            roles_json              TEXT,
            grantable_roles_json    TEXT,
            roles_at_hq_json        TEXT,
            roles_at_base_json      TEXT,
            roles_at_other_json     TEXT,
            roles_history_json      TEXT,
            title_ids               INTEGER[],
            fetched_at              TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_shareholders (
            shareholder_id      BIGINT NOT NULL,
            shareholder_type    TEXT NOT NULL,
            share_count         BIGINT NOT NULL,
            fetched_at          TIMESTAMP DEFAULT now(),
            PRIMARY KEY (shareholder_id, shareholder_type)
        )
    """)


def fetch_corp_members(corporation_id: int, character_id: int, access_token: str) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}
    con = connect_entity(corporation_id)
    try:
        _ensure_tables(con)

        # Member list
        m_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/members/", headers=headers)
        if not m_resp.ok:
            if m_resp.status_code == 403:
                return
            logger.warning("[corp.members] ESI %s", m_resp.status_code)
            return
        member_ids = m_resp.json()  # list of character_ids

        # Seed rows
        con.execute("DELETE FROM corp_members")
        con.executemany(
            "INSERT INTO corp_members (character_id, fetched_at) VALUES (?, now())",
            [(mid,) for mid in member_ids])

        # Member tracking (inline enrichment)
        track_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/membertracking/",
                             headers=headers)
        if track_resp.ok:
            for t in track_resp.json():
                cid = t["character_id"]
                con.execute("""
                    UPDATE corp_members SET
                        start_date = ?, base_id = ?, location_id = ?,
                        logoff_date = ?, logon_date = ?, ship_type_id = ?
                    WHERE character_id = ?
                """, [t.get("start_date"), t.get("base_id"), t.get("location_id"),
                      t.get("logoff_date"), t.get("logon_date"), t.get("ship_type_id"), cid])

        # Roles (inline enrichment, paginated by character bloc)
        roles_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/roles/", headers=headers)
        if roles_resp.ok:
            for r in roles_resp.json():
                cid = r["character_id"]
                con.execute("""
                    UPDATE corp_members SET
                        roles_json = ?, grantable_roles_json = ?,
                        roles_at_hq_json = ?, roles_at_base_json = ?, roles_at_other_json = ?
                    WHERE character_id = ?
                """, [json.dumps(r.get("roles", [])), json.dumps(r.get("grantable_roles", [])),
                      json.dumps(r.get("roles_at_hq", [])), json.dumps(r.get("roles_at_base", [])),
                      json.dumps(r.get("roles_at_other", [])), cid])

        # Roles history
        hist_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/roles/history/",
                            params={"page": 1}, headers=headers)
        if hist_resp.ok:
            history = hist_resp.json()
            total = int(hist_resp.headers.get("X-Pages", 1))
            for page in range(2, total + 1):
                r = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/roles/history/",
                            params={"page": page}, headers=headers)
                if r.ok:
                    history.extend(r.json())
            # Group by character
            by_char: dict[int, list] = {}
            for entry in history:
                by_char.setdefault(entry["character_id"], []).append(entry)
            for cid, entries in by_char.items():
                con.execute("UPDATE corp_members SET roles_history_json = ? WHERE character_id = ?",
                            [json.dumps(entries), cid])

        # Member titles
        titles_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/members/titles/",
                              headers=headers)
        if titles_resp.ok:
            for t in titles_resp.json():
                cid = t["character_id"]
                con.execute("UPDATE corp_members SET title_ids = ? WHERE character_id = ?",
                            [t.get("titles", []), cid])

        # Shareholders
        sh_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/shareholders/",
                          params={"page": 1}, headers=headers)
        if sh_resp.ok:
            shareholders = sh_resp.json()
            total = int(sh_resp.headers.get("X-Pages", 1))
            for page in range(2, total + 1):
                r = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/shareholders/",
                            params={"page": page}, headers=headers)
                if r.ok:
                    shareholders.extend(r.json())
            con.execute("DELETE FROM corp_shareholders")
            con.executemany("""
                INSERT INTO corp_shareholders (shareholder_id, shareholder_type, share_count, fetched_at)
                VALUES (?, ?, ?, now())
            """, [(s["shareholder_id"], s.get("shareholder_type"), s.get("share_count", 0))
                  for s in shareholders])
    finally:
        con.close()
    logger.info("[corp.members] %d members for corp %s", len(member_ids), corporation_id)


def run_for_all_corps() -> None:
    from collectors.corp import get_corp_token_map
    token_map = get_corp_token_map()
    for corp_id, (char_id, access_token) in token_map.items():
        try:
            fetch_corp_members(corp_id, char_id, access_token)
        except Exception:
            logger.exception("[corp.members] failed for corp %s", corp_id)
