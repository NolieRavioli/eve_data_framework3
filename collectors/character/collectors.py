"""analysis/character/collectors.py — additional per-character ESI collectors.

Each collector fetches one ESI dataset and upserts into the owner's private SQLite.
Table DDL is owned here — each ensure_*table function is idempotent.

Signature contract:
    def populate_<domain>(owner_id, character_id, access_token) -> None

Called by populate_all() in populate.py after scope gating.
"""

from __future__ import annotations

import logging

import sqlalchemy as sa

from core.db.private import get_private_session, initialize_private_database

logger = logging.getLogger(__name__)

_text = sa.text


# ═══════════════════════════════════════════════════════════════════════════════
# DDL helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _ensure_table(engine, ddl: str) -> None:
    with engine.connect() as con:
        con.execute(_text(ddl))
        con.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# Mail
# ═══════════════════════════════════════════════════════════════════════════════

_DDL_MAIL = """
CREATE TABLE IF NOT EXISTS character_mail (
    mail_id         INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL,
    sender_id       INTEGER,
    subject         TEXT,
    timestamp       TEXT,
    is_read         INTEGER DEFAULT 0
)
"""


def populate_mail(owner_id: int, character_id: int, access_token: str) -> None:
    from core.esi.personal.mail import get_characters_character_id_mail
    engine = initialize_private_database(owner_id)
    _ensure_table(engine, _DDL_MAIL)
    data = get_characters_character_id_mail(character_id, access_token)
    if not data:
        return
    with engine.connect() as con:
        for m in data:
            con.execute(_text("""
                INSERT INTO character_mail (mail_id, character_id, sender_id, subject, timestamp, is_read)
                VALUES (:mail_id, :character_id, :sender_id, :subject, :timestamp, :is_read)
                ON CONFLICT (mail_id) DO UPDATE SET
                    is_read = excluded.is_read
            """), {
                "mail_id": m["mail_id"],
                "character_id": character_id,
                "sender_id": m.get("from"),
                "subject": m.get("subject", ""),
                "timestamp": m.get("timestamp", ""),
                "is_read": int(m.get("is_read", False)),
            })
        con.commit()
    logger.info("[Collectors] mail: %d headers for char %s", len(data), character_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Contracts
# ═══════════════════════════════════════════════════════════════════════════════

_DDL_CONTRACTS = """
CREATE TABLE IF NOT EXISTS character_contracts (
    contract_id     INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL,
    issuer_id       INTEGER,
    type            TEXT,
    status          TEXT,
    title           TEXT,
    price           REAL DEFAULT 0,
    date_issued     TEXT,
    date_expired    TEXT,
    date_completed  TEXT
)
"""


def populate_contracts(owner_id: int, character_id: int, access_token: str) -> None:
    from core.esi.personal.contracts import get_characters_character_id_contracts
    engine = initialize_private_database(owner_id)
    _ensure_table(engine, _DDL_CONTRACTS)
    data = get_characters_character_id_contracts(character_id, access_token)
    if not data:
        return
    with engine.connect() as con:
        for c in data:
            con.execute(_text("""
                INSERT INTO character_contracts
                    (contract_id, character_id, issuer_id, type, status, title, price,
                     date_issued, date_expired, date_completed)
                VALUES (:contract_id, :character_id, :issuer_id, :type, :status, :title, :price,
                        :date_issued, :date_expired, :date_completed)
                ON CONFLICT (contract_id) DO UPDATE SET
                    status = excluded.status, date_completed = excluded.date_completed
            """), {
                "contract_id": c["contract_id"],
                "character_id": character_id,
                "issuer_id": c.get("issuer_id"),
                "type": c.get("type", ""),
                "status": c.get("status", ""),
                "title": c.get("title", ""),
                "price": c.get("price", 0),
                "date_issued": c.get("date_issued", ""),
                "date_expired": c.get("date_expired", ""),
                "date_completed": c.get("date_completed"),
            })
        con.commit()
    logger.info("[Collectors] contracts: %d for char %s", len(data), character_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Calendar
# ═══════════════════════════════════════════════════════════════════════════════

_DDL_CALENDAR = """
CREATE TABLE IF NOT EXISTS character_calendar (
    event_id        INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL,
    title           TEXT,
    event_date      TEXT,
    importance      INTEGER DEFAULT 0,
    event_response  TEXT
)
"""


def populate_calendar(owner_id: int, character_id: int, access_token: str) -> None:
    from core.esi.personal.calendar import get_characters_character_id_calendar
    engine = initialize_private_database(owner_id)
    _ensure_table(engine, _DDL_CALENDAR)
    data = get_characters_character_id_calendar(character_id, access_token)
    if not data:
        return
    with engine.connect() as con:
        for e in data:
            con.execute(_text("""
                INSERT INTO character_calendar
                    (event_id, character_id, title, event_date, importance, event_response)
                VALUES (:event_id, :character_id, :title, :event_date, :importance, :event_response)
                ON CONFLICT (event_id) DO UPDATE SET
                    event_response = excluded.event_response
            """), {
                "event_id": e["event_id"],
                "character_id": character_id,
                "title": e.get("title", ""),
                "event_date": e.get("event_date", ""),
                "importance": e.get("importance", 0),
                "event_response": e.get("event_response", ""),
            })
        con.commit()
    logger.info("[Collectors] calendar: %d events for char %s", len(data), character_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Contacts
# ═══════════════════════════════════════════════════════════════════════════════

_DDL_CONTACTS = """
CREATE TABLE IF NOT EXISTS character_contacts (
    contact_id      INTEGER NOT NULL,
    character_id    INTEGER NOT NULL,
    contact_type    TEXT,
    standing        REAL DEFAULT 0,
    label_ids       TEXT,
    PRIMARY KEY (character_id, contact_id)
)
"""


def populate_contacts(owner_id: int, character_id: int, access_token: str) -> None:
    from core.esi.personal.contacts import get_characters_character_id_contacts
    engine = initialize_private_database(owner_id)
    _ensure_table(engine, _DDL_CONTACTS)
    data = get_characters_character_id_contacts(character_id, access_token)
    if not data:
        return
    with engine.connect() as con:
        for c in data:
            label_ids = ",".join(str(l) for l in (c.get("label_ids") or []))
            con.execute(_text("""
                INSERT INTO character_contacts
                    (contact_id, character_id, contact_type, standing, label_ids)
                VALUES (:contact_id, :character_id, :contact_type, :standing, :label_ids)
                ON CONFLICT (character_id, contact_id) DO UPDATE SET
                    standing = excluded.standing, label_ids = excluded.label_ids
            """), {
                "contact_id": c["contact_id"],
                "character_id": character_id,
                "contact_type": c.get("contact_type", ""),
                "standing": c.get("standing", 0),
                "label_ids": label_ids,
            })
        con.commit()
    logger.info("[Collectors] contacts: %d for char %s", len(data), character_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Notifications
# ═══════════════════════════════════════════════════════════════════════════════

_DDL_NOTIFICATIONS = """
CREATE TABLE IF NOT EXISTS character_notifications (
    notification_id INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL,
    sender_id       INTEGER,
    sender_type     TEXT,
    type            TEXT,
    timestamp       TEXT,
    is_read         INTEGER DEFAULT 0,
    text            TEXT
)
"""


def populate_notifications(owner_id: int, character_id: int, access_token: str) -> None:
    from core.esi.personal.character import get_characters_character_id_notifications
    engine = initialize_private_database(owner_id)
    _ensure_table(engine, _DDL_NOTIFICATIONS)
    data = get_characters_character_id_notifications(character_id, access_token)
    if not data:
        return
    with engine.connect() as con:
        for n in data:
            con.execute(_text("""
                INSERT INTO character_notifications
                    (notification_id, character_id, sender_id, sender_type, type, timestamp, is_read, text)
                VALUES (:notification_id, :character_id, :sender_id, :sender_type, :type, :timestamp, :is_read, :text)
                ON CONFLICT (notification_id) DO UPDATE SET
                    is_read = excluded.is_read
            """), {
                "notification_id": n["notification_id"],
                "character_id": character_id,
                "sender_id": n.get("sender_id"),
                "sender_type": n.get("sender_type", ""),
                "type": n.get("type", ""),
                "timestamp": n.get("timestamp", ""),
                "is_read": int(n.get("is_read", False)),
                "text": n.get("text", ""),
            })
        con.commit()
    logger.info("[Collectors] notifications: %d for char %s", len(data), character_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Industry Jobs
# ═══════════════════════════════════════════════════════════════════════════════

_DDL_INDUSTRY = """
CREATE TABLE IF NOT EXISTS character_industry (
    job_id          INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL,
    activity_id     INTEGER,
    blueprint_type_id INTEGER,
    output_type_id  INTEGER,
    status          TEXT,
    runs            INTEGER DEFAULT 0,
    start_date      TEXT,
    end_date        TEXT,
    station_id      INTEGER
)
"""


def populate_industry(owner_id: int, character_id: int, access_token: str) -> None:
    from core.esi.personal.industry import get_characters_character_id_industry_jobs
    engine = initialize_private_database(owner_id)
    _ensure_table(engine, _DDL_INDUSTRY)
    data = get_characters_character_id_industry_jobs(character_id, access_token)
    if not data:
        return
    with engine.connect() as con:
        for j in data:
            con.execute(_text("""
                INSERT INTO character_industry
                    (job_id, character_id, activity_id, blueprint_type_id, output_type_id,
                     status, runs, start_date, end_date, station_id)
                VALUES (:job_id, :character_id, :activity_id, :blueprint_type_id, :output_type_id,
                        :status, :runs, :start_date, :end_date, :station_id)
                ON CONFLICT (job_id) DO UPDATE SET
                    status = excluded.status, end_date = excluded.end_date
            """), {
                "job_id": j["job_id"],
                "character_id": character_id,
                "activity_id": j.get("activity_id"),
                "blueprint_type_id": j.get("blueprint_type_id"),
                "output_type_id": j.get("product_type_id"),
                "status": j.get("status", ""),
                "runs": j.get("runs", 0),
                "start_date": j.get("start_date", ""),
                "end_date": j.get("end_date", ""),
                "station_id": j.get("station_id"),
            })
        con.commit()
    logger.info("[Collectors] industry: %d jobs for char %s", len(data), character_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Personal Market Orders
# ═══════════════════════════════════════════════════════════════════════════════

_DDL_ORDERS = """
CREATE TABLE IF NOT EXISTS character_orders (
    order_id        INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL,
    type_id         INTEGER NOT NULL,
    is_buy_order    INTEGER DEFAULT 0,
    price           REAL,
    volume_remain   INTEGER,
    volume_total    INTEGER,
    location_id     INTEGER,
    state           TEXT,
    issued          TEXT,
    duration        INTEGER DEFAULT 0
)
"""


def populate_orders(owner_id: int, character_id: int, access_token: str) -> None:
    from core.esi.personal.market import get_characters_character_id_orders
    engine = initialize_private_database(owner_id)
    _ensure_table(engine, _DDL_ORDERS)
    data = get_characters_character_id_orders(character_id, access_token)
    if not data:
        return
    with engine.connect() as con:
        for o in data:
            con.execute(_text("""
                INSERT INTO character_orders
                    (order_id, character_id, type_id, is_buy_order, price, volume_remain,
                     volume_total, location_id, state, issued, duration)
                VALUES (:order_id, :character_id, :type_id, :is_buy_order, :price, :volume_remain,
                        :volume_total, :location_id, :state, :issued, :duration)
                ON CONFLICT (order_id) DO UPDATE SET
                    price = excluded.price, volume_remain = excluded.volume_remain,
                    state = excluded.state
            """), {
                "order_id": o["order_id"],
                "character_id": character_id,
                "type_id": o["type_id"],
                "is_buy_order": int(o.get("is_buy_order", False)),
                "price": o.get("price", 0),
                "volume_remain": o.get("volume_remain", 0),
                "volume_total": o.get("volume_total", 0),
                "location_id": o.get("location_id"),
                "state": o.get("state", "open"),
                "issued": o.get("issued", ""),
                "duration": o.get("duration", 0),
            })
        con.commit()
    logger.info("[Collectors] orders: %d for char %s", len(data), character_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Blueprints
# ═══════════════════════════════════════════════════════════════════════════════

_DDL_BLUEPRINTS = """
CREATE TABLE IF NOT EXISTS character_blueprints (
    item_id         INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL,
    type_id         INTEGER NOT NULL,
    location_id     INTEGER,
    material_efficiency INTEGER DEFAULT 0,
    time_efficiency INTEGER DEFAULT 0,
    runs            INTEGER DEFAULT -1,
    quantity        INTEGER DEFAULT 1
)
"""


def populate_blueprints(owner_id: int, character_id: int, access_token: str) -> None:
    from core.esi.personal.character import get_characters_character_id_blueprints
    engine = initialize_private_database(owner_id)
    _ensure_table(engine, _DDL_BLUEPRINTS)
    data = get_characters_character_id_blueprints(character_id, access_token)
    if not data:
        return
    with engine.connect() as con:
        for bp in data:
            con.execute(_text("""
                INSERT INTO character_blueprints
                    (item_id, character_id, type_id, location_id, material_efficiency,
                     time_efficiency, runs, quantity)
                VALUES (:item_id, :character_id, :type_id, :location_id, :material_efficiency,
                        :time_efficiency, :runs, :quantity)
                ON CONFLICT (item_id) DO UPDATE SET
                    material_efficiency = excluded.material_efficiency,
                    time_efficiency = excluded.time_efficiency,
                    runs = excluded.runs, quantity = excluded.quantity
            """), {
                "item_id": bp["item_id"],
                "character_id": character_id,
                "type_id": bp["type_id"],
                "location_id": bp.get("location_id"),
                "material_efficiency": bp.get("material_efficiency", 0),
                "time_efficiency": bp.get("time_efficiency", 0),
                "runs": bp.get("runs", -1),
                "quantity": bp.get("quantity", 1),
            })
        con.commit()
    logger.info("[Collectors] blueprints: %d for char %s", len(data), character_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Planetary Interaction
# ═══════════════════════════════════════════════════════════════════════════════

_DDL_PLANETS = """
CREATE TABLE IF NOT EXISTS character_planets (
    planet_id       INTEGER NOT NULL,
    character_id    INTEGER NOT NULL,
    planet_type     TEXT,
    solar_system_id INTEGER,
    num_pins        INTEGER DEFAULT 0,
    last_update     TEXT,
    PRIMARY KEY (character_id, planet_id)
)
"""


def populate_planets(owner_id: int, character_id: int, access_token: str) -> None:
    from core.esi.personal.planetary_interaction import (
        get_characters_character_id_planets,
    )
    engine = initialize_private_database(owner_id)
    _ensure_table(engine, _DDL_PLANETS)
    data = get_characters_character_id_planets(character_id, access_token)
    if not data:
        return
    with engine.connect() as con:
        for p in data:
            con.execute(_text("""
                INSERT INTO character_planets
                    (planet_id, character_id, planet_type, solar_system_id, num_pins, last_update)
                VALUES (:planet_id, :character_id, :planet_type, :solar_system_id, :num_pins, :last_update)
                ON CONFLICT (character_id, planet_id) DO UPDATE SET
                    num_pins = excluded.num_pins, last_update = excluded.last_update
            """), {
                "planet_id": p["planet_id"],
                "character_id": character_id,
                "planet_type": p.get("planet_type", ""),
                "solar_system_id": p.get("solar_system_id"),
                "num_pins": p.get("num_pins", 0),
                "last_update": p.get("last_update", ""),
            })
        con.commit()
    logger.info("[Collectors] planets: %d for char %s", len(data), character_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Mining Ledger
# ═══════════════════════════════════════════════════════════════════════════════

_DDL_MINING = """
CREATE TABLE IF NOT EXISTS character_mining (
    character_id    INTEGER NOT NULL,
    date            TEXT NOT NULL,
    type_id         INTEGER NOT NULL,
    solar_system_id INTEGER NOT NULL,
    quantity        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (character_id, date, type_id, solar_system_id)
)
"""


def populate_mining(owner_id: int, character_id: int, access_token: str) -> None:
    from core.esi.personal.industry import get_characters_character_id_mining
    engine = initialize_private_database(owner_id)
    _ensure_table(engine, _DDL_MINING)
    data = get_characters_character_id_mining(character_id, access_token)
    if not data:
        return
    with engine.connect() as con:
        for m in data:
            con.execute(_text("""
                INSERT INTO character_mining
                    (character_id, date, type_id, solar_system_id, quantity)
                VALUES (:character_id, :date, :type_id, :solar_system_id, :quantity)
                ON CONFLICT (character_id, date, type_id, solar_system_id) DO UPDATE SET
                    quantity = excluded.quantity
            """), {
                "character_id": character_id,
                "date": m.get("date", ""),
                "type_id": m["type_id"],
                "solar_system_id": m["solar_system_id"],
                "quantity": m.get("quantity", 0),
            })
        con.commit()
    logger.info("[Collectors] mining: %d entries for char %s", len(data), character_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Loyalty Points
# ═══════════════════════════════════════════════════════════════════════════════

_DDL_LOYALTY = """
CREATE TABLE IF NOT EXISTS character_loyalty (
    character_id    INTEGER NOT NULL,
    corporation_id  INTEGER NOT NULL,
    loyalty_points  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (character_id, corporation_id)
)
"""


def populate_loyalty(owner_id: int, character_id: int, access_token: str) -> None:
    from core.esi.personal.loyalty import get_characters_character_id_loyalty_points
    engine = initialize_private_database(owner_id)
    _ensure_table(engine, _DDL_LOYALTY)
    data = get_characters_character_id_loyalty_points(character_id, access_token)
    if not data:
        return
    with engine.connect() as con:
        for lp in data:
            con.execute(_text("""
                INSERT INTO character_loyalty (character_id, corporation_id, loyalty_points)
                VALUES (:character_id, :corporation_id, :loyalty_points)
                ON CONFLICT (character_id, corporation_id) DO UPDATE SET
                    loyalty_points = excluded.loyalty_points
            """), {
                "character_id": character_id,
                "corporation_id": lp["corporation_id"],
                "loyalty_points": lp.get("loyalty_points", 0),
            })
        con.commit()
    logger.info("[Collectors] loyalty: %d corps for char %s", len(data), character_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Research Agents
# ═══════════════════════════════════════════════════════════════════════════════

_DDL_RESEARCH = """
CREATE TABLE IF NOT EXISTS character_research (
    character_id    INTEGER NOT NULL,
    agent_id        INTEGER NOT NULL,
    skill_type_id   INTEGER,
    points_per_day  REAL DEFAULT 0,
    remainder_points REAL DEFAULT 0,
    started_at      TEXT,
    PRIMARY KEY (character_id, agent_id)
)
"""


def populate_research(owner_id: int, character_id: int, access_token: str) -> None:
    from core.esi.personal.character import get_characters_character_id_agents_research
    engine = initialize_private_database(owner_id)
    _ensure_table(engine, _DDL_RESEARCH)
    data = get_characters_character_id_agents_research(character_id, access_token)
    if not data:
        return
    with engine.connect() as con:
        for r in data:
            con.execute(_text("""
                INSERT INTO character_research
                    (character_id, agent_id, skill_type_id, points_per_day, remainder_points, started_at)
                VALUES (:character_id, :agent_id, :skill_type_id, :points_per_day, :remainder_points, :started_at)
                ON CONFLICT (character_id, agent_id) DO UPDATE SET
                    points_per_day = excluded.points_per_day,
                    remainder_points = excluded.remainder_points
            """), {
                "character_id": character_id,
                "agent_id": r["agent_id"],
                "skill_type_id": r.get("skill_type_id"),
                "points_per_day": r.get("points_per_day", 0),
                "remainder_points": r.get("remainder_points", 0),
                "started_at": r.get("started_at", ""),
            })
        con.commit()
    logger.info("[Collectors] research: %d agents for char %s", len(data), character_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Fittings
# ═══════════════════════════════════════════════════════════════════════════════

_DDL_FITTINGS = """
CREATE TABLE IF NOT EXISTS character_fittings (
    fitting_id      INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL,
    name            TEXT,
    description     TEXT,
    ship_type_id    INTEGER NOT NULL,
    items           TEXT
)
"""


def populate_fittings(owner_id: int, character_id: int, access_token: str) -> None:
    import json
    from core.esi.personal.fittings import get_characters_character_id_fittings
    engine = initialize_private_database(owner_id)
    _ensure_table(engine, _DDL_FITTINGS)
    data = get_characters_character_id_fittings(character_id, access_token)
    if not data:
        return
    with engine.connect() as con:
        for f in data:
            con.execute(_text("""
                INSERT INTO character_fittings
                    (fitting_id, character_id, name, description, ship_type_id, items)
                VALUES (:fitting_id, :character_id, :name, :description, :ship_type_id, :items)
                ON CONFLICT (fitting_id) DO UPDATE SET
                    name = excluded.name, description = excluded.description,
                    items = excluded.items
            """), {
                "fitting_id": f["fitting_id"],
                "character_id": character_id,
                "name": f.get("name", ""),
                "description": f.get("description", ""),
                "ship_type_id": f.get("ship_type_id", 0),
                "items": json.dumps(f.get("items", [])),
            })
        con.commit()
    logger.info("[Collectors] fittings: %d for char %s", len(data), character_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Standings
# ═══════════════════════════════════════════════════════════════════════════════

_DDL_STANDINGS = """
CREATE TABLE IF NOT EXISTS character_standings (
    character_id    INTEGER NOT NULL,
    from_id         INTEGER NOT NULL,
    from_type       TEXT NOT NULL,
    standing        REAL DEFAULT 0,
    PRIMARY KEY (character_id, from_id, from_type)
)
"""


def populate_standings(owner_id: int, character_id: int, access_token: str) -> None:
    from core.esi.personal.character import get_characters_character_id_standings
    engine = initialize_private_database(owner_id)
    _ensure_table(engine, _DDL_STANDINGS)
    data = get_characters_character_id_standings(character_id, access_token)
    if not data:
        return
    with engine.connect() as con:
        for s in data:
            con.execute(_text("""
                INSERT INTO character_standings (character_id, from_id, from_type, standing)
                VALUES (:character_id, :from_id, :from_type, :standing)
                ON CONFLICT (character_id, from_id, from_type) DO UPDATE SET
                    standing = excluded.standing
            """), {
                "character_id": character_id,
                "from_id": s["from_id"],
                "from_type": s.get("from_type", ""),
                "standing": s.get("standing", 0),
            })
        con.commit()
    logger.info("[Collectors] standings: %d for char %s", len(data), character_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Killmails (recent)
# ═══════════════════════════════════════════════════════════════════════════════

_DDL_KILLMAILS = """
CREATE TABLE IF NOT EXISTS character_killmails (
    killmail_id     INTEGER PRIMARY KEY,
    character_id    INTEGER NOT NULL,
    killmail_hash   TEXT NOT NULL
)
"""


def populate_killmails(owner_id: int, character_id: int, access_token: str) -> None:
    from core.esi.personal.killmails import get_characters_character_id_killmails_recent
    engine = initialize_private_database(owner_id)
    _ensure_table(engine, _DDL_KILLMAILS)
    data = get_characters_character_id_killmails_recent(character_id, access_token)
    if not data:
        return
    with engine.connect() as con:
        for km in data:
            con.execute(_text("""
                INSERT INTO character_killmails (killmail_id, character_id, killmail_hash)
                VALUES (:killmail_id, :character_id, :killmail_hash)
                ON CONFLICT (killmail_id) DO NOTHING
            """), {
                "killmail_id": km["killmail_id"],
                "character_id": character_id,
                "killmail_hash": km.get("killmail_hash", ""),
            })
        con.commit()
    logger.info("[Collectors] killmails: %d for char %s", len(data), character_id)


# ═══════════════════════════════════════════════════════════════════════════════
# Scope → Collector registry
# ═══════════════════════════════════════════════════════════════════════════════

SCOPE_COLLECTORS: list[tuple[str, str, callable]] = [
    ("esi-mail.read_mail.v1",                          "mail",          populate_mail),
    ("esi-contracts.read_character_contracts.v1",       "contracts",     populate_contracts),
    ("esi-calendar.read_calendar_events.v1",            "calendar",      populate_calendar),
    ("esi-characters.read_contacts.v1",                 "contacts",      populate_contacts),
    ("esi-characters.read_notifications.v1",            "notifications", populate_notifications),
    ("esi-industry.read_character_jobs.v1",             "industry",      populate_industry),
    ("esi-markets.read_character_orders.v1",            "orders",        populate_orders),
    ("esi-characters.read_blueprints.v1",               "blueprints",    populate_blueprints),
    ("esi-planets.manage_planets.v1",                   "planets",       populate_planets),
    ("esi-industry.read_character_mining.v1",           "mining",        populate_mining),
    ("esi-characters.read_loyalty.v1",                  "loyalty",       populate_loyalty),
    ("esi-characters.read_agents_research.v1",          "research",      populate_research),
    ("esi-fittings.read_fittings.v1",                   "fittings",      populate_fittings),
    ("esi-characters.read_standings.v1",                "standings",     populate_standings),
    ("esi-killmails.read_killmails.v1",                 "killmails",     populate_killmails),
]
