"""
core/esi/generated/schemas.py
-------------------------
AUTO-GENERATED — do not edit by hand.
Source: ESI compatibility date 2025-12-16
Schemas: 263

TypedDict stubs and type aliases for ESI response schemas.
These are informational; the runtime uses plain dicts.
"""
# ruff: noqa
from __future__ import annotations
from typing import Any, TypedDict

SCHEMA_COUNT: int = 263

# AccessListID: integer
AccessListID = int

class AllianceDetail(TypedDict, total=False):
    creator_corporation_id: Any  # required=True
    creator_id: Any  # required=True
    date_founded: str  # required=True
    executor_corporation_id: Any  # required=False
    faction_id: Any  # required=False
    name: str  # required=True
    ticker: str  # required=True

# AllianceID: integer
AllianceID = int

# AlliancesAllianceIdContactsGet: array of dict
AlliancesAllianceIdContactsGet = list[dict]

# AlliancesAllianceIdContactsLabelsGet: array of dict
AlliancesAllianceIdContactsLabelsGet = list[dict]

# AlliancesAllianceIdCorporationsGet: array of int
AlliancesAllianceIdCorporationsGet = list[int]

class AlliancesAllianceIdIconsGet(TypedDict, total=False):
    px128x128: str  # required=False
    px64x64: str  # required=False

# AlliancesGet: array of int
AlliancesGet = list[int]

# ArchetypeID: integer
ArchetypeID = int

# AttributeID: integer
AttributeID = int

# BloodlineID: integer
BloodlineID = int

# CharacterID: integer
CharacterID = int

# CharactersAffiliationPost: array of dict
CharactersAffiliationPost = list[dict]

# CharactersCharacterIdAgentsResearchGet: array of dict
CharactersCharacterIdAgentsResearchGet = list[dict]

# CharactersCharacterIdAssetsGet: array of dict
CharactersCharacterIdAssetsGet = list[dict]

# CharactersCharacterIdAssetsLocationsPost: array of dict
CharactersCharacterIdAssetsLocationsPost = list[dict]

# CharactersCharacterIdAssetsNamesPost: array of dict
CharactersCharacterIdAssetsNamesPost = list[dict]

class CharactersCharacterIdAttributesGet(TypedDict, total=False):
    accrued_remap_cooldown_date: str  # required=False
    bonus_remaps: int  # required=False
    charisma: int  # required=True
    intelligence: int  # required=True
    last_remap_date: str  # required=False
    memory: int  # required=True
    perception: int  # required=True
    willpower: int  # required=True

# CharactersCharacterIdBlueprintsGet: array of dict
CharactersCharacterIdBlueprintsGet = list[dict]

# CharactersCharacterIdCalendarEventIdAttendeesGet: array of dict
CharactersCharacterIdCalendarEventIdAttendeesGet = list[dict]

class CharactersCharacterIdCalendarEventIdGet(TypedDict, total=False):
    """Full details of a specific event"""
    date: str  # required=True
    duration: int  # required=True
    event_id: int  # required=True
    importance: int  # required=True
    owner_id: int  # required=True
    owner_name: str  # required=True
    owner_type: str  # required=True
    response: str  # required=True
    text: str  # required=True
    title: str  # required=True

# CharactersCharacterIdCalendarGet: array of dict
CharactersCharacterIdCalendarGet = list[dict]

class CharactersCharacterIdClonesGet(TypedDict, total=False):
    home_location: dict  # required=False
    jump_clones: list[dict]  # required=True
    last_clone_jump_date: str  # required=False
    last_station_change_date: str  # required=False

# CharactersCharacterIdContactsGet: array of dict
CharactersCharacterIdContactsGet = list[dict]

# CharactersCharacterIdContactsLabelsGet: array of dict
CharactersCharacterIdContactsLabelsGet = list[dict]

# CharactersCharacterIdContactsPost: array of int
CharactersCharacterIdContactsPost = list[int]

# CharactersCharacterIdContractsContractIdBidsGet: array of dict
CharactersCharacterIdContractsContractIdBidsGet = list[dict]

# CharactersCharacterIdContractsContractIdItemsGet: array of dict
CharactersCharacterIdContractsContractIdItemsGet = list[dict]

# CharactersCharacterIdContractsGet: array of dict
CharactersCharacterIdContractsGet = list[dict]

# CharactersCharacterIdCorporationhistoryGet: array of dict
CharactersCharacterIdCorporationhistoryGet = list[dict]

# CharactersCharacterIdCspaPost: number
CharactersCharacterIdCspaPost = float

class CharactersCharacterIdFatigueGet(TypedDict, total=False):
    jump_fatigue_expire_date: str  # required=False
    last_jump_date: str  # required=False
    last_update_date: str  # required=False

# CharactersCharacterIdFittingsGet: array of dict
CharactersCharacterIdFittingsGet = list[dict]

class CharactersCharacterIdFittingsPost(TypedDict, total=False):
    """201 created object"""
    fitting_id: int  # required=True

class CharactersCharacterIdFleetGet(TypedDict, total=False):
    fleet_boss_id: int  # required=True
    fleet_id: int  # required=True
    role: str  # required=True
    squad_id: int  # required=True
    wing_id: int  # required=True

class CharactersCharacterIdFwStatsGet(TypedDict, total=False):
    current_rank: int  # required=False
    enlisted_on: str  # required=False
    faction_id: int  # required=False
    highest_rank: int  # required=False
    kills: dict  # required=True
    victory_points: dict  # required=True

# CharactersCharacterIdImplantsGet: array of int
CharactersCharacterIdImplantsGet = list[int]

# CharactersCharacterIdIndustryJobsGet: array of dict
CharactersCharacterIdIndustryJobsGet = list[dict]

# CharactersCharacterIdKillmailsRecentGet: array of dict
CharactersCharacterIdKillmailsRecentGet = list[dict]

class CharactersCharacterIdLocationGet(TypedDict, total=False):
    solar_system_id: int  # required=True
    station_id: int  # required=False
    structure_id: int  # required=False

# CharactersCharacterIdLoyaltyPointsGet: array of dict
CharactersCharacterIdLoyaltyPointsGet = list[dict]

# CharactersCharacterIdMailGet: array of dict
CharactersCharacterIdMailGet = list[dict]

class CharactersCharacterIdMailLabelsGet(TypedDict, total=False):
    labels: list[dict]  # required=False
    total_unread_count: int  # required=False

# CharactersCharacterIdMailLabelsPost: integer
CharactersCharacterIdMailLabelsPost = int

# CharactersCharacterIdMailListsGet: array of dict
CharactersCharacterIdMailListsGet = list[dict]

class CharactersCharacterIdMailMailIdGet(TypedDict, total=False):
    body: str  # required=False
    from_: int  # required=False
    labels: list[int]  # required=False
    read: bool  # required=False
    recipients: list[dict]  # required=False
    subject: str  # required=False
    timestamp: str  # required=False

# CharactersCharacterIdMailPost: integer
CharactersCharacterIdMailPost = int

# CharactersCharacterIdMedalsGet: array of dict
CharactersCharacterIdMedalsGet = list[dict]

# CharactersCharacterIdMiningGet: array of dict
CharactersCharacterIdMiningGet = list[dict]

# CharactersCharacterIdNotificationsContactsGet: array of dict
CharactersCharacterIdNotificationsContactsGet = list[dict]

# CharactersCharacterIdNotificationsGet: array of dict
CharactersCharacterIdNotificationsGet = list[dict]

class CharactersCharacterIdOnlineGet(TypedDict, total=False):
    last_login: str  # required=False
    last_logout: str  # required=False
    logins: int  # required=False
    online: bool  # required=True

# CharactersCharacterIdOrdersGet: array of dict
CharactersCharacterIdOrdersGet = list[dict]

# CharactersCharacterIdOrdersHistoryGet: array of dict
CharactersCharacterIdOrdersHistoryGet = list[dict]

# CharactersCharacterIdPlanetsGet: array of dict
CharactersCharacterIdPlanetsGet = list[dict]

class CharactersCharacterIdPlanetsPlanetIdGet(TypedDict, total=False):
    links: list[dict]  # required=True
    pins: list[dict]  # required=True
    routes: list[dict]  # required=True

class CharactersCharacterIdPortraitGet(TypedDict, total=False):
    px128x128: str  # required=False
    px256x256: str  # required=False
    px512x512: str  # required=False
    px64x64: str  # required=False

class CharactersCharacterIdRolesGet(TypedDict, total=False):
    roles: list[str]  # required=False
    roles_at_base: list[str]  # required=False
    roles_at_hq: list[str]  # required=False
    roles_at_other: list[str]  # required=False

class CharactersCharacterIdSearchGet(TypedDict, total=False):
    agent: list[int]  # required=False
    alliance: list[int]  # required=False
    character: list[int]  # required=False
    constellation: list[int]  # required=False
    corporation: list[int]  # required=False
    faction: list[int]  # required=False
    inventory_type: list[int]  # required=False
    region: list[int]  # required=False
    solar_system: list[int]  # required=False
    station: list[int]  # required=False
    structure: list[int]  # required=False

class CharactersCharacterIdShipGet(TypedDict, total=False):
    ship_item_id: int  # required=True
    ship_name: str  # required=True
    ship_type_id: int  # required=True

# CharactersCharacterIdStandingsGet: array of dict
CharactersCharacterIdStandingsGet = list[dict]

# CharactersCharacterIdTitlesGet: array of dict
CharactersCharacterIdTitlesGet = list[dict]

# CharactersCharacterIdWalletGet: number
CharactersCharacterIdWalletGet = float

# CharactersCharacterIdWalletJournalGet: array of dict
CharactersCharacterIdWalletJournalGet = list[dict]

# CharactersCharacterIdWalletTransactionsGet: array of dict
CharactersCharacterIdWalletTransactionsGet = list[dict]

class CharactersDetail(TypedDict, total=False):
    alliance_id: Any  # required=False
    birthday: str  # required=True
    bloodline_id: Any  # required=True
    corporation_id: Any  # required=True
    description: str  # required=False
    faction_id: Any  # required=False
    gender: str  # required=True
    name: str  # required=True
    race_id: Any  # required=True
    security_status: float  # required=False
    title: str  # required=False

class CharactersFreelanceJobsListing(TypedDict, total=False):
    freelance_jobs: list[Any]  # required=True

class CharactersFreelanceJobsParticipation(TypedDict, total=False):
    contributed: int  # required=True
    last_modified: str  # required=True
    state: str  # required=True

class CharactersSkillqueueSkill(TypedDict, total=False):
    finish_date: str  # required=False
    finished_level: int  # required=True
    level_end_sp: int  # required=False
    level_start_sp: int  # required=False
    queue_position: int  # required=True
    skill_id: Any  # required=True
    start_date: str  # required=False
    training_start_sp: int  # required=False

class CharactersSkills(TypedDict, total=False):
    skills: list[Any]  # required=True
    total_sp: int  # required=True
    unallocated_sp: int  # required=False

class CharactersSkillsSkill(TypedDict, total=False):
    active_skill_level: int  # required=True
    skill_id: int  # required=True
    skillpoints_in_skill: int  # required=True
    trained_skill_level: int  # required=True

# CompatibilityDate: string
CompatibilityDate = str

# ConstellationID: integer
ConstellationID = int

# ContractsPublicBidsContractIdGet: array of dict
ContractsPublicBidsContractIdGet = list[dict]

# ContractsPublicItemsContractIdGet: array of dict
ContractsPublicItemsContractIdGet = list[dict]

# ContractsPublicRegionIdGet: array of dict
ContractsPublicRegionIdGet = list[dict]

# CorporationCorporationIdMiningExtractionsGet: array of dict
CorporationCorporationIdMiningExtractionsGet = list[dict]

# CorporationCorporationIdMiningObserversGet: array of dict
CorporationCorporationIdMiningObserversGet = list[dict]

# CorporationCorporationIdMiningObserversObserverIdGet: array of dict
CorporationCorporationIdMiningObserversObserverIdGet = list[dict]

# CorporationID: integer
CorporationID = int

# CorporationsCorporationIdAlliancehistoryGet: array of dict
CorporationsCorporationIdAlliancehistoryGet = list[dict]

# CorporationsCorporationIdAssetsGet: array of dict
CorporationsCorporationIdAssetsGet = list[dict]

# CorporationsCorporationIdAssetsLocationsPost: array of dict
CorporationsCorporationIdAssetsLocationsPost = list[dict]

# CorporationsCorporationIdAssetsNamesPost: array of dict
CorporationsCorporationIdAssetsNamesPost = list[dict]

# CorporationsCorporationIdBlueprintsGet: array of dict
CorporationsCorporationIdBlueprintsGet = list[dict]

# CorporationsCorporationIdContactsGet: array of dict
CorporationsCorporationIdContactsGet = list[dict]

# CorporationsCorporationIdContactsLabelsGet: array of dict
CorporationsCorporationIdContactsLabelsGet = list[dict]

# CorporationsCorporationIdContainersLogsGet: array of dict
CorporationsCorporationIdContainersLogsGet = list[dict]

# CorporationsCorporationIdContractsContractIdBidsGet: array of dict
CorporationsCorporationIdContractsContractIdBidsGet = list[dict]

# CorporationsCorporationIdContractsContractIdItemsGet: array of dict
CorporationsCorporationIdContractsContractIdItemsGet = list[dict]

# CorporationsCorporationIdContractsGet: array of dict
CorporationsCorporationIdContractsGet = list[dict]

# CorporationsCorporationIdCustomsOfficesGet: array of dict
CorporationsCorporationIdCustomsOfficesGet = list[dict]

class CorporationsCorporationIdDivisionsGet(TypedDict, total=False):
    hangar: list[dict]  # required=False
    wallet: list[dict]  # required=False

# CorporationsCorporationIdFacilitiesGet: array of dict
CorporationsCorporationIdFacilitiesGet = list[dict]

class CorporationsCorporationIdFwStatsGet(TypedDict, total=False):
    enlisted_on: str  # required=False
    faction_id: int  # required=False
    kills: dict  # required=True
    pilots: int  # required=False
    victory_points: dict  # required=True

class CorporationsCorporationIdIconsGet(TypedDict, total=False):
    px128x128: str  # required=False
    px256x256: str  # required=False
    px64x64: str  # required=False

# CorporationsCorporationIdIndustryJobsGet: array of dict
CorporationsCorporationIdIndustryJobsGet = list[dict]

# CorporationsCorporationIdKillmailsRecentGet: array of dict
CorporationsCorporationIdKillmailsRecentGet = list[dict]

# CorporationsCorporationIdMedalsGet: array of dict
CorporationsCorporationIdMedalsGet = list[dict]

# CorporationsCorporationIdMedalsIssuedGet: array of dict
CorporationsCorporationIdMedalsIssuedGet = list[dict]

# CorporationsCorporationIdMembersGet: array of int
CorporationsCorporationIdMembersGet = list[int]

# CorporationsCorporationIdMembersLimitGet: integer
CorporationsCorporationIdMembersLimitGet = int

# CorporationsCorporationIdMembersTitlesGet: array of dict
CorporationsCorporationIdMembersTitlesGet = list[dict]

# CorporationsCorporationIdMembertrackingGet: array of dict
CorporationsCorporationIdMembertrackingGet = list[dict]

# CorporationsCorporationIdOrdersGet: array of dict
CorporationsCorporationIdOrdersGet = list[dict]

# CorporationsCorporationIdOrdersHistoryGet: array of dict
CorporationsCorporationIdOrdersHistoryGet = list[dict]

# CorporationsCorporationIdRolesGet: array of dict
CorporationsCorporationIdRolesGet = list[dict]

# CorporationsCorporationIdRolesHistoryGet: array of dict
CorporationsCorporationIdRolesHistoryGet = list[dict]

# CorporationsCorporationIdShareholdersGet: array of dict
CorporationsCorporationIdShareholdersGet = list[dict]

# CorporationsCorporationIdStandingsGet: array of dict
CorporationsCorporationIdStandingsGet = list[dict]

# CorporationsCorporationIdStarbasesGet: array of dict
CorporationsCorporationIdStarbasesGet = list[dict]

class CorporationsCorporationIdStarbasesStarbaseIdGet(TypedDict, total=False):
    allow_alliance_members: bool  # required=True
    allow_corporation_members: bool  # required=True
    anchor: str  # required=True
    attack_if_at_war: bool  # required=True
    attack_if_other_security_status_dropping: bool  # required=True
    attack_security_status_threshold: float  # required=False
    attack_standing_threshold: float  # required=False
    fuel_bay_take: str  # required=True
    fuel_bay_view: str  # required=True
    fuels: list[dict]  # required=False
    offline: str  # required=True
    online: str  # required=True
    unanchor: str  # required=True
    use_alliance_standings: bool  # required=True

# CorporationsCorporationIdStructuresGet: array of dict
CorporationsCorporationIdStructuresGet = list[dict]

# CorporationsCorporationIdTitlesGet: array of dict
CorporationsCorporationIdTitlesGet = list[dict]

# CorporationsCorporationIdWalletsDivisionJournalGet: array of dict
CorporationsCorporationIdWalletsDivisionJournalGet = list[dict]

# CorporationsCorporationIdWalletsDivisionTransactionsGet: array of dict
CorporationsCorporationIdWalletsDivisionTransactionsGet = list[dict]

# CorporationsCorporationIdWalletsGet: array of dict
CorporationsCorporationIdWalletsGet = list[dict]

class CorporationsDetail(TypedDict, total=False):
    alliance_id: Any  # required=False
    ceo_id: Any  # required=True
    creator_id: Any  # required=True
    date_founded: str  # required=False
    description: str  # required=False
    faction_id: Any  # required=False
    home_station_id: Any  # required=False
    member_count: int  # required=True
    name: str  # required=True
    shares: int  # required=False
    tax_rate: float  # required=True
    ticker: str  # required=True
    url: str  # required=False
    war_eligible: bool  # required=False

class CorporationsFreelanceJobsListing(TypedDict, total=False):
    cursor: Any  # required=False
    freelance_jobs: list[Any]  # required=True

class CorporationsFreelanceJobsParticipants(TypedDict, total=False):
    cursor: Any  # required=False
    participants: list[Any]  # required=True

class CorporationsFreelanceJobsParticipantsParticipant(TypedDict, total=False):
    contributed: int  # required=True
    id: Any  # required=True
    name: str  # required=True
    state: str  # required=True

# CorporationsNpccorpsGet: array of int
CorporationsNpccorpsGet = list[int]

class CorporationsProjectsContribution(TypedDict, total=False):
    contributed: int  # required=True
    last_modified: str  # required=False

class CorporationsProjectsContributors(TypedDict, total=False):
    contributors: list[Any]  # required=True
    cursor: Any  # required=False

class CorporationsProjectsContributorsContributor(TypedDict, total=False):
    contributed: int  # required=True
    id: Any  # required=True
    name: str  # required=True

class CorporationsProjectsDetail(TypedDict, total=False):
    configuration: Any  # required=True
    contribution: Any  # required=False
    creator: Any  # required=True
    details: Any  # required=True
    id: Any  # required=True
    last_modified: str  # required=True
    name: str  # required=True
    progress: Any  # required=True
    reward: Any  # required=False
    state: str  # required=True

class CorporationsProjectsDetailConfigurationcapturefwcomplex(TypedDict, total=False):
    archetypes: list[Any]  # required=False
    factions: list[Any]  # required=False
    locations: list[Any]  # required=False

class CorporationsProjectsDetailConfigurationdamageship(TypedDict, total=False):
    identities: list[Any]  # required=False
    locations: list[Any]  # required=False
    ships: list[Any]  # required=False

class CorporationsProjectsDetailConfigurationdefendfwcomplex(TypedDict, total=False):
    archetypes: list[Any]  # required=False
    factions: list[Any]  # required=False
    locations: list[Any]  # required=False

class CorporationsProjectsDetailConfigurationdeliveritem(TypedDict, total=False):
    docking_locations: list[Any]  # required=False
    items: list[Any]  # required=False
    office_id: Any  # required=False

class CorporationsProjectsDetailConfigurationdestroynpc(TypedDict, total=False):
    locations: list[Any]  # required=False

class CorporationsProjectsDetailConfigurationdestroyship(TypedDict, total=False):
    identities: list[Any]  # required=False
    locations: list[Any]  # required=False
    ships: list[Any]  # required=False

class CorporationsProjectsDetailConfigurationearnloyaltypoints(TypedDict, total=False):
    corporations: list[Any]  # required=False

class CorporationsProjectsDetailConfigurationlostship(TypedDict, total=False):
    identities: list[Any]  # required=False
    locations: list[Any]  # required=False
    ships: list[Any]  # required=False

# CorporationsProjectsDetailConfigurationmanual: object
CorporationsProjectsDetailConfigurationmanual = dict

class CorporationsProjectsDetailConfigurationmanufactureitem(TypedDict, total=False):
    docking_locations: list[Any]  # required=False
    items: list[Any]  # required=False
    owner: str  # required=True

class CorporationsProjectsDetailConfigurationmatcherarchetype(TypedDict, total=False):
    archetype_id: Any  # required=False

class CorporationsProjectsDetailConfigurationmatchercorporation(TypedDict, total=False):
    corporation_id: Any  # required=False

class CorporationsProjectsDetailConfigurationmatcherfaction(TypedDict, total=False):
    faction_id: Any  # required=False

class CorporationsProjectsDetailConfigurationmatchersignature(TypedDict, total=False):
    signature_type_id: Any  # required=False

class CorporationsProjectsDetailConfigurationminematerial(TypedDict, total=False):
    locations: list[Any]  # required=False
    materials: list[Any]  # required=False

class CorporationsProjectsDetailConfigurationremoteboostshield(TypedDict, total=False):
    identities: list[Any]  # required=False
    locations: list[Any]  # required=False
    ships: list[Any]  # required=False

class CorporationsProjectsDetailConfigurationremoterepairarmor(TypedDict, total=False):
    identities: list[Any]  # required=False
    locations: list[Any]  # required=False
    ships: list[Any]  # required=False

class CorporationsProjectsDetailConfigurationsalvagewreck(TypedDict, total=False):
    locations: list[Any]  # required=False

class CorporationsProjectsDetailConfigurationscansignature(TypedDict, total=False):
    locations: list[Any]  # required=False
    signatures: list[Any]  # required=False

class CorporationsProjectsDetailConfigurationshipinsurance(TypedDict, total=False):
    conflict_type: str  # required=True
    identities: list[Any]  # required=False
    locations: list[Any]  # required=False
    reimburse_implants: bool  # required=True
    ships: list[Any]  # required=False

class CorporationsProjectsDetailConfigurationunknown(TypedDict, total=False):
    data: Any  # required=True
    type: str  # required=True

class CorporationsProjectsDetailContribution(TypedDict, total=False):
    participation_limit: int  # required=False
    reward_per_contribution: float  # required=False
    submission_limit: int  # required=False
    submission_multiplier: float  # required=False

class CorporationsProjectsDetailCreator(TypedDict, total=False):
    id: Any  # required=True
    name: str  # required=True

class CorporationsProjectsDetailDetails(TypedDict, total=False):
    career: str  # required=True
    created: str  # required=True
    description: str  # required=True
    expires: str  # required=False
    finished: str  # required=False

class CorporationsProjectsDetailProgress(TypedDict, total=False):
    current: int  # required=True
    desired: int  # required=True

class CorporationsProjectsDetailProject(TypedDict, total=False):
    id: Any  # required=True
    last_modified: str  # required=True
    name: str  # required=True
    progress: Any  # required=True
    reward: Any  # required=False
    state: str  # required=True

class CorporationsProjectsDetailReward(TypedDict, total=False):
    initial: float  # required=True
    remaining: float  # required=True

class CorporationsProjectsListing(TypedDict, total=False):
    cursor: Any  # required=False
    projects: list[Any]  # required=True

class Cursor(TypedDict, total=False):
    after: str  # required=False
    before: str  # required=False

class DogmaAttributesAttributeIdGet(TypedDict, total=False):
    attribute_id: int  # required=True
    default_value: float  # required=False
    description: str  # required=False
    display_name: str  # required=False
    high_is_good: bool  # required=False
    icon_id: int  # required=False
    name: str  # required=False
    published: bool  # required=False
    stackable: bool  # required=False
    unit_id: int  # required=False

# DogmaAttributesGet: array of int
DogmaAttributesGet = list[int]

class DogmaDynamicItemsTypeIdItemIdGet(TypedDict, total=False):
    created_by: int  # required=True
    dogma_attributes: list[dict]  # required=True
    dogma_effects: list[dict]  # required=True
    mutator_type_id: int  # required=True
    source_type_id: int  # required=True

class DogmaEffectsEffectIdGet(TypedDict, total=False):
    description: str  # required=False
    disallow_auto_repeat: bool  # required=False
    discharge_attribute_id: int  # required=False
    display_name: str  # required=False
    duration_attribute_id: int  # required=False
    effect_category: int  # required=False
    effect_id: int  # required=True
    electronic_chance: bool  # required=False
    falloff_attribute_id: int  # required=False
    icon_id: int  # required=False
    is_assistance: bool  # required=False
    is_offensive: bool  # required=False
    is_warp_safe: bool  # required=False
    modifiers: list[dict]  # required=False
    name: str  # required=False
    post_expression: int  # required=False
    pre_expression: int  # required=False
    published: bool  # required=False
    range_attribute_id: int  # required=False
    range_chance: bool  # required=False
    tracking_speed_attribute_id: int  # required=False

# DogmaEffectsGet: array of int
DogmaEffectsGet = list[int]

# DungeonID: integer
DungeonID = int

class Error(TypedDict, total=False):
    details: list[Any]  # required=False
    error: str  # required=True
    status: int  # required=True

class ErrorDetail(TypedDict, total=False):
    location: str  # required=False
    message: str  # required=False
    value: Any  # required=False

# FactionID: integer
FactionID = int

class FleetsFleetIdGet(TypedDict, total=False):
    is_free_move: bool  # required=True
    is_registered: bool  # required=True
    is_voice_enabled: bool  # required=True
    motd: str  # required=True

# FleetsFleetIdMembersGet: array of dict
FleetsFleetIdMembersGet = list[dict]

# FleetsFleetIdWingsGet: array of dict
FleetsFleetIdWingsGet = list[dict]

class FleetsFleetIdWingsPost(TypedDict, total=False):
    """201 created object"""
    wing_id: int  # required=True

class FleetsFleetIdWingsWingIdSquadsPost(TypedDict, total=False):
    """201 created object"""
    squad_id: int  # required=True

class FreelanceJobsDetail(TypedDict, total=False):
    access_and_visibility: Any  # required=True
    configuration: Any  # required=True
    contribution: Any  # required=False
    details: Any  # required=True
    id: Any  # required=True
    last_modified: str  # required=True
    name: str  # required=True
    progress: Any  # required=True
    reward: Any  # required=False
    state: str  # required=True

class FreelanceJobsDetailAccessandvisibility(TypedDict, total=False):
    acl_protected: bool  # required=True
    broadcast_locations: list[Any]  # required=False
    restrictions: Any  # required=False

class FreelanceJobsDetailBroadcastlocations(TypedDict, total=False):
    id: Any  # required=True
    name: str  # required=True

class FreelanceJobsDetailConfiguration(TypedDict, total=False):
    method: str  # required=True
    parameters: dict  # required=True
    version: int  # required=True

class FreelanceJobsDetailContribution(TypedDict, total=False):
    contribution_per_participant_limit: int  # required=False
    max_committed_participants: int  # required=True
    reward_per_contribution: float  # required=False
    submission_limit: int  # required=False
    submission_multiplier: float  # required=False

class FreelanceJobsDetailCreator(TypedDict, total=False):
    character: Any  # required=True
    corporation: Any  # required=True

class FreelanceJobsDetailCreatorcharacter(TypedDict, total=False):
    id: Any  # required=True
    name: str  # required=True

class FreelanceJobsDetailCreatorcorporation(TypedDict, total=False):
    id: Any  # required=True
    name: str  # required=True

class FreelanceJobsDetailDetails(TypedDict, total=False):
    career: str  # required=True
    created: str  # required=True
    creator: Any  # required=True
    description: str  # required=True
    expires: str  # required=False
    finished: str  # required=False

class FreelanceJobsDetailFreelancejob(TypedDict, total=False):
    id: Any  # required=True
    last_modified: str  # required=True
    name: str  # required=True
    progress: Any  # required=True
    reward: Any  # required=False
    state: str  # required=True

class FreelanceJobsDetailParameterboolean(TypedDict, total=False):
    value: bool  # required=True

class FreelanceJobsDetailParametercorporationitemdelivery(TypedDict, total=False):
    corporation_office_location: Any  # required=True
    item_type: Any  # required=True

class FreelanceJobsDetailParametermatcher(TypedDict, total=False):
    values: list[Any]  # required=True

class FreelanceJobsDetailParametermatchervalue(TypedDict, total=False):
    value_type: str  # required=True
    values: list[str]  # required=True

class FreelanceJobsDetailParameteroptions(TypedDict, total=False):
    selected: list[str]  # required=True

class FreelanceJobsDetailProgress(TypedDict, total=False):
    current: int  # required=True
    desired: int  # required=True

class FreelanceJobsDetailRestrictions(TypedDict, total=False):
    maximum_age: int  # required=False
    minimum_age: int  # required=False

class FreelanceJobsDetailReward(TypedDict, total=False):
    initial: float  # required=True
    remaining: float  # required=True

class FreelanceJobsListing(TypedDict, total=False):
    cursor: Any  # required=False
    freelance_jobs: list[Any]  # required=True

class FwLeaderboardsCharactersGet(TypedDict, total=False):
    kills: dict  # required=True
    victory_points: dict  # required=True

class FwLeaderboardsCorporationsGet(TypedDict, total=False):
    kills: dict  # required=True
    victory_points: dict  # required=True

class FwLeaderboardsGet(TypedDict, total=False):
    kills: dict  # required=True
    victory_points: dict  # required=True

# FwStatsGet: array of dict
FwStatsGet = list[dict]

# FwSystemsGet: array of dict
FwSystemsGet = list[dict]

# FwWarsGet: array of dict
FwWarsGet = list[dict]

# GroupID: integer
GroupID = int

# IncursionsGet: array of dict
IncursionsGet = list[dict]

# IndustryFacilitiesGet: array of dict
IndustryFacilitiesGet = list[dict]

# IndustrySystemsGet: array of dict
IndustrySystemsGet = list[dict]

# InsurancePricesGet: array of dict
InsurancePricesGet = list[dict]

# ItemID: integer
ItemID = int

class KillmailsKillmailIdKillmailHashGet(TypedDict, total=False):
    attackers: list[dict]  # required=True
    killmail_id: int  # required=True
    killmail_time: str  # required=True
    moon_id: int  # required=False
    solar_system_id: int  # required=True
    victim: dict  # required=True
    war_id: int  # required=False

# LoyaltyStoresCorporationIdOffersGet: array of dict
LoyaltyStoresCorporationIdOffersGet = list[dict]

# MarketsGroupsGet: array of int
MarketsGroupsGet = list[int]

class MarketsGroupsMarketGroupIdGet(TypedDict, total=False):
    description: str  # required=True
    market_group_id: int  # required=True
    name: str  # required=True
    parent_group_id: int  # required=False
    types: list[int]  # required=True

# MarketsPricesGet: array of dict
MarketsPricesGet = list[dict]

# MarketsRegionIdHistoryGet: array of dict
MarketsRegionIdHistoryGet = list[dict]

# MarketsRegionIdOrdersGet: array of dict
MarketsRegionIdOrdersGet = list[dict]

# MarketsRegionIdTypesGet: array of int
MarketsRegionIdTypesGet = list[int]

# MarketsStructuresStructureIdGet: array of dict
MarketsStructuresStructureIdGet = list[dict]

class MetaChangelog(TypedDict, total=False):
    changelog: dict  # required=True

class MetaChangelogEntry(TypedDict, total=False):
    compatibility_date: Any  # required=True
    description: str  # required=True
    method: str  # required=True
    path: str  # required=True
    type: str  # required=True

class MetaCompatibilityDates(TypedDict, total=False):
    compatibility_dates: list[Any]  # required=True

class MetaStatus(TypedDict, total=False):
    routes: list[Any]  # required=True

class MetaStatusRoutestatus(TypedDict, total=False):
    method: str  # required=True
    path: str  # required=True
    status: str  # required=True

# PlanetID: integer
PlanetID = int

# RaceID: integer
RaceID = int

# RegionID: integer
RegionID = int

class Route(TypedDict, total=False):
    route: list[Any]  # required=True

class RouteConnection(TypedDict, total=False):
    from_: Any  # required=True
    to: Any  # required=True

class RouteRequestBody(TypedDict, total=False):
    avoid_systems: list[Any]  # required=False
    connections: list[Any]  # required=False
    preference: str  # required=False
    security_penalty: int  # required=False

# ShipTreeGroupID: integer
ShipTreeGroupID = int

# SolarSystemID: integer
SolarSystemID = int

# SovereigntyCampaignsGet: array of dict
SovereigntyCampaignsGet = list[dict]

# SovereigntyMapGet: array of dict
SovereigntyMapGet = list[dict]

# SovereigntyStructuresGet: array of dict
SovereigntyStructuresGet = list[dict]

# StationID: integer
StationID = int

class StatusGet(TypedDict, total=False):
    players: int  # required=True
    server_version: str  # required=True
    start_time: str  # required=True
    vip: bool  # required=False

# TypeID: integer
TypeID = int

# UUID: string
UUID = str

# UniverseAncestriesGet: array of dict
UniverseAncestriesGet = list[dict]

class UniverseAsteroidBeltsAsteroidBeltIdGet(TypedDict, total=False):
    name: str  # required=True
    position: dict  # required=True
    system_id: int  # required=True

# UniverseBloodlinesGet: array of dict
UniverseBloodlinesGet = list[dict]

class UniverseCategoriesCategoryIdGet(TypedDict, total=False):
    category_id: int  # required=True
    groups: list[int]  # required=True
    name: str  # required=True
    published: bool  # required=True

# UniverseCategoriesGet: array of int
UniverseCategoriesGet = list[int]

class UniverseConstellationsConstellationIdGet(TypedDict, total=False):
    constellation_id: int  # required=True
    name: str  # required=True
    position: dict  # required=True
    region_id: int  # required=True
    systems: list[int]  # required=True

# UniverseConstellationsGet: array of int
UniverseConstellationsGet = list[int]

# UniverseFactionsGet: array of dict
UniverseFactionsGet = list[dict]

# UniverseGraphicsGet: array of int
UniverseGraphicsGet = list[int]

class UniverseGraphicsGraphicIdGet(TypedDict, total=False):
    collision_file: str  # required=False
    graphic_file: str  # required=False
    graphic_id: int  # required=True
    icon_folder: str  # required=False
    sof_dna: str  # required=False
    sof_fation_name: str  # required=False
    sof_hull_name: str  # required=False
    sof_race_name: str  # required=False

# UniverseGroupsGet: array of int
UniverseGroupsGet = list[int]

class UniverseGroupsGroupIdGet(TypedDict, total=False):
    category_id: int  # required=True
    group_id: int  # required=True
    name: str  # required=True
    published: bool  # required=True
    types: list[int]  # required=True

class UniverseIdsPost(TypedDict, total=False):
    agents: list[dict]  # required=False
    alliances: list[dict]  # required=False
    characters: list[dict]  # required=False
    constellations: list[dict]  # required=False
    corporations: list[dict]  # required=False
    factions: list[dict]  # required=False
    inventory_types: list[dict]  # required=False
    regions: list[dict]  # required=False
    stations: list[dict]  # required=False
    systems: list[dict]  # required=False

class UniverseMoonsMoonIdGet(TypedDict, total=False):
    moon_id: int  # required=True
    name: str  # required=True
    position: dict  # required=True
    system_id: int  # required=True

# UniverseNamesPost: array of dict
UniverseNamesPost = list[dict]

class UniversePlanetsPlanetIdGet(TypedDict, total=False):
    name: str  # required=True
    planet_id: int  # required=True
    position: dict  # required=True
    system_id: int  # required=True
    type_id: int  # required=True

# UniverseRacesGet: array of dict
UniverseRacesGet = list[dict]

# UniverseRegionsGet: array of int
UniverseRegionsGet = list[int]

class UniverseRegionsRegionIdGet(TypedDict, total=False):
    constellations: list[int]  # required=True
    description: str  # required=False
    name: str  # required=True
    region_id: int  # required=True

class UniverseSchematicsSchematicIdGet(TypedDict, total=False):
    cycle_time: int  # required=True
    schematic_name: str  # required=True

class UniverseStargatesStargateIdGet(TypedDict, total=False):
    destination: dict  # required=True
    name: str  # required=True
    position: dict  # required=True
    stargate_id: int  # required=True
    system_id: int  # required=True
    type_id: int  # required=True

class UniverseStarsStarIdGet(TypedDict, total=False):
    age: int  # required=True
    luminosity: float  # required=True
    name: str  # required=True
    radius: int  # required=True
    solar_system_id: int  # required=True
    spectral_class: str  # required=True
    temperature: int  # required=True
    type_id: int  # required=True

class UniverseStationsStationIdGet(TypedDict, total=False):
    max_dockable_ship_volume: float  # required=True
    name: str  # required=True
    office_rental_cost: float  # required=True
    owner: int  # required=False
    position: dict  # required=True
    race_id: int  # required=False
    reprocessing_efficiency: float  # required=True
    reprocessing_stations_take: float  # required=True
    services: list[str]  # required=True
    station_id: int  # required=True
    system_id: int  # required=True
    type_id: int  # required=True

# UniverseStructuresGet: array of int
UniverseStructuresGet = list[int]

class UniverseStructuresStructureIdGet(TypedDict, total=False):
    name: str  # required=True
    owner_id: int  # required=True
    position: dict  # required=False
    solar_system_id: int  # required=True
    type_id: int  # required=False

# UniverseSystemJumpsGet: array of dict
UniverseSystemJumpsGet = list[dict]

# UniverseSystemKillsGet: array of dict
UniverseSystemKillsGet = list[dict]

# UniverseSystemsGet: array of int
UniverseSystemsGet = list[int]

class UniverseSystemsSystemIdGet(TypedDict, total=False):
    constellation_id: int  # required=True
    name: str  # required=True
    planets: list[dict]  # required=False
    position: dict  # required=True
    security_class: str  # required=False
    security_status: float  # required=True
    star_id: int  # required=False
    stargates: list[int]  # required=False
    stations: list[int]  # required=False
    system_id: int  # required=True

# UniverseTypesGet: array of int
UniverseTypesGet = list[int]

class UniverseTypesTypeIdGet(TypedDict, total=False):
    capacity: float  # required=False
    description: str  # required=True
    dogma_attributes: list[dict]  # required=False
    dogma_effects: list[dict]  # required=False
    graphic_id: int  # required=False
    group_id: int  # required=True
    icon_id: int  # required=False
    market_group_id: int  # required=False
    mass: float  # required=False
    name: str  # required=True
    packaged_volume: float  # required=False
    portion_size: int  # required=False
    published: bool  # required=True
    radius: float  # required=False
    type_id: int  # required=True
    volume: float  # required=False

# WarsGet: array of int
WarsGet = list[int]

class WarsWarIdGet(TypedDict, total=False):
    aggressor: dict  # required=True
    allies: list[dict]  # required=False
    declared: str  # required=True
    defender: dict  # required=True
    finished: str  # required=False
    id: int  # required=True
    mutual: bool  # required=True
    open_for_allies: bool  # required=True
    retracted: str  # required=False
    started: str  # required=False

# WarsWarIdKillmailsGet: array of dict
WarsWarIdKillmailsGet = list[dict]

# -- Schema name constant map -------------------------------------------------
SCHEMA_NAMES: list[str] = ['AccessListID', 'AllianceDetail', 'AllianceID', 'AlliancesAllianceIdContactsGet', 'AlliancesAllianceIdContactsLabelsGet', 'AlliancesAllianceIdCorporationsGet', 'AlliancesAllianceIdIconsGet', 'AlliancesGet', 'ArchetypeID', 'AttributeID', 'BloodlineID', 'CharacterID', 'CharactersAffiliationPost', 'CharactersCharacterIdAgentsResearchGet', 'CharactersCharacterIdAssetsGet', 'CharactersCharacterIdAssetsLocationsPost', 'CharactersCharacterIdAssetsNamesPost', 'CharactersCharacterIdAttributesGet', 'CharactersCharacterIdBlueprintsGet', 'CharactersCharacterIdCalendarEventIdAttendeesGet', 'CharactersCharacterIdCalendarEventIdGet', 'CharactersCharacterIdCalendarGet', 'CharactersCharacterIdClonesGet', 'CharactersCharacterIdContactsGet', 'CharactersCharacterIdContactsLabelsGet', 'CharactersCharacterIdContactsPost', 'CharactersCharacterIdContractsContractIdBidsGet', 'CharactersCharacterIdContractsContractIdItemsGet', 'CharactersCharacterIdContractsGet', 'CharactersCharacterIdCorporationhistoryGet', 'CharactersCharacterIdCspaPost', 'CharactersCharacterIdFatigueGet', 'CharactersCharacterIdFittingsGet', 'CharactersCharacterIdFittingsPost', 'CharactersCharacterIdFleetGet', 'CharactersCharacterIdFwStatsGet', 'CharactersCharacterIdImplantsGet', 'CharactersCharacterIdIndustryJobsGet', 'CharactersCharacterIdKillmailsRecentGet', 'CharactersCharacterIdLocationGet', 'CharactersCharacterIdLoyaltyPointsGet', 'CharactersCharacterIdMailGet', 'CharactersCharacterIdMailLabelsGet', 'CharactersCharacterIdMailLabelsPost', 'CharactersCharacterIdMailListsGet', 'CharactersCharacterIdMailMailIdGet', 'CharactersCharacterIdMailPost', 'CharactersCharacterIdMedalsGet', 'CharactersCharacterIdMiningGet', 'CharactersCharacterIdNotificationsContactsGet', 'CharactersCharacterIdNotificationsGet', 'CharactersCharacterIdOnlineGet', 'CharactersCharacterIdOrdersGet', 'CharactersCharacterIdOrdersHistoryGet', 'CharactersCharacterIdPlanetsGet', 'CharactersCharacterIdPlanetsPlanetIdGet', 'CharactersCharacterIdPortraitGet', 'CharactersCharacterIdRolesGet', 'CharactersCharacterIdSearchGet', 'CharactersCharacterIdShipGet', 'CharactersCharacterIdStandingsGet', 'CharactersCharacterIdTitlesGet', 'CharactersCharacterIdWalletGet', 'CharactersCharacterIdWalletJournalGet', 'CharactersCharacterIdWalletTransactionsGet', 'CharactersDetail', 'CharactersFreelanceJobsListing', 'CharactersFreelanceJobsParticipation', 'CharactersSkillqueueSkill', 'CharactersSkills', 'CharactersSkillsSkill', 'CompatibilityDate', 'ConstellationID', 'ContractsPublicBidsContractIdGet', 'ContractsPublicItemsContractIdGet', 'ContractsPublicRegionIdGet', 'CorporationCorporationIdMiningExtractionsGet', 'CorporationCorporationIdMiningObserversGet', 'CorporationCorporationIdMiningObserversObserverIdGet', 'CorporationID', 'CorporationsCorporationIdAlliancehistoryGet', 'CorporationsCorporationIdAssetsGet', 'CorporationsCorporationIdAssetsLocationsPost', 'CorporationsCorporationIdAssetsNamesPost', 'CorporationsCorporationIdBlueprintsGet', 'CorporationsCorporationIdContactsGet', 'CorporationsCorporationIdContactsLabelsGet', 'CorporationsCorporationIdContainersLogsGet', 'CorporationsCorporationIdContractsContractIdBidsGet', 'CorporationsCorporationIdContractsContractIdItemsGet', 'CorporationsCorporationIdContractsGet', 'CorporationsCorporationIdCustomsOfficesGet', 'CorporationsCorporationIdDivisionsGet', 'CorporationsCorporationIdFacilitiesGet', 'CorporationsCorporationIdFwStatsGet', 'CorporationsCorporationIdIconsGet', 'CorporationsCorporationIdIndustryJobsGet', 'CorporationsCorporationIdKillmailsRecentGet', 'CorporationsCorporationIdMedalsGet', 'CorporationsCorporationIdMedalsIssuedGet', 'CorporationsCorporationIdMembersGet', 'CorporationsCorporationIdMembersLimitGet', 'CorporationsCorporationIdMembersTitlesGet', 'CorporationsCorporationIdMembertrackingGet', 'CorporationsCorporationIdOrdersGet', 'CorporationsCorporationIdOrdersHistoryGet', 'CorporationsCorporationIdRolesGet', 'CorporationsCorporationIdRolesHistoryGet', 'CorporationsCorporationIdShareholdersGet', 'CorporationsCorporationIdStandingsGet', 'CorporationsCorporationIdStarbasesGet', 'CorporationsCorporationIdStarbasesStarbaseIdGet', 'CorporationsCorporationIdStructuresGet', 'CorporationsCorporationIdTitlesGet', 'CorporationsCorporationIdWalletsDivisionJournalGet', 'CorporationsCorporationIdWalletsDivisionTransactionsGet', 'CorporationsCorporationIdWalletsGet', 'CorporationsDetail', 'CorporationsFreelanceJobsListing', 'CorporationsFreelanceJobsParticipants', 'CorporationsFreelanceJobsParticipantsParticipant', 'CorporationsNpccorpsGet', 'CorporationsProjectsContribution', 'CorporationsProjectsContributors', 'CorporationsProjectsContributorsContributor', 'CorporationsProjectsDetail', 'CorporationsProjectsDetailConfigurationcapturefwcomplex', 'CorporationsProjectsDetailConfigurationdamageship', 'CorporationsProjectsDetailConfigurationdefendfwcomplex', 'CorporationsProjectsDetailConfigurationdeliveritem', 'CorporationsProjectsDetailConfigurationdestroynpc', 'CorporationsProjectsDetailConfigurationdestroyship', 'CorporationsProjectsDetailConfigurationearnloyaltypoints', 'CorporationsProjectsDetailConfigurationlostship', 'CorporationsProjectsDetailConfigurationmanual', 'CorporationsProjectsDetailConfigurationmanufactureitem', 'CorporationsProjectsDetailConfigurationmatcherarchetype', 'CorporationsProjectsDetailConfigurationmatchercorporation', 'CorporationsProjectsDetailConfigurationmatcherfaction', 'CorporationsProjectsDetailConfigurationmatchersignature', 'CorporationsProjectsDetailConfigurationminematerial', 'CorporationsProjectsDetailConfigurationremoteboostshield', 'CorporationsProjectsDetailConfigurationremoterepairarmor', 'CorporationsProjectsDetailConfigurationsalvagewreck', 'CorporationsProjectsDetailConfigurationscansignature', 'CorporationsProjectsDetailConfigurationshipinsurance', 'CorporationsProjectsDetailConfigurationunknown', 'CorporationsProjectsDetailContribution', 'CorporationsProjectsDetailCreator', 'CorporationsProjectsDetailDetails', 'CorporationsProjectsDetailProgress', 'CorporationsProjectsDetailProject', 'CorporationsProjectsDetailReward', 'CorporationsProjectsListing', 'Cursor', 'DogmaAttributesAttributeIdGet', 'DogmaAttributesGet', 'DogmaDynamicItemsTypeIdItemIdGet', 'DogmaEffectsEffectIdGet', 'DogmaEffectsGet', 'DungeonID', 'Error', 'ErrorDetail', 'FactionID', 'FleetsFleetIdGet', 'FleetsFleetIdMembersGet', 'FleetsFleetIdWingsGet', 'FleetsFleetIdWingsPost', 'FleetsFleetIdWingsWingIdSquadsPost', 'FreelanceJobsDetail', 'FreelanceJobsDetailAccessandvisibility', 'FreelanceJobsDetailBroadcastlocations', 'FreelanceJobsDetailConfiguration', 'FreelanceJobsDetailContribution', 'FreelanceJobsDetailCreator', 'FreelanceJobsDetailCreatorcharacter', 'FreelanceJobsDetailCreatorcorporation', 'FreelanceJobsDetailDetails', 'FreelanceJobsDetailFreelancejob', 'FreelanceJobsDetailParameterboolean', 'FreelanceJobsDetailParametercorporationitemdelivery', 'FreelanceJobsDetailParametermatcher', 'FreelanceJobsDetailParametermatchervalue', 'FreelanceJobsDetailParameteroptions', 'FreelanceJobsDetailProgress', 'FreelanceJobsDetailRestrictions', 'FreelanceJobsDetailReward', 'FreelanceJobsListing', 'FwLeaderboardsCharactersGet', 'FwLeaderboardsCorporationsGet', 'FwLeaderboardsGet', 'FwStatsGet', 'FwSystemsGet', 'FwWarsGet', 'GroupID', 'IncursionsGet', 'IndustryFacilitiesGet', 'IndustrySystemsGet', 'InsurancePricesGet', 'ItemID', 'KillmailsKillmailIdKillmailHashGet', 'LoyaltyStoresCorporationIdOffersGet', 'MarketsGroupsGet', 'MarketsGroupsMarketGroupIdGet', 'MarketsPricesGet', 'MarketsRegionIdHistoryGet', 'MarketsRegionIdOrdersGet', 'MarketsRegionIdTypesGet', 'MarketsStructuresStructureIdGet', 'MetaChangelog', 'MetaChangelogEntry', 'MetaCompatibilityDates', 'MetaStatus', 'MetaStatusRoutestatus', 'PlanetID', 'RaceID', 'RegionID', 'Route', 'RouteConnection', 'RouteRequestBody', 'ShipTreeGroupID', 'SolarSystemID', 'SovereigntyCampaignsGet', 'SovereigntyMapGet', 'SovereigntyStructuresGet', 'StationID', 'StatusGet', 'TypeID', 'UUID', 'UniverseAncestriesGet', 'UniverseAsteroidBeltsAsteroidBeltIdGet', 'UniverseBloodlinesGet', 'UniverseCategoriesCategoryIdGet', 'UniverseCategoriesGet', 'UniverseConstellationsConstellationIdGet', 'UniverseConstellationsGet', 'UniverseFactionsGet', 'UniverseGraphicsGet', 'UniverseGraphicsGraphicIdGet', 'UniverseGroupsGet', 'UniverseGroupsGroupIdGet', 'UniverseIdsPost', 'UniverseMoonsMoonIdGet', 'UniverseNamesPost', 'UniversePlanetsPlanetIdGet', 'UniverseRacesGet', 'UniverseRegionsGet', 'UniverseRegionsRegionIdGet', 'UniverseSchematicsSchematicIdGet', 'UniverseStargatesStargateIdGet', 'UniverseStarsStarIdGet', 'UniverseStationsStationIdGet', 'UniverseStructuresGet', 'UniverseStructuresStructureIdGet', 'UniverseSystemJumpsGet', 'UniverseSystemKillsGet', 'UniverseSystemsGet', 'UniverseSystemsSystemIdGet', 'UniverseTypesGet', 'UniverseTypesTypeIdGet', 'WarsGet', 'WarsWarIdGet', 'WarsWarIdKillmailsGet']
