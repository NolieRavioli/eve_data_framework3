"""collectors/corp/infrastructure.py — corp_facilities, corp_starbases, corp_structures, corp_customs_offices."""

from __future__ import annotations

import logging

from core.io.entity_db import connect_entity
from core.esi import esi_get

logger = logging.getLogger(__name__)

ESI_BASE = "https://esi.evetech.net/latest"


def _ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_facilities (
            facility_id BIGINT PRIMARY KEY,
            system_id   INTEGER,
            type_id     INTEGER,
            fetched_at  TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_starbases (
            starbase_id             BIGINT PRIMARY KEY,
            type_id                 INTEGER NOT NULL,
            system_id               INTEGER NOT NULL,
            moon_id                 INTEGER,
            state                   TEXT,
            state_timer_start       TIMESTAMP,
            state_timer_end         TIMESTAMP,
            unanchor_at             TIMESTAMP,
            reinforced_until        TIMESTAMP,
            onlined_since           TIMESTAMP,
            allow_alliance_members  BOOLEAN,
            allow_corp_members      BOOLEAN,
            attack_if_at_war        BOOLEAN,
            use_alliance_standings  BOOLEAN,
            fuel_bay_take           TEXT,
            anchor                  TEXT,
            online                  TEXT,
            offline                 TEXT,
            unanchor                TEXT,
            details_fetched_at      TIMESTAMP,
            fetched_at              TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_structures (
            structure_id            BIGINT PRIMARY KEY,
            corporation_id          BIGINT,
            type_id                 INTEGER,
            system_id               INTEGER,
            name                    TEXT,
            state                   TEXT,
            state_timer_start       TIMESTAMP,
            state_timer_end         TIMESTAMP,
            fuel_expires            TIMESTAMP,
            profile_id              INTEGER,
            reinforce_hour          INTEGER,
            services_json           TEXT,
            fetched_at              TIMESTAMP DEFAULT now()
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS corp_customs_offices (
            office_id                   BIGINT PRIMARY KEY,
            system_id                   INTEGER NOT NULL,
            standing_level              TEXT,
            allow_access_with_standings BOOLEAN DEFAULT TRUE,
            allow_alliance_access       BOOLEAN DEFAULT FALSE,
            bad_standing_tax_rate       REAL,
            corporation_tax_rate        REAL,
            excellent_standing_tax_rate REAL,
            good_standing_tax_rate      REAL,
            neutral_standing_tax_rate   REAL,
            reinforce_exit_end          INTEGER,
            reinforce_exit_start        INTEGER,
            terrible_standing_tax_rate  REAL,
            fetched_at                  TIMESTAMP DEFAULT now()
        )
    """)


def fetch_corp_infrastructure(corporation_id: int, character_id: int, access_token: str) -> None:
    import json
    headers = {"Authorization": f"Bearer {access_token}"}
    con = connect_entity(corporation_id)
    try:
        _ensure_tables(con)

        # Facilities
        r = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/facilities/", headers=headers)
        if r.ok:
            for f in r.json():
                con.execute("""
                    INSERT INTO corp_facilities (facility_id, system_id, type_id, fetched_at)
                    VALUES (?, ?, ?, now())
                    ON CONFLICT (facility_id) DO UPDATE SET fetched_at = now()
                """, [f["facility_id"], f.get("system_id"), f.get("type_id")])

        # Starbases (paginated) + inline detail
        sb_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/starbases/",
                          params={"page": 1}, headers=headers)
        if sb_resp.ok:
            starbases = sb_resp.json()
            total = int(sb_resp.headers.get("X-Pages", 1))
            for page in range(2, total + 1):
                r2 = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/starbases/",
                             params={"page": page}, headers=headers)
                if r2.ok:
                    starbases.extend(r2.json())

            for sb in starbases:
                sb_id = sb["starbase_id"]
                # Inline detail
                det_r = esi_get(
                    f"{ESI_BASE}/corporations/{corporation_id}/starbases/{sb_id}/",
                    params={"system_id": sb.get("system_id")}, headers=headers)
                det = det_r.json() if det_r.ok else {}
                con.execute("""
                    INSERT INTO corp_starbases
                        (starbase_id, type_id, system_id, moon_id, state,
                         state_timer_start, state_timer_end, unanchor_at, reinforced_until, onlined_since,
                         allow_alliance_members, allow_corp_members, attack_if_at_war,
                         use_alliance_standings, fuel_bay_take, anchor, online, offline, unanchor,
                         details_fetched_at, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now(), now())
                    ON CONFLICT (starbase_id) DO UPDATE SET
                        state = excluded.state, fetched_at = now()
                """, [sb_id, sb["type_id"], sb["system_id"], sb.get("moon_id"), sb.get("state"),
                      sb.get("state_timer_start"), sb.get("state_timer_end"),
                      sb.get("unanchor_at"), sb.get("reinforced_until"), sb.get("onlined_since"),
                      det.get("allow_alliance_members"), det.get("allow_corp_members"),
                      det.get("attack_if_at_war"), det.get("use_alliance_standings"),
                      det.get("fuel_bay_take"), det.get("anchor"), det.get("online"),
                      det.get("offline"), det.get("unanchor")])

        # Structures (paginated)
        st_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/structures/",
                          params={"page": 1}, headers=headers)
        if st_resp.ok:
            structures = st_resp.json()
            total = int(st_resp.headers.get("X-Pages", 1))
            for page in range(2, total + 1):
                r2 = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/structures/",
                             params={"page": page}, headers=headers)
                if r2.ok:
                    structures.extend(r2.json())
            for s in structures:
                con.execute("""
                    INSERT INTO corp_structures
                        (structure_id, corporation_id, type_id, system_id, name, state,
                         state_timer_start, state_timer_end, fuel_expires, profile_id,
                         reinforce_hour, services_json, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                    ON CONFLICT (structure_id) DO UPDATE SET
                        state = excluded.state, fuel_expires = excluded.fuel_expires,
                        fetched_at = now()
                """, [s["structure_id"], s.get("corporation_id"), s.get("type_id"),
                      s.get("system_id"), s.get("name"), s.get("state"),
                      s.get("state_timer_start"), s.get("state_timer_end"),
                      s.get("fuel_expires"), s.get("profile_id"), s.get("reinforce_hour"),
                      json.dumps(s.get("services", []))])

        # Customs Offices (paginated)
        co_resp = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/customs_offices/",
                          params={"page": 1}, headers=headers)
        if co_resp.ok:
            customs = co_resp.json()
            total = int(co_resp.headers.get("X-Pages", 1))
            for page in range(2, total + 1):
                r2 = esi_get(f"{ESI_BASE}/corporations/{corporation_id}/customs_offices/",
                             params={"page": page}, headers=headers)
                if r2.ok:
                    customs.extend(r2.json())
            for c in customs:
                con.execute("""
                    INSERT INTO corp_customs_offices
                        (office_id, system_id, standing_level, allow_access_with_standings,
                         allow_alliance_access, bad_standing_tax_rate, corporation_tax_rate,
                         excellent_standing_tax_rate, good_standing_tax_rate,
                         neutral_standing_tax_rate, reinforce_exit_end, reinforce_exit_start,
                         terrible_standing_tax_rate, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
                    ON CONFLICT (office_id) DO UPDATE SET fetched_at = now()
                """, [c["office_id"], c.get("system_id"), c.get("standing_level"),
                      c.get("allow_access_with_standings", True),
                      c.get("allow_alliance_access", False),
                      c.get("bad_standing_tax_rate"), c.get("corporation_tax_rate"),
                      c.get("excellent_standing_tax_rate"), c.get("good_standing_tax_rate"),
                      c.get("neutral_standing_tax_rate"), c.get("reinforce_exit_end"),
                      c.get("reinforce_exit_start"), c.get("terrible_standing_tax_rate")])
    finally:
        con.close()
    logger.info("[corp.infrastructure] updated for corp %s", corporation_id)


def run_for_all_corps() -> None:
    from collectors.corp import get_corp_token_map
    token_map = get_corp_token_map()
    for corp_id, (char_id, access_token) in token_map.items():
        try:
            fetch_corp_infrastructure(corp_id, char_id, access_token)
        except Exception:
            logger.exception("[corp.infrastructure] failed for corp %s", corp_id)
