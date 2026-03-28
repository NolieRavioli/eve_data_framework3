# db/models.py

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON, BigInteger
from sqlalchemy.orm import declarative_base
import datetime

# ──────── Base Declarative Classes ───────────────────────────────────────────────
PublicBase = declarative_base()
PrivateBase = declarative_base()

# ──────── Public Database Models ──────────────────────────────────────────────────

class User(PublicBase):
    __tablename__   = "users"
    owner_id        = Column(Integer, index=True)
    character_id    = Column(Integer, primary_key=True)

class SiteAdmin(PublicBase):
    """Tracks which owner_ids have site-admin privileges."""
    __tablename__     = "site_admins"
    owner_id          = Column(Integer, primary_key=True)
    is_site_owner     = Column(Boolean, default=False)   # True only for the very first owner
    granted_by        = Column(Integer, nullable=True)   # owner_id that promoted them
    granted_at        = Column(DateTime, default=datetime.datetime.utcnow)

class SolarSystem(PublicBase):
    __tablename__       = "systems"
    system_id           = Column(Integer, primary_key=True)
    region_id           = Column(Integer, index=True)
    owner_id            = Column(Integer, index=True, nullable=True)    #corporation_id or alliance_id
    faction_id          = Column(Integer, nullable=True)
    constellation_id    = Column(Integer)
    security            = Column(Float)
    system_name         = Column(String)
    region_name         = Column(String, nullable=True)
    planets             = Column(JSON, nullable=True)   # List of planet IDs
    moons               = Column(JSON, nullable=True)   # List of moon IDs
    stargates           = Column(JSON, nullable=True)   # List of stargate IDs
    neighbors           = Column(JSON, nullable=True)   # List of connected system IDs
    
class Stargate(PublicBase):
    __tablename__           = "stargates"
    stargate_id             = Column(Integer, primary_key=True)
    owner_id                = Column(Integer, nullable=True)
    type_id                 = Column(Integer)
    system_id               = Column(Integer)
    destination_gate_id     = Column(Integer)
    destination_system_id   = Column(Integer)
    position                = Column(JSON)      # [x, y, z]

class MarketOrder(PublicBase):
    __tablename__   = "market_orders"
    order_id        = Column(Integer, primary_key=True)
    type_id         = Column(Integer)
    location_id     = Column(Integer)
    region_id       = Column(Integer)
    is_buy_order    = Column(Boolean)
    issued          = Column(DateTime)
    duration        = Column(Integer)
    price           = Column(Float)
    order_range     = Column(String)
    volume_remain   = Column(Integer)
    volume_total    = Column(Integer)
    min_volume      = Column(Integer)
    last_seen       = Column(DateTime, default=datetime.datetime.utcnow)

class PublicContract(PublicBase):
    __tablename__           = "public_contracts"
    contract_id             = Column(Integer, primary_key=True)
    region_id               = Column(Integer, index=True)
    issuer_id               = Column(Integer)
    issuer_corporation_id   = Column(Integer)
    contract_type           = Column(String)
    date_issued             = Column(DateTime)
    date_expired            = Column(DateTime)
    title                   = Column(String, nullable=True)
    volume                  = Column(Float, nullable=True)
    price                   = Column(Float, nullable=True)
    buyout                  = Column(Float, nullable=True)
    collateral              = Column(Float, nullable=True)
    reward                  = Column(Float, nullable=True)
    days_to_complete        = Column(Integer, nullable=True)
    start_location_id       = Column(Integer, nullable=True)
    end_location_id         = Column(Integer, nullable=True)
    for_corporation         = Column(Boolean, nullable=True)
    last_seen               = Column(DateTime, default=datetime.datetime.utcnow)

class Structure(PublicBase):
    __tablename__   = "structures"
    structure_id    = Column(Integer, primary_key=True)
    solar_system_id = Column(Integer, index=True)
    region_id       = Column(Integer, nullable=True)
    owner_id        = Column(Integer, nullable=True)
    name            = Column(String, nullable=True)
    type_id         = Column(Integer, nullable=True)
    position        = Column(JSON, nullable=True)
    last_seen       = Column(DateTime, default=datetime.datetime.utcnow)

class MarketStructure(PublicBase):
    __tablename__   = "market_structures"
    structure_id    = Column(Integer, primary_key=True)
    solar_system_id = Column(Integer, nullable=True)
    region_id       = Column(Integer, nullable=True)
    owner_id        = Column(Integer, nullable=True)
    name            = Column(String, nullable=True)
    type_id         = Column(Integer, nullable=True)
    position        = Column(JSON, nullable=True)
    last_seen       = Column(DateTime, default=datetime.datetime.utcnow)

# ──────── Private Database Models ────────────────────────────────────────────────

class Character(PrivateBase):
    __tablename__   = "characters"
    character_id    = Column(Integer, primary_key=True)
    name            = Column(String)
    corporation_id  = Column(Integer)
    birthday        = Column(String)
    security_status = Column(Float, nullable=True)
    alliance_id     = Column(Integer, nullable=True)
    access_token    = Column(String)
    refresh_token   = Column(String)
    expires_at      = Column(Float)
    scopes          = Column(String)

class Asset(PrivateBase):
    __tablename__       = "assets"
    item_id             = Column(BigInteger, primary_key=True)
    character_id        = Column(Integer, index=True)
    type_id             = Column(Integer)
    location_id         = Column(Integer)
    quantity            = Column(Integer)
    location_type       = Column(String)
    location_flag       = Column(Integer)
    is_blueprint_copy   = Column(Boolean, nullable=True)

class Blueprint(PrivateBase):
    __tablename__           = "blueprints"
    item_id                 = Column(BigInteger, primary_key=True)
    character_id            = Column(Integer, index=True)
    type_id                 = Column(Integer)
    location_id             = Column(Integer)
    location_flag           = Column(String)
    material_efficiency     = Column(Integer)
    time_efficiency         = Column(Integer)
    runs                    = Column(Integer)
    quantity                = Column(Integer)

class IndustryJob(PrivateBase):
    __tablename__           = "industry_jobs"
    job_id                  = Column(BigInteger, primary_key=True)
    character_id            = Column(Integer, index=True)
    activity_id             = Column(Integer)
    blueprint_id            = Column(BigInteger)
    blueprint_location_id   = Column(BigInteger)
    blueprint_type_id       = Column(Integer)
    cost                    = Column(Float)
    duration                = Column(Integer)
    facility_id             = Column(BigInteger)
    installer_id            = Column(BigInteger)
    licensed_runs           = Column(Integer)
    output_location_id      = Column(BigInteger)
    runs                    = Column(Integer)
    status                  = Column(String)
    start_date              = Column(DateTime)
    end_date                = Column(DateTime)
    
class PersonalBookmark(PrivateBase):
    __tablename__   = "personal_bookmarks"
    bookmark_id     = Column(BigInteger, primary_key=True)
    character_id    = Column(Integer, index=True)
    folder_id       = Column(BigInteger)
    location_id     = Column(BigInteger)
    item_id         = Column(BigInteger)
    label           = Column(String)
    created         = Column(DateTime)
    coordinates     = Column(JSON)
    notes           = Column(String)

class Skill(PrivateBase):
    __tablename__           = "skills"
    character_id            = Column(Integer, primary_key=True)
    skill_id                = Column(Integer, primary_key=True)
    active_level            = Column(Integer)
    skillpoints_in_skill    = Column(Integer)
    trained_skill_level     = Column(Integer)
    skill_active            = Column(Boolean)

class SkillQueue(PrivateBase):
    __tablename__   = "skill_queues"
    character_id    = Column(Integer, primary_key=True)
    queue_position  = Column(Integer, primary_key=True)
    skill_id        = Column(Integer)
    finish_level    = Column(Integer)
    finish_date     = Column(DateTime)

class WalletBalance(PrivateBase):
    __tablename__   = "wallet_balances"
    character_id    = Column(Integer, primary_key=True)
    balance         = Column(Float)

class WalletJournal(PrivateBase):
    __tablename__   = "wallet_journals"
    journal_id      = Column(BigInteger, primary_key=True)
    character_id    = Column(Integer, index=True)
    date            = Column(String)
    description     = Column(String)
    ref_type        = Column(String)
    amount          = Column(Float, nullable=True)
    balance         = Column(Float, nullable=True)
    context_id      = Column(BigInteger, nullable=True)
    context_id_type = Column(String, nullable=True)
    first_party_id  = Column(Integer, nullable=True)
    second_party_id = Column(Integer, nullable=True)
    reason          = Column(String, nullable=True)

class WalletTransaction(PrivateBase):
    __tablename__   = "wallet_transactions"
    transaction_id              = Column(BigInteger, primary_key=True)
    character_id    = Column(Integer, index=True)
    location_id     = Column(Integer)
    type_id         = Column(Float)
    quantity        = Column(Integer)
    amount          = Column(Float)
    unit_price      = Column(Float)
    date            = Column(DateTime)
    is_buy          = Column(Boolean)
    is_personal     = Column(Boolean)

# ══════════════════════════════════════════════════════════════════════════════
#  EXTENDED PERSONAL MODELS
# ══════════════════════════════════════════════════════════════════════════════

class CharacterAttributes(PrivateBase):
    __tablename__                   = "character_attributes"
    character_id                    = Column(Integer, primary_key=True)
    perception                      = Column(Integer, nullable=True)
    memory                          = Column(Integer, nullable=True)
    willpower                       = Column(Integer, nullable=True)
    intelligence                    = Column(Integer, nullable=True)
    charisma                        = Column(Integer, nullable=True)
    bonus_remaps                    = Column(Integer, nullable=True)
    last_remap_date                 = Column(DateTime, nullable=True)
    accrued_remap_cooldown_date     = Column(DateTime, nullable=True)

class HomeLocation(PrivateBase):
    __tablename__   = "home_location"
    character_id    = Column(Integer, primary_key=True)
    location_id     = Column(BigInteger, nullable=True)
    location_type   = Column(String, nullable=True)

class JumpClone(PrivateBase):
    __tablename__   = "jump_clones"
    jump_clone_id   = Column(Integer, primary_key=True)
    character_id    = Column(Integer, index=True)
    location_id     = Column(BigInteger, nullable=True)
    location_type   = Column(String, nullable=True)
    clone_name      = Column(String, nullable=True)
    implants        = Column(JSON, nullable=True)   # list of type_ids

class ActiveImplant(PrivateBase):
    __tablename__       = "active_implants"
    character_id        = Column(Integer, primary_key=True)
    implant_type_id     = Column(Integer, primary_key=True)

class Contact(PrivateBase):
    __tablename__       = "contacts"
    character_id        = Column(Integer, primary_key=True)
    contact_id          = Column(Integer, primary_key=True)
    contact_type        = Column(String)
    standing            = Column(Float)
    is_watched          = Column(Boolean, nullable=True)
    is_blocked          = Column(Boolean, nullable=True)
    label_ids           = Column(JSON, nullable=True)

class ContactLabel(PrivateBase):
    __tablename__   = "contact_labels"
    character_id    = Column(Integer, primary_key=True)
    label_id        = Column(BigInteger, primary_key=True)
    label_name      = Column(String)

class PersonalContract(PrivateBase):
    __tablename__               = "personal_contracts"
    contract_id                 = Column(Integer, primary_key=True)
    character_id                = Column(Integer, index=True)
    issuer_id                   = Column(Integer, nullable=True)
    issuer_corporation_id       = Column(Integer, nullable=True)
    assignee_id                 = Column(Integer, nullable=True)
    acceptor_id                 = Column(Integer, nullable=True)
    contract_type               = Column(String, nullable=True)
    availability                = Column(String, nullable=True)
    status                      = Column(String, nullable=True)
    date_issued                 = Column(DateTime, nullable=True)
    date_expired                = Column(DateTime, nullable=True)
    date_accepted               = Column(DateTime, nullable=True)
    date_completed              = Column(DateTime, nullable=True)
    title                       = Column(String, nullable=True)
    volume                      = Column(Float, nullable=True)
    price                       = Column(Float, nullable=True)
    reward                      = Column(Float, nullable=True)
    buyout                      = Column(Float, nullable=True)
    collateral                  = Column(Float, nullable=True)
    days_to_complete            = Column(Integer, nullable=True)
    start_location_id           = Column(BigInteger, nullable=True)
    end_location_id             = Column(BigInteger, nullable=True)
    for_corporation             = Column(Boolean, nullable=True)

class PersonalContractItem(PrivateBase):
    __tablename__   = "personal_contract_items"
    record_id       = Column(BigInteger, primary_key=True)
    contract_id     = Column(Integer, index=True)
    character_id    = Column(Integer, index=True)
    type_id         = Column(Integer)
    quantity        = Column(Integer)
    is_included     = Column(Boolean)
    is_singleton    = Column(Boolean)
    raw_quantity    = Column(Integer, nullable=True)

class MailHeader(PrivateBase):
    __tablename__   = "mail_headers"
    mail_id         = Column(Integer, primary_key=True)
    character_id    = Column(Integer, index=True)
    from_id         = Column(Integer, nullable=True)
    subject         = Column(String, nullable=True)
    timestamp       = Column(DateTime, nullable=True)
    label_ids       = Column(JSON, nullable=True)
    recipients      = Column(JSON, nullable=True)   # list of {recipient_id, recipient_type}
    is_read         = Column(Boolean, nullable=True)

class MailLabel(PrivateBase):
    __tablename__       = "mail_labels"
    character_id        = Column(Integer, primary_key=True)
    label_id            = Column(Integer, primary_key=True)
    label_name          = Column(String, nullable=True)
    unread_count        = Column(Integer, nullable=True)
    color               = Column(String, nullable=True)

class MailList(PrivateBase):
    __tablename__       = "mail_lists"
    character_id        = Column(Integer, primary_key=True)
    mailing_list_id     = Column(Integer, primary_key=True)
    name                = Column(String, nullable=True)

class CalendarEvent(PrivateBase):
    __tablename__   = "calendar_events"
    character_id    = Column(Integer, primary_key=True)
    event_id        = Column(Integer, primary_key=True)
    event_date      = Column(DateTime, nullable=True)
    title           = Column(String, nullable=True)
    duration        = Column(Integer, nullable=True)
    importance      = Column(Integer, nullable=True)
    event_response  = Column(String, nullable=True)
    owner_id        = Column(Integer, nullable=True)
    owner_name      = Column(String, nullable=True)
    owner_type      = Column(String, nullable=True)

class Notification(PrivateBase):
    __tablename__           = "notifications"
    notification_id         = Column(BigInteger, primary_key=True)
    character_id            = Column(Integer, index=True)
    sender_id               = Column(Integer, nullable=True)
    sender_type             = Column(String, nullable=True)
    timestamp               = Column(DateTime, nullable=True)
    notification_type       = Column(String, nullable=True)
    is_read                 = Column(Boolean, nullable=True)
    text                    = Column(String, nullable=True)

class CharacterStanding(PrivateBase):
    __tablename__   = "character_standings"
    character_id    = Column(Integer, primary_key=True)
    from_id         = Column(Integer, primary_key=True)
    from_type       = Column(String)
    standing        = Column(Float)

class Fitting(PrivateBase):
    __tablename__   = "fittings"
    fitting_id      = Column(Integer, primary_key=True)
    character_id    = Column(Integer, index=True)
    name            = Column(String, nullable=True)
    ship_type_id    = Column(Integer, nullable=True)
    description     = Column(String, nullable=True)

class FittingItem(PrivateBase):
    __tablename__   = "fitting_items"
    fitting_id      = Column(Integer, primary_key=True)
    flag            = Column(String, primary_key=True)
    character_id    = Column(Integer, index=True)
    type_id         = Column(Integer)
    quantity        = Column(Integer)

class PlanetaryColony(PrivateBase):
    __tablename__       = "planetary_colonies"
    character_id        = Column(Integer, primary_key=True)
    planet_id           = Column(Integer, primary_key=True)
    planet_type         = Column(String, nullable=True)
    solar_system_id     = Column(Integer, nullable=True)
    last_update         = Column(DateTime, nullable=True)
    num_pins            = Column(Integer, nullable=True)
    upgrade_level       = Column(Integer, nullable=True)

class PlanetaryPin(PrivateBase):
    __tablename__           = "planetary_pins"
    pin_id                  = Column(BigInteger, primary_key=True)
    character_id            = Column(Integer, index=True)
    planet_id               = Column(Integer, index=True)
    type_id                 = Column(Integer)
    latitude                = Column(Float, nullable=True)
    longitude               = Column(Float, nullable=True)
    install_time            = Column(DateTime, nullable=True)
    expiry_time             = Column(DateTime, nullable=True)
    last_cycle_start        = Column(DateTime, nullable=True)
    contents                = Column(JSON, nullable=True)
    extractor_details       = Column(JSON, nullable=True)
    factory_details         = Column(JSON, nullable=True)

class PlanetaryRoute(PrivateBase):
    __tablename__       = "planetary_routes"
    route_id            = Column(BigInteger, primary_key=True)
    character_id        = Column(Integer, index=True)
    planet_id           = Column(Integer, index=True)
    destination_pin_id  = Column(BigInteger)
    source_pin_id       = Column(BigInteger)
    content_type_id     = Column(Integer)
    quantity            = Column(Float)
    waypoints           = Column(JSON, nullable=True)

class JumpFatigue(PrivateBase):
    __tablename__               = "jump_fatigue"
    character_id                = Column(Integer, primary_key=True)
    jump_fatigue                = Column(DateTime, nullable=True)
    last_jump_date              = Column(DateTime, nullable=True)
    jump_fatigue_expire_date    = Column(DateTime, nullable=True)

class LoyaltyPoint(PrivateBase):
    __tablename__   = "loyalty_points"
    character_id    = Column(Integer, primary_key=True)
    corporation_id  = Column(Integer, primary_key=True)
    lp_balance      = Column(Integer)

class Medal(PrivateBase):
    __tablename__   = "medals"
    medal_id        = Column(Integer, primary_key=True)
    character_id    = Column(Integer, primary_key=True)
    corporation_id  = Column(Integer, nullable=True)
    title           = Column(String, nullable=True)
    description     = Column(String, nullable=True)
    date            = Column(DateTime, nullable=True)
    issued_by       = Column(Integer, nullable=True)
    reason          = Column(String, nullable=True)
    status          = Column(String, nullable=True)

class MiningLedger(PrivateBase):
    __tablename__       = "mining_ledger"
    character_id        = Column(Integer, primary_key=True)
    date                = Column(String, primary_key=True)
    solar_system_id     = Column(Integer, primary_key=True)
    type_id             = Column(Integer, primary_key=True)
    quantity            = Column(BigInteger)

class CharacterMarketOrder(PrivateBase):
    __tablename__   = "character_market_orders"
    order_id        = Column(BigInteger, primary_key=True)
    character_id    = Column(Integer, index=True)
    type_id         = Column(Integer)
    location_id     = Column(BigInteger)
    region_id       = Column(Integer, nullable=True)
    is_buy_order    = Column(Boolean)
    issued          = Column(DateTime)
    duration        = Column(Integer)
    price           = Column(Float)
    volume_remain   = Column(Integer)
    volume_total    = Column(Integer)
    min_volume      = Column(Integer, nullable=True)
    escrow          = Column(Float, nullable=True)
    is_corporation  = Column(Boolean, nullable=True)
    state           = Column(String, nullable=True)
    is_history      = Column(Boolean, default=False)

class KillmailRef(PrivateBase):
    __tablename__       = "killmail_refs"
    killmail_id         = Column(Integer, primary_key=True)
    character_id        = Column(Integer, index=True)
    killmail_hash       = Column(String)
    is_victim           = Column(Boolean)
    solar_system_id     = Column(Integer, nullable=True)
    killmail_time       = Column(DateTime, nullable=True)

# ══════════════════════════════════════════════════════════════════════════════
#  CORPORATION MODELS  (stored in per-owner private DB, tagged by corporation_id)
# ══════════════════════════════════════════════════════════════════════════════

class CorpInfo(PrivateBase):
    __tablename__       = "corp_info"
    corporation_id      = Column(Integer, primary_key=True)
    alliance_id         = Column(Integer, nullable=True)
    ceo_id              = Column(Integer, nullable=True)
    creator_id          = Column(Integer, nullable=True)
    date_founded        = Column(String, nullable=True)
    description         = Column(String, nullable=True)
    home_station_id     = Column(Integer, nullable=True)
    member_count        = Column(Integer, nullable=True)
    name                = Column(String, nullable=True)
    shares              = Column(BigInteger, nullable=True)
    tax_rate            = Column(Float, nullable=True)
    ticker              = Column(String, nullable=True)
    war_eligible        = Column(Boolean, nullable=True)
    last_seen           = Column(DateTime, default=datetime.datetime.utcnow)

class CorpRole(PrivateBase):
    __tablename__   = "corp_roles"
    character_id    = Column(Integer, primary_key=True)
    corporation_id  = Column(Integer, primary_key=True)
    role_name       = Column(String, primary_key=True)
    role_type       = Column(String, primary_key=True)   # roles / roles_at_hq / roles_at_base / roles_at_other

class CorpTitle(PrivateBase):
    __tablename__   = "corp_titles"
    title_id        = Column(Integer, primary_key=True)
    corporation_id  = Column(Integer, primary_key=True)
    title_name      = Column(String, nullable=True)
    roles           = Column(JSON, nullable=True)

class CorpMember(PrivateBase):
    __tablename__       = "corp_members"
    character_id        = Column(Integer, primary_key=True)
    corporation_id      = Column(Integer, primary_key=True)
    base_id             = Column(Integer, nullable=True)
    joined              = Column(DateTime, nullable=True)
    logoff_date         = Column(DateTime, nullable=True)
    logon_date          = Column(DateTime, nullable=True)
    ship_type_id        = Column(Integer, nullable=True)
    start_date          = Column(DateTime, nullable=True)
    title_ids           = Column(JSON, nullable=True)
    location_id         = Column(BigInteger, nullable=True)

class CorpDivision(PrivateBase):
    __tablename__       = "corp_divisions"
    corporation_id      = Column(Integer, primary_key=True)
    division_number     = Column(Integer, primary_key=True)
    division_type       = Column(String, primary_key=True)   # hangar / wallet
    name                = Column(String, nullable=True)

class CorpStanding(PrivateBase):
    __tablename__   = "corp_standings"
    corporation_id  = Column(Integer, primary_key=True)
    from_id         = Column(Integer, primary_key=True)
    from_type       = Column(String)
    standing        = Column(Float)

class CorpContract(PrivateBase):
    __tablename__               = "corp_contracts"
    contract_id                 = Column(Integer, primary_key=True)
    corporation_id              = Column(Integer, index=True)
    issuer_id                   = Column(Integer, nullable=True)
    issuer_corporation_id       = Column(Integer, nullable=True)
    assignee_id                 = Column(Integer, nullable=True)
    acceptor_id                 = Column(Integer, nullable=True)
    contract_type               = Column(String, nullable=True)
    availability                = Column(String, nullable=True)
    status                      = Column(String, nullable=True)
    date_issued                 = Column(DateTime, nullable=True)
    date_expired                = Column(DateTime, nullable=True)
    date_accepted               = Column(DateTime, nullable=True)
    date_completed              = Column(DateTime, nullable=True)
    title                       = Column(String, nullable=True)
    volume                      = Column(Float, nullable=True)
    price                       = Column(Float, nullable=True)
    reward                      = Column(Float, nullable=True)
    collateral                  = Column(Float, nullable=True)
    buyout                      = Column(Float, nullable=True)
    start_location_id           = Column(BigInteger, nullable=True)
    end_location_id             = Column(BigInteger, nullable=True)

class CorpContractItem(PrivateBase):
    __tablename__   = "corp_contract_items"
    record_id       = Column(BigInteger, primary_key=True)
    contract_id     = Column(Integer, index=True)
    corporation_id  = Column(Integer, index=True)
    type_id         = Column(Integer)
    quantity        = Column(Integer)
    is_included     = Column(Boolean)
    is_singleton    = Column(Boolean)

class CorpMarketOrder(PrivateBase):
    __tablename__       = "corp_market_orders"
    order_id            = Column(BigInteger, primary_key=True)
    corporation_id      = Column(Integer, index=True)
    type_id             = Column(Integer)
    location_id         = Column(BigInteger)
    region_id           = Column(Integer, nullable=True)
    is_buy_order        = Column(Boolean)
    issued              = Column(DateTime)
    duration            = Column(Integer)
    price               = Column(Float)
    volume_remain       = Column(Integer)
    volume_total        = Column(Integer)
    min_volume          = Column(Integer, nullable=True)
    escrow              = Column(Float, nullable=True)
    wallet_division     = Column(Integer, nullable=True)
    state               = Column(String, nullable=True)
    is_history          = Column(Boolean, default=False)

class CorpBlueprint(PrivateBase):
    __tablename__           = "corp_blueprints"
    item_id                 = Column(BigInteger, primary_key=True)
    corporation_id          = Column(Integer, index=True)
    type_id                 = Column(Integer)
    location_id             = Column(BigInteger)
    location_flag           = Column(String)
    material_efficiency     = Column(Integer)
    time_efficiency         = Column(Integer)
    runs                    = Column(Integer)
    quantity                = Column(Integer)

class CorpCustomsOffice(PrivateBase):
    __tablename__           = "corp_customs_offices"
    item_id                 = Column(BigInteger, primary_key=True)
    corporation_id          = Column(Integer, index=True)
    solar_system_id         = Column(Integer, nullable=True)
    allowed_access          = Column(JSON, nullable=True)
    reinforce_exit_end      = Column(Integer, nullable=True)
    reinforce_exit_start    = Column(Integer, nullable=True)
    standing_level          = Column(String, nullable=True)
    tax_rates               = Column(JSON, nullable=True)

class CorpStructure(PrivateBase):
    __tablename__           = "corp_structures"
    structure_id            = Column(BigInteger, primary_key=True)
    corporation_id          = Column(Integer, index=True)
    solar_system_id         = Column(Integer, nullable=True)
    type_id                 = Column(Integer, nullable=True)
    name                    = Column(String, nullable=True)
    profile_id              = Column(Integer, nullable=True)
    state                   = Column(String, nullable=True)
    state_timer_end         = Column(DateTime, nullable=True)
    state_timer_start       = Column(DateTime, nullable=True)
    unanchors_at            = Column(DateTime, nullable=True)
    services                = Column(JSON, nullable=True)
    fuel_expires            = Column(DateTime, nullable=True)
    next_reinforce_hour     = Column(Integer, nullable=True)
    last_seen               = Column(DateTime, default=datetime.datetime.utcnow)

class CorpKillmailRef(PrivateBase):
    __tablename__       = "corp_killmail_refs"
    killmail_id         = Column(Integer, primary_key=True)
    corporation_id      = Column(Integer, primary_key=True)
    killmail_hash       = Column(String)
    is_victim           = Column(Boolean)
    solar_system_id     = Column(Integer, nullable=True)
    killmail_time       = Column(DateTime, nullable=True)

class CorpIndustryJob(PrivateBase):
    __tablename__           = "corp_industry_jobs"
    job_id                  = Column(BigInteger, primary_key=True)
    corporation_id          = Column(Integer, index=True)
    activity_id             = Column(Integer)
    blueprint_id            = Column(BigInteger)
    blueprint_type_id       = Column(Integer)
    cost                    = Column(Float)
    duration                = Column(Integer)
    facility_id             = Column(BigInteger)
    installer_id            = Column(BigInteger)
    licensed_runs           = Column(Integer)
    output_location_id      = Column(BigInteger)
    runs                    = Column(Integer)
    status                  = Column(String)
    start_date              = Column(DateTime)
    end_date                = Column(DateTime)

class CorpWalletJournal(PrivateBase):
    __tablename__       = "corp_wallet_journal"
    journal_id          = Column(BigInteger, primary_key=True)
    division            = Column(Integer, primary_key=True)
    corporation_id      = Column(Integer, index=True)
    date                = Column(String)
    description         = Column(String, nullable=True)
    ref_type            = Column(String, nullable=True)
    amount              = Column(Float, nullable=True)
    balance             = Column(Float, nullable=True)
    context_id          = Column(BigInteger, nullable=True)
    context_id_type     = Column(String, nullable=True)
    first_party_id      = Column(Integer, nullable=True)
    second_party_id     = Column(Integer, nullable=True)
    reason              = Column(String, nullable=True)

class CorpWalletTransaction(PrivateBase):
    __tablename__       = "corp_wallet_transactions"
    transaction_id      = Column(BigInteger, primary_key=True)
    division            = Column(Integer, primary_key=True)
    corporation_id      = Column(Integer, index=True)
    location_id         = Column(BigInteger)
    type_id             = Column(Integer)
    quantity            = Column(Integer)
    amount              = Column(Float)
    unit_price          = Column(Float)
    date                = Column(DateTime)
    is_buy              = Column(Boolean)
    journal_ref_id      = Column(BigInteger, nullable=True)

class CorpMining(PrivateBase):
    __tablename__               = "corp_mining"
    corporation_id              = Column(Integer, primary_key=True)
    observer_id                 = Column(BigInteger, primary_key=True)
    observed_character_id       = Column(Integer, primary_key=True)
    type_id                     = Column(Integer, primary_key=True)
    last_updated                = Column(String, primary_key=True)
    quantity                    = Column(BigInteger)
    observer_type               = Column(String, nullable=True)
