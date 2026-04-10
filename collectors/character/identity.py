"""collectors/character/identity.py — enriched character sheet, clones, agent research, projects.

Writes to the owner's per-entity DuckDB (`<owner_id>.duckdb`).
"""

from __future__ import annotations

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
        CREATE TABLE IF NOT EXISTS character_sheet (
            character_id        BIGINT PRIMARY KEY,
            owner_id            BIGINT NOT NULL,
            name                TEXT,
            description         TEXT,
            birthday            TIMESTAMP,
            gender              TEXT,
            race_id             INTEGER,
            bloodline_id        INTEGER,
            ancestry_id         INTEGER,
            corporation_id      BIGINT,
            alliance_id         BIGINT,
            faction_id          INTEGER,
            security_status     REAL,
            title               TEXT,
            fetched_at          TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_clones (
            character_id        BIGINT NOT NULL,
            clone_type          TEXT NOT NULL,
            location_id         BIGINT,
            location_type       TEXT,
            clone_name          TEXT,
            implants_json       TEXT,
            fetched_at          TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, clone_type)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_agent_research (
            character_id        BIGINT NOT NULL,
            agent_id            BIGINT NOT NULL,
            points_per_day      REAL,
            remainder_points    REAL,
            skill_type_id       INTEGER,
            started_at          TIMESTAMP,
            fetched_at          TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, agent_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_projects (
            character_id        BIGINT NOT NULL,
            project_id          BIGINT NOT NULL,
            name                TEXT,
            description         TEXT,
            status              TEXT,
            fetched_at          TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, project_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_implants (
            character_id        BIGINT NOT NULL,
            type_id             INTEGER NOT NULL,
            slot                INTEGER,
            fetched_at          TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, type_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_attributes (
            character_id        BIGINT PRIMARY KEY,
            charisma            INTEGER,
            intelligence        INTEGER,
            memory              INTEGER,
            perception          INTEGER,
            willpower           INTEGER,
            bonus_remaps        INTEGER DEFAULT 0,
            accrued_remap_cooldown_date TIMESTAMP,
            last_remap_date     TIMESTAMP,
            fetched_at          TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_roles (
            character_id        BIGINT NOT NULL,
            role_type           TEXT NOT NULL,
            roles_json          TEXT,
            fetched_at          TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, role_type)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_skills (
            character_id        BIGINT NOT NULL,
            skill_id            INTEGER NOT NULL,
            active_skill_level  INTEGER NOT NULL DEFAULT 0,
            trained_skill_level INTEGER NOT NULL DEFAULT 0,
            skillpoints_in_skill BIGINT NOT NULL DEFAULT 0,
            fetched_at          TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, skill_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS character_assets (
            character_id        BIGINT NOT NULL,
            item_id             BIGINT NOT NULL,
            type_id             INTEGER NOT NULL,
            location_id         BIGINT NOT NULL,
            location_type       TEXT,
            location_flag       TEXT,
            quantity            INTEGER NOT NULL DEFAULT 1,
            is_singleton        BOOLEAN DEFAULT FALSE,
            is_blueprint_copy   BOOLEAN,
            name                TEXT,
            position_x          DOUBLE,
            position_y          DOUBLE,
            position_z          DOUBLE,
            fetched_at          TIMESTAMP DEFAULT now(),
            PRIMARY KEY (character_id, item_id)
        )
    """)


# ─────────────────────────────────────────────────────────────────────────────
# Enriched character sheet (public endpoint)
# ─────────────────────────────────────────────────────────────────────────────

def populate_character_sheet(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/"
    resp = esi_get(url)  # Public endpoint
    if not resp.ok:
        logger.warning("[identity.sheet] ESI %s for char %s", resp.status_code, character_id)
        return
    d = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        con.execute("""
            INSERT INTO character_sheet
                (character_id, owner_id, name, description, birthday, gender,
                 race_id, bloodline_id, ancestry_id, corporation_id, alliance_id,
                 faction_id, security_status, title, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
            ON CONFLICT (character_id) DO UPDATE SET
                corporation_id = excluded.corporation_id,
                alliance_id = excluded.alliance_id,
                security_status = excluded.security_status,
                title = excluded.title,
                fetched_at = now()
        """, [character_id, owner_id, d.get("name"), d.get("description"),
              d.get("birthday"), d.get("gender"), d.get("race_id"),
              d.get("bloodline_id"), d.get("ancestry_id"), d.get("corporation_id"),
              d.get("alliance_id"), d.get("faction_id"), d.get("security_status"),
              d.get("title")])
    finally:
        con.close()
    logger.info("[identity.sheet] updated for char %s", character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Clones
# ─────────────────────────────────────────────────────────────────────────────

def populate_clones(owner_id: int, character_id: int, access_token: str) -> None:
    import json
    url = f"{ESI_BASE}/characters/{character_id}/clones/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[identity.clones] ESI %s for char %s", resp.status_code, character_id)
        return
    d = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        # Home clone
        home = d.get("home_location", {})
        if home:
            con.execute("""
                INSERT INTO character_clones
                    (character_id, clone_type, location_id, location_type, clone_name, fetched_at)
                VALUES (?, 'home', ?, ?, ?, now())
                ON CONFLICT (character_id, clone_type) DO UPDATE SET
                    location_id = excluded.location_id, fetched_at = now()
            """, [character_id, home.get("location_id"), home.get("location_type"), None])

        # Jump clones
        for jc in d.get("jump_clones", []):
            con.execute("""
                INSERT INTO character_clones
                    (character_id, clone_type, location_id, location_type, clone_name, implants_json, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, clone_type) DO UPDATE SET
                    location_id = excluded.location_id,
                    implants_json = excluded.implants_json, fetched_at = now()
            """, [character_id, f"jump_{jc.get('jump_clone_id', 0)}",
                  jc.get("location_id"), jc.get("location_type"),
                  jc.get("name"), json.dumps(jc.get("implants", []))])
    finally:
        con.close()
    logger.info("[identity.clones] updated for char %s", character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Implants
# ─────────────────────────────────────────────────────────────────────────────

def populate_implants(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/implants/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[identity.implants] ESI %s for char %s", resp.status_code, character_id)
        return
    data = resp.json()  # list of type_ids

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        con.execute("DELETE FROM character_implants WHERE character_id = ?", [character_id])
        for type_id in data:
            con.execute("""
                INSERT INTO character_implants (character_id, type_id, fetched_at)
                VALUES (?, ?, now())
            """, [character_id, type_id])
    finally:
        con.close()
    logger.info("[identity.implants] %d for char %s", len(data), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Attributes
# ─────────────────────────────────────────────────────────────────────────────

def populate_attributes(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/attributes/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[identity.attributes] ESI %s for char %s", resp.status_code, character_id)
        return
    d = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        con.execute("""
            INSERT INTO character_attributes
                (character_id, charisma, intelligence, memory, perception, willpower,
                 bonus_remaps, accrued_remap_cooldown_date, last_remap_date, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, now())
            ON CONFLICT (character_id) DO UPDATE SET
                charisma = excluded.charisma, intelligence = excluded.intelligence,
                memory = excluded.memory, perception = excluded.perception,
                willpower = excluded.willpower, bonus_remaps = excluded.bonus_remaps,
                fetched_at = now()
        """, [character_id, d.get("charisma"), d.get("intelligence"), d.get("memory"),
              d.get("perception"), d.get("willpower"), d.get("bonus_remaps", 0),
              d.get("accrued_remap_cooldown_date"), d.get("last_remap_date")])
    finally:
        con.close()
    logger.info("[identity.attributes] updated for char %s", character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Roles (corp roles in space, at HQ, etc.)
# ─────────────────────────────────────────────────────────────────────────────

def populate_roles(owner_id: int, character_id: int, access_token: str) -> None:
    import json
    url = f"{ESI_BASE}/characters/{character_id}/roles/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[identity.roles] ESI %s for char %s", resp.status_code, character_id)
        return
    d = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for role_type, role_list in d.items():
            con.execute("""
                INSERT INTO character_roles (character_id, role_type, roles_json, fetched_at)
                VALUES (?, ?, ?, now())
                ON CONFLICT (character_id, role_type) DO UPDATE SET
                    roles_json = excluded.roles_json, fetched_at = now()
            """, [character_id, role_type, json.dumps(role_list)])
    finally:
        con.close()
    logger.info("[identity.roles] updated for char %s", character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Agent research
# ─────────────────────────────────────────────────────────────────────────────

def populate_agent_research(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/agents_research/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[identity.agent_research] ESI %s for char %s", resp.status_code, character_id)
        return
    data = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for a in data:
            con.execute("""
                INSERT INTO character_agent_research
                    (character_id, agent_id, points_per_day, remainder_points, skill_type_id, started_at, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, agent_id) DO UPDATE SET
                    points_per_day = excluded.points_per_day,
                    remainder_points = excluded.remainder_points,
                    fetched_at = now()
            """, [character_id, a["agent_id"], a.get("points_per_day"),
                  a.get("remainder_points"), a.get("skill_type_id"), a.get("started_at")])
    finally:
        con.close()
    logger.info("[identity.agent_research] %d for char %s", len(data), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Projects
# ─────────────────────────────────────────────────────────────────────────────

def populate_projects(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/projects/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code in (403, 404):
            return
        logger.warning("[identity.projects] ESI %s for char %s", resp.status_code, character_id)
        return
    data = resp.json()

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        for p in data:
            con.execute("""
                INSERT INTO character_projects
                    (character_id, project_id, name, description, status, fetched_at)
                VALUES (?, ?, ?, ?, ?, now())
                ON CONFLICT (character_id, project_id) DO UPDATE SET
                    status = excluded.status, fetched_at = now()
            """, [character_id, p.get("project_id", p.get("id")),
                  p.get("name"), p.get("description"), p.get("status")])
    finally:
        con.close()
    logger.info("[identity.projects] %d for char %s", len(data), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Scope → Collector registry
# ─────────────────────────────────────────────────────────────────────────────

# character sheet is public — no scope needed
populate_character_sheet._no_scope = True


# ─────────────────────────────────────────────────────────────────────────────
# Skills
# ─────────────────────────────────────────────────────────────────────────────

def populate_skills(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/skills/"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = esi_get(url, headers=headers)
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[identity.skills] ESI %s for char %s", resp.status_code, character_id)
        return
    d = resp.json()
    skills = d.get("skills", [])
    if not skills:
        return

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        con.executemany("""
            INSERT INTO character_skills
                (character_id, skill_id, active_skill_level, trained_skill_level,
                 skillpoints_in_skill, fetched_at)
            VALUES (?, ?, ?, ?, ?, now())
            ON CONFLICT (character_id, skill_id) DO UPDATE SET
                active_skill_level   = excluded.active_skill_level,
                trained_skill_level  = excluded.trained_skill_level,
                skillpoints_in_skill = excluded.skillpoints_in_skill,
                fetched_at           = now()
        """, [
            (character_id, s["skill_id"], s.get("active_skill_level", 0),
             s.get("trained_skill_level", 0), s.get("skillpoints_in_skill", 0))
            for s in skills
        ])
    finally:
        con.close()
    logger.info("[identity.skills] %d skills for char %s", len(skills), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Assets (paginated, full-replacement)
# ─────────────────────────────────────────────────────────────────────────────

def populate_assets(owner_id: int, character_id: int, access_token: str) -> None:
    url = f"{ESI_BASE}/characters/{character_id}/assets/"
    headers = {"Authorization": f"Bearer {access_token}"}

    assets = []
    resp = esi_get(url, headers=headers, params={"page": 1})
    if not resp.ok:
        if resp.status_code == 403:
            return
        logger.warning("[identity.assets] ESI %s for char %s", resp.status_code, character_id)
        return
    assets.extend(resp.json())
    total_pages = int(resp.headers.get("X-Pages", 1))
    for page in range(2, total_pages + 1):
        r = esi_get(url, headers=headers, params={"page": page})
        if r.ok:
            assets.extend(r.json())

    con = connect_entity(owner_id)
    try:
        _ensure_tables(con)
        con.execute("DELETE FROM character_assets WHERE character_id = ?", [character_id])
        con.executemany("""
            INSERT INTO character_assets
                (character_id, item_id, type_id, location_id, location_type,
                 location_flag, quantity, is_singleton, is_blueprint_copy, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, now())
        """, [
            (character_id, a["item_id"], a["type_id"], a["location_id"],
             a.get("location_type"), a.get("location_flag"),
             a.get("quantity", 1), a.get("is_singleton", False), a.get("is_blueprint_copy"))
            for a in assets
        ])
    finally:
        con.close()
    logger.info("[identity.assets] %d items for char %s", len(assets), character_id)


# ─────────────────────────────────────────────────────────────────────────────
# Scope → Collector registry
# ─────────────────────────────────────────────────────────────────────────────

SCOPE_COLLECTORS: list[tuple[str, str, object]] = [
    ("esi-clones.read_clones.v1",            "clones",          populate_clones),
    ("esi-clones.read_implants.v1",           "implants",        populate_implants),
    ("esi-characters.read_attributes.v1",    "attributes",      populate_attributes),
    ("esi-characters.read_corporation_roles.v1", "roles",       populate_roles),
    ("esi-characters.read_agents_research.v1",   "agent_research", populate_agent_research),
    ("esi-characters.read_projects.v1",      "projects",        populate_projects),
    ("esi-skills.read_skills.v1",            "skills",          populate_skills),
    ("esi-assets.read_assets.v1",            "assets",          populate_assets),
]

NO_SCOPE_COLLECTORS: list[tuple[str, object]] = [
    ("character_sheet", populate_character_sheet),
]
