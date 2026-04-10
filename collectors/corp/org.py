"""collectors/corp/org.py — corp_divisions, corp_medals, corp_issued_medals, corp_titles, corp_projects."""

from __future__ import annotations

import json
import logging

from core.db.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_divisions (
            division_type   TEXT NOT NULL,
            division_number INTEGER NOT NULL,
            name            TEXT,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (division_type, division_number)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_medals (
            medal_id    INTEGER PRIMARY KEY,
            title       TEXT,
            description TEXT,
            created     TIMESTAMP,
            creator_id  BIGINT,
            fetched_at  TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_issued_medals (
            medal_id        INTEGER NOT NULL,
            character_id    BIGINT NOT NULL,
            issued_at       TIMESTAMP,
            issuer_id       BIGINT,
            reason          TEXT,
            status          TEXT,
            fetched_at      TIMESTAMP DEFAULT now(),
            PRIMARY KEY (medal_id, character_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_titles (
            title_id                INTEGER PRIMARY KEY,
            name                    TEXT,
            roles_json              TEXT,
            grantable_roles_json    TEXT,
            fetched_at              TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_projects (
            project_id          INTEGER PRIMARY KEY,
            name                TEXT,
            status              TEXT,
            reward_type_id      INTEGER,
            reward_quantity     INTEGER,
            description         TEXT,
            details_json        TEXT,
            contributors_json   TEXT,
            fetched_at          TIMESTAMP DEFAULT now()
        )
    """)


def fetch_corp_org(corporation_id: int, character_id: int, access_token: str) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}
    con = connect_entity(corporation_id)
    try:
        _ensure_tables(con)

        # Divisions
        div_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/divisions/", headers=headers)
        if div_resp.ok:
            d = div_resp.json()
            for div_type, divisions in d.items():
                if isinstance(divisions, list):
                    for div in divisions:
                        con.execute("""
                            INSERT INTO corp_divisions (division_type, division_number, name, fetched_at)
                            VALUES (?, ?, ?, now())
                            ON CONFLICT (division_type, division_number) DO UPDATE SET
                                name = excluded.name, fetched_at = now()
                        """, [div_type, div.get("division"), div.get("name")])

        # Medals
        med_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/medals/", headers=headers)
        if med_resp.ok:
            for m in med_resp.json():
                con.execute("""
                    INSERT INTO corp_medals (medal_id, title, description, created, creator_id, fetched_at)
                    VALUES (?, ?, ?, ?, ?, now())
                    ON CONFLICT (medal_id) DO NOTHING
                """, [m["medal_id"], m.get("title"), m.get("description"),
                      m.get("created"), m.get("creator_id")])

        # Issued medals (paginated)
        im_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/medals/issued/",
                          params={"page": 1}, headers=headers)
        if im_resp.ok:
            issued = im_resp.json()
            total = int(im_resp.headers.get("X-Pages", 1))
            for page in range(2, total + 1):
                r = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/medals/issued/",
                            params={"page": page}, headers=headers)
                if r.ok:
                    issued.extend(r.json())
            for i in issued:
                con.execute("""
                    INSERT INTO corp_issued_medals
                        (medal_id, character_id, issued_at, issuer_id, reason, status, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, now())
                    ON CONFLICT (medal_id, character_id) DO UPDATE SET
                        status = excluded.status, fetched_at = now()
                """, [i["medal_id"], i["character_id"], i.get("issued_at"),
                      i.get("issuer_id"), i.get("reason"), i.get("status")])

        # Titles
        t_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/titles/", headers=headers)
        if t_resp.ok:
            for t in t_resp.json():
                con.execute("""
                    INSERT INTO corp_titles (title_id, name, roles_json, grantable_roles_json, fetched_at)
                    VALUES (?, ?, ?, ?, now())
                    ON CONFLICT (title_id) DO UPDATE SET name = excluded.name, fetched_at = now()
                """, [t["title_id"], t.get("name"), json.dumps(t.get("roles", [])),
                      json.dumps(t.get("grantable_roles", []))])

        # Projects (paginated) + inline detail + contributors
        proj_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/projects/",
                            params={"page": 1}, headers=headers)
        if proj_resp.ok:
            projects = proj_resp.json()
            total = int(proj_resp.headers.get("X-Pages", 1))
            for page in range(2, total + 1):
                r = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/projects/",
                            params={"page": page}, headers=headers)
                if r.ok:
                    projects.extend(r.json())
            for p in projects:
                pid = p.get("project_id") or p.get("id")
                if not pid:
                    continue
                details_json = None
                contrib_json = None
                det_r = esi_get(
                    f"{ESI_BASE}/corporations/{corporation_id}/projects/{pid}/", headers=headers)
                if det_r.ok:
                    details_json = json.dumps(det_r.json())
                con_r = esi_get(
                    f"{ESI_BASE}/corporations/{corporation_id}/projects/{pid}/contributors/",
                    headers=headers)
                if con_r.ok:
                    contrib_json = json.dumps(con_r.json())
                con.execute("""
                    INSERT INTO corp_projects
                        (project_id, name, status, reward_type_id, reward_quantity,
                         description, details_json, contributors_json, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, now())
                    ON CONFLICT (project_id) DO UPDATE SET
                        status = excluded.status, fetched_at = now()
                """, [pid, p.get("name"), p.get("status"), p.get("reward_type_id"),
                      p.get("reward_quantity"), p.get("description"), details_json, contrib_json])
    finally:
        con.close()
    logger.info("[corp.org] updated for corp %s", corporation_id)


def run_for_all_corps() -> None:
    from collectors.corp import get_corp_token_map
    token_map = get_corp_token_map()
    for corp_id, (char_id, access_token) in token_map.items():
        try:
            fetch_corp_org(corp_id, char_id, access_token)
        except Exception:
            logger.exception("[corp.org] failed for corp %s", corp_id)
