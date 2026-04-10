# Collector Pipeline — Full Implementation Plan

**Created:** 2026-04-09  
**Branch:** v0.2.16  
**ESI Compatibility Date:** `2025-12-16` (208 routes, 66 scopes)

---

## 1. Executive Summary

This document is the authoritative implementation plan for building every viable ESI → database
data collector in this framework.

**Current coverage:** 5 domains (market orders, structure market orders, market history,
structure discovery, character core data).

**Target coverage:** ~45 collector domains spanning personal, corporation, alliance, and public
data using a **4-tier all-DuckDB architecture**, writing to approximately **85 new tables**,
registered across **~30 new scheduler jobs** (21 collector + 9 analysis enrichment).

### Scope Boundaries

| In Scope | Out of Scope |
|----------|-------------|
| All ESI GET endpoints that return storable data | Write/action endpoints (POST/PUT/DELETE) |
| Personal character data (DuckDB per-owner, `character_id` keyed) | Fleet real-time state |
| Corporation data (DuckDB per-corp) | UI action endpoints |
| Alliance data (DuckDB per-alliance) | Search utility endpoints |
| Public / FW / sovereignty data (shared DuckDB) | NPC corps (already in SDE: `npcCorporations.jsonl`) |
| Cross-entity analysis enrichment (`analysis/` modules) | |
| market_history scheduled batching | |

---

## 2. Current State Audit

### 2.1 Live Scheduler Jobs (Working)

| job_id | Entry Point | Interval | Tables Owned |
|--------|-------------|----------|--------------|
| `market_refresh` | `collectors.public_data.market.fetch_region_orders` *(was `collectors.market.regions` — migrated Phase 5)* | 1 h | `market_orders`, `market_region_cooldowns` |
| `structure_market_refresh` | `collectors.public_data.market.fetch_structure_orders` *(was `collectors.market.structures` — migrated Phase 5)* | 1 h | `market_structures` |
| `structure_discovery` | `collectors.public_data.structures.discover_structures` *(was `collectors.structures.discover` — migrated Phase 5)* | 24 h | `structures` |
| `character_refresh` | `core.tasks.jobs._refresh_all_characters` | 24 h | `character_skills`, `character_wallet`, `character_assets` (SQLite — **needs DuckDB migration**) |
| `esi_spec_refresh` | `core.system.bootstrap.ensure_esi_ready` | 24 h | `esi_routes/schemas/scopes` — **disabled by default** |

### 2.2 Coded but Unscheduled (WIP)

`collectors/character/collectors.py` (~1075 lines) contains 15 complete collectors keyed to a
`SCOPE_COLLECTORS` registry but **none have `jobs.py` entries**.

| Function | Required Scope | Table |
|----------|---------------|-------|
| `populate_mail` | `esi-mail.read_mail.v1` | `character_mail` |
| `populate_contracts` | `esi-contracts.read_character_contracts.v1` | `character_contracts` |
| `populate_calendar` | `esi-calendar.read_calendar_events.v1` | `character_calendar` |
| `populate_contacts` | `esi-characters.read_contacts.v1` | `character_contacts` |
| `populate_notifications` | `esi-characters.read_notifications.v1` | `character_notifications` |
| `populate_industry` | `esi-industry.read_character_jobs.v1` | `character_industry` |
| `populate_orders` | `esi-markets.read_character_orders.v1` | `character_orders` |
| `populate_blueprints` | `esi-characters.read_blueprints.v1` | `character_blueprints` |
| `populate_planets` | `esi-planets.manage_planets.v1` | `character_planets` |
| `populate_mining` | `esi-industry.read_character_mining.v1` | `character_mining` |
| `populate_loyalty` | `esi-characters.read_loyalty.v1` | `character_loyalty` |
| `populate_research` | `esi-characters.read_agents_research.v1` | `character_research` |
| `populate_fittings` | `esi-fittings.read_fittings.v1` | `character_fittings` |
| `populate_standings` | `esi-characters.read_standings.v1` | `character_standings` |
| `populate_killmails` | `esi-killmails.read_killmails.v1` | `character_killmails` |

`collectors/market/history.py` — `fetch_market_history()` is fully coded but only called
reactively from routes; no scheduled batch job exists. *(Phase 5: migrates to
`collectors/public_data/market.py`; Phase 6 adds the scheduled batch job.)*

### 2.3 Missing (Not Coded)

See §4 for the exhaustive endpoint → table mapping. Summary of gaps:
- **Personal:** character info enrichment, skill queue, corporation history, clones, fatigue,
  medals, titles, contacts/contracts/calendar enrichment, fittings, freelance, presence,
  wallet journal/txn, colonies enrichment, mail enrichment, FW stats, project contributions
- **Corporation (entire domain — 0 collectors):** all corp endpoints
- **Alliance (entire domain — 0 collectors):** contacts
- **Public (partial):** alliances, corporations enrichment, public contracts, freelance, incursions,
  industry facilities/costs, loyalty offers, market prices/items, FW, sovereignty, wars

---

## 3. Architectural Decisions

### 3.1 DuckDB 4-Tier Storage Architecture

**Decision: All data storage uses DuckDB. Four isolated database tiers.**

| Tier | Path | Keying | Content |
|------|------|--------|---------|
| **Public** | `_publicData/public.duckdb` | varies per table | SDE, market orders, structures, alliances, FW, sovereignty, wars, industry, etc. |
| **Personal** | `_privateData/<owner_id>/<owner_id>.duckdb` | `character_id` column | Per-character data: assets, mail, skills, wallet, industry, etc. |
| **Corporation** | `_privateData/<corporation_id>/<corporation_id>.duckdb` | none (implicit in file) | Corp assets, members, wallets, industry, structures, etc. |
| **Alliance** | `_privateData/<alliance_id>/<alliance_id>.duckdb` | none (implicit in file) | Alliance contacts |

Auth/token storage remains in existing SQLite per-owner (`_privateData/<owner_id>/<owner_id>.db`).
The `.db` SQLite file is managed by `core/db/private.py` (unchanged). The `.duckdb` data file
is a new addition alongside it.

**Rationale:**
- DuckDB's columnar storage provides vastly better analytical query performance.
- Consistent query syntax across all 4 tiers.
- `ATTACH` allows cross-database JOINs (e.g. personal data with public SDE).
- Per-entity isolation: deleting corp/alliance data is a single file removal.
- Entity-specific data never sits in the shared public warehouse.

**New infrastructure — `core/db/entity_db.py`:**

```python
import duckdb, os

PRIVATE_DATA_FOLDER = os.environ.get("PRIVATE_DATA_FOLDER", "_privateData")

_entity_connections: dict[int, duckdb.DuckDBPyConnection] = {}

def connect_entity(entity_id: int) -> duckdb.DuckDBPyConnection:
    """Fresh DuckDB connection for a per-entity database (owner, corp, or alliance)."""
    path = os.path.join(PRIVATE_DATA_FOLDER, str(entity_id), f"{entity_id}.duckdb")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return duckdb.connect(path)
```

### 3.2 Character-ID Keying

**Decision: All personal (per-owner) tables include `character_id BIGINT NOT NULL` in their
primary key.**

An owner can have multiple characters (via "Add Toon"). Each character's data must be
distinguishable within the same owner DuckDB file. Example:

```sql
CREATE TABLE IF NOT EXISTS character_skill_queue (
    character_id    BIGINT NOT NULL,
    queue_position  INTEGER NOT NULL,
    skill_id        INTEGER NOT NULL,
    ...
    PRIMARY KEY (character_id, queue_position)
);
```

**Migration needed:** Existing tables (`character_skills`, `character_wallet`, `character_assets`)
in SQLite must be migrated to the new owner DuckDB file with a `character_id` column. This is
a Phase 0 pre-requisite.

### 3.3 Character Collector Module Reorganisation

**Decision: Split `collectors/character/collectors.py` into domain sub-modules.**

```
collectors/character/
  __init__.py      # re-exports: populate_all, run_extended_refresh
  populate.py      # EXISTING — core character data (migrate to DuckDB + character_id)
  comms.py         # mail, mail_labels, mail_lists, notifications, notification_contacts, events, contacts
  finance.py       # contracts, market_orders, market_history, wallet_journal, wallet_txn, loyalty
  industry.py      # industry_jobs, mining, blueprints, colonies
  social.py        # standings, fittings, medals, titles, corporation_history, fw_stats
  combat.py        # killmails, fatigue, freelance_jobs
  identity.py      # characters (enriched), clones, agent_research, projects
  skillqueue.py    # skill queue (separate job, 30 min interval)
  presence.py      # location, online, ship (optional high-frequency job)
  extended.py      # run_extended_refresh() — orchestrator for scheduler
```

> **TODO: Scope Registry** — Each sub-module must call `register_collector_scopes()` at
> import time. See §3.8.

### 3.4 Scope-Gate Pattern

The `SCOPE_COLLECTORS` registry is the canonical per-character dispatch pattern.
`run_extended_refresh()`:

1. Queries `auth_users` for all `owner_id` values.
2. For each owner, calls `pick_token` → `fresh_token` to get a valid access token.
3. Fetches the owner's available scopes.
4. Iterates `SCOPE_COLLECTORS`; skips any entry whose scope the owner lacks.
5. Logs and continues on per-collector failures.

```python
# collectors/character/extended.py
def run_extended_refresh() -> None:
    from collectors.character.comms import SCOPE_COLLECTORS as _comms
    from collectors.character.finance import SCOPE_COLLECTORS as _finance
    # ... (all sub-modules)

    all_collectors = _comms + _finance + ...

    con = db.connect()
    try:
        rows = con.execute("SELECT DISTINCT owner_id FROM auth_users").fetchall()
        owner_ids = [r[0] for r in rows]
    finally:
        con.close()

    for owner_id in owner_ids:
        char_id, token_data = pick_token(owner_id)
        char_id, fresh_data = fresh_token(owner_id, char_id, token_data)
        access_token = fresh_data["access_token"]
        scopes = _get_scope_set(owner_id, char_id)
        for required_scope, domain, fn in all_collectors:
            if required_scope in scopes:
                fn(owner_id, char_id, access_token)
```

### 3.5 Excluded Endpoints

**No collectors created** for these scopes / endpoints:

| Scope / Endpoint | Reason |
|-------|--------|
| `esi-calendar.respond_calendar_events.v1` | Write only |
| `esi-characters.write_contacts.v1` | Write only |
| `esi-fittings.write_fittings.v1` | Write only |
| `esi-fleets.write_fleet.v1` | Write only |
| `esi-fleets.read_fleet.v1` | Real-time ephemeral state |
| `esi-mail.organize_mail.v1` | Write only |
| `esi-mail.send_mail.v1` | Write only |
| `esi-ui.open_window.v1` | Write only |
| `esi-ui.write_waypoint.v1` | Write only |
| `esi-search.search_structures.v1` | Query tool, not a collector |
| `/dogma/*` (attributes, effects, dynamic items) | Reference data — already in SDE (`dogmaAttributes.jsonl`, `dogmaEffects.jsonl`, `dynamicItemAttributes.jsonl`) |
| `/universe/*` reference endpoints (ancestries, bloodlines, categories, constellations, factions, graphics, groups, moons, planets, regions, stargates, stars, systems, types) | Reference data — already in SDE (30+ JSONL files). No need to collect from ESI. |
| `GET /characters/{character_id}/portrait` | Image URLs only — no storable data |
| `GET /alliances/{alliance_id}/icons` | Image URLs only — no storable data |
| `POST /characters/{character_id}/cspa` | Query tool — calculates CSPA charge cost on demand |
| `POST /route/{origin}/{destination}` | Utility — route calculation, not persistent data |
| `GET /corporations/npccorps` | Redundant — NPC corp list already in SDE (`npcCorporations.jsonl`) |
| `POST /universe/ids`, `POST /universe/names` | Utility — name ↔ ID resolution, not persistent data |

### 3.6 market_history Batch Strategy

Fetching history for all types × all regions would exceed 500k ESI calls per run.

**Strategy — active-types batch:**
1. Continue existing on-demand caching (route-triggered, already working).
2. New `market_history_refresh` job fetches top-N traded types per region:
   ```sql
   SELECT DISTINCT type_id FROM market_orders ORDER BY volume_total DESC LIMIT 500
   ```
   ~19 500 calls per run at 24 h interval. ETag caching reduces most to 304s.
3. Starts **disabled** — operator enables manually after confirming ESI rate budget.

### 3.7 Faction Warfare & Sovereignty Strategy

**FW — YES, create tables.** FW data is useful for alliance strategy tools and warzone
dashboards. Three public tables + personal FW stats + corp FW stats.

**Sovereignty — YES, create tables.** Sovereignty data shows nullsec territory ownership.
Three public tables: campaigns (active timers), map (system ownership), structures (TCUs/IHubs).
Sov changes rapidly during wars — 30 min refresh interval recommended.

### 3.8 Scope Registry (Future — Post-Collector Expansion)

**Decision: implement a declarative scope registry in `core/auth` after all collectors are wired.**

This is a follow-up task. Each collector section includes a `TODO: Scope Registry` marker.

1. **Minimal SSO login** — only identity-level scopes on first auth.
2. **Collectors register scopes** via `register_collector_scopes(domain, scopes)`.
3. **Applications declare collector dependencies** via `ToolManifest.required_collectors`.
4. **Progressive scope upgrade UX** — missing scopes prompt re-auth before app loads.
5. **New module:** `core/auth/scopes.py`.

### 3.9 Collector vs Analysis Boundary

**Decision: raw ESI → DB stays in `collectors/`; cross-entity enrichment and orchestration
moves to `analysis/`.**

A **collector** calls ESI endpoints scoped to a single entity (a character, a corporation, a
public list) and writes raw rows to that entity's database. If enrichment requires reading from
the database first, batching across multiple entities, or operates on data produced by *other*
collectors, it is an **analysis task** — a separate scheduled job in `analysis/`.

#### Classification Rule

| Enrichment Type | Belongs In | Reason |
|---|---|---|
| 1:1 detail fetch, same scope, bounded by list size (starbase detail, colony layout, event detail, mail body, contact labels) | **Inline collector** | N is bounded by the parent list; leaving rows half-populated buys nothing |
| Static config for a row — contract bids/items, project detail, observer ledger (personal/corp) | **Inline collector** | The row without its enrichment is not useful; same scope covers it |
| Cross-owner or cross-DB batching (`POST /characters/affiliation`, alliance/corp discovery) | **Analysis task** | Must read from multiple DBs or aggregate across entities |
| POST enrichment that reads from DB (`POST .../assets/locations`, `POST .../assets/names`) | **Analysis task** | Requires reading item_ids from DB first; potentially large payloads |
| High-volume, opt-in, N×calls where N could be thousands (killmail detail, war killmails, public contract items) | **Analysis task** | Rate-budget risk; operator should opt in |
| Shared detail endpoint used by multiple DBs (`/freelance-jobs/{job_id}`) | **Analysis task** | Calling from each collector independently wastes ESI budget; centralise |
| Universe-wide orchestration (market browser, region sweeps) | **Analysis task** | Reads from SDE + structures to coordinate raw collectors |

#### Inline Enrichments (stay in collectors)

These enrichment calls happen inside the collector that fetches the parent list:

| Collector | Enrichment Calls | Why Inline |
|---|---|---|
| `character/identity.py` — `characters` | `/attributes`, `/wallet`, `/location`, `/ship`, `/online`, `/roles`, `/implants` | 1:1, same character, bounded |
| `character/comms.py` — `character_events` | `/calendar/{event_id}`, `/calendar/{event_id}/attendees` | Bounded by event count |
| `character/comms.py` — `character_contacts` | `/contacts/labels` | 1 call |
| `character/comms.py` — `character_mail` | `/mail/{mail_id}` (body) | Bounded by mail list |
| `character/finance.py` — `character_contracts` | `/contracts/{id}/bids`, `/contracts/{id}/items` | Bounded by contract count, same scope |
| `character/industry.py` — `character_colonies` | `/planets/{planet_id}` | Bounded by planet count |
| `character/combat.py` — `character_freelance_jobs` | `/freelance-jobs/{job_id}/participation` | Same scope, personal-only |
| `corp/contacts.py` — `corp_contacts` | `/contacts/labels` | 1 call |
| `corp/contracts.py` — `corp_contracts` | `/contracts/{id}/bids`, `/contracts/{id}/items` | Bounded, same scope |
| `corp/members.py` — `corp_members` | `/membertracking`, `/members/titles`, `/roles`, `/roles/history` | Bounded by member count, same scope |
| `corp/infrastructure.py` — `corp_starbases` | `/starbases/{id}` | Bounded by starbase count |
| `corp/org.py` — `corp_projects` | `/projects/{id}`, `/projects/{id}/contributors` | Bounded by project count |
| `corp/industry.py` — `corp_mining_observers` | `/mining/observers/{id}` ledger | Bounded by observer count |
| `alliance/contacts.py` — `alliance_contacts` | `/contacts/labels` | 1 call |

#### Analysis Tasks (new `analysis/` modules)

These run as their own scheduled jobs with independent intervals:

| Module | What It Does | Tables It Enriches | Key Endpoints |
|---|---|---|---|
| `analysis/affiliation_sync.py` | Batch `POST /characters/affiliation` across all owner DBs | `characters.{corporation_id, alliance_id, faction_id}` in every personal DB | `POST /characters/affiliation` |
| `analysis/asset_enrichment.py` | Resolve asset names + positions for personal and corp assets | `character_assets.{name, position_*}`, `corp_assets.{name, position_*}` | `POST .../assets/locations`, `POST .../assets/names` |
| `analysis/killmail_enrichment.py` | Fetch full killmail details for personal + corp killmail hashes | `character_killmails.details_json`, `corp_killmails.details_json` | `GET /killmails/{id}/{hash}` |
| `analysis/alliance_enrichment.py` | Enrich `alliances` table: fetch details + member corp lists for all known alliance IDs | `alliances.*` (public DB) | `GET /alliances/{id}`, `GET /alliances/{id}/corporations` |
| `analysis/corporation_discovery.py` | Cross-DB aggregation to discover corp IDs, then fetch details + member limits | `corporations.*` (public DB) | `GET /corporations/{id}`, `GET /corporations/{id}/members/limit` |
| `analysis/public_contract_enrichment.py` | Fetch bids + items for public contracts | `public_contracts.{items_json, bids_json}` | `GET /contracts/public/bids/{id}`, `/items/{id}` |
| `analysis/war_enrichment.py` | Fetch war details + killmail lists | `wars.{detail columns, killmails_json}` | `GET /wars/{id}`, `GET /wars/{id}/killmails` |
| `analysis/freelance_enrichment.py` | Shared `/freelance-jobs/{job_id}` detail for public + personal + corp tables | `freelance_jobs.details_json`, `character_freelance_jobs.details_json`, `corp_freelance_jobs.details_json` | `GET /freelance-jobs/{job_id}` |
| `analysis/market_browser.py` | Universe-wide market orchestration: iterate regions via `sde_regions`, coordinate structure discovery | (orchestration — calls raw collectors) | N/A |

#### Import Rules for `analysis/`

- `analysis/` modules import from `core.*` and `collectors.*` — never from `applications/`.
- Applications import from `analysis/` via `applications/_api.py` to power dashboards.
- Analysis modules are registered as scheduler jobs like any other domain.
- Each analysis module owns no tables — it **enriches** columns on tables owned by collectors.

---

## 4. Endpoint → Table Map

### 4.1 PUBLIC DuckDB — `_publicData/public.duckdb`

#### PUBLIC `alliances`

`GET /alliances` → list of alliance IDs  
**Enrichment [analysis — `analysis/alliance_enrichment.py`]:** `GET /alliances/{alliance_id}` (details), `GET /alliances/{alliance_id}/corporations` (member corps)

```sql
CREATE TABLE IF NOT EXISTS alliances (
    alliance_id             BIGINT PRIMARY KEY,
    name                    TEXT,
    ticker                  TEXT,
    creator_id              BIGINT,
    creator_corporation_id  BIGINT,
    executor_corporation_id BIGINT,
    faction_id              INTEGER,
    date_founded            TIMESTAMP,
    member_corp_ids         BIGINT[],       -- from /corporations enrichment
    fetched_at              TIMESTAMP DEFAULT now()
);
```

#### PUBLIC `corporations`

**No bulk endpoint.** Populated via enrichment analysis — corp IDs discovered from alliance
member lists and personal DB character data.  
**Enrichment [analysis — `analysis/corporation_discovery.py`]:** `GET /corporations/{corporation_id}`, `GET /corporations/{corporation_id}/members/limit`

```sql
CREATE TABLE IF NOT EXISTS corporations (
    corporation_id  BIGINT PRIMARY KEY,
    alliance_id     BIGINT,
    ceo_id          BIGINT,
    creator_id      BIGINT,
    date_founded    TIMESTAMP,
    description     TEXT,
    faction_id      INTEGER,
    home_station_id BIGINT,
    member_count    INTEGER,
    name            TEXT,
    shares          BIGINT,
    tax_rate        REAL,
    ticker          TEXT,
    member_limit    INTEGER,        -- requires auth, may be NULL
    fetched_at      TIMESTAMP DEFAULT now()
);
```

> **Note:** NPC corporations are already in the SDE (`npcCorporations.jsonl`). The ESI endpoint
> `GET /corporations/npccorps` is not needed as a collector — cross-reference the SDE instead.

#### PUBLIC `public_contracts`

`GET /contracts/public/{region_id}`  
**Enrichment [analysis — `analysis/public_contract_enrichment.py`]:** `GET /contracts/public/bids/{contract_id}`, `GET /contracts/public/items/{contract_id}`

```sql
CREATE TABLE IF NOT EXISTS public_contracts (
    contract_id         BIGINT PRIMARY KEY,
    region_id           INTEGER NOT NULL,
    issuer_id           BIGINT NOT NULL,
    issuer_corporation_id BIGINT,
    assignee_id         BIGINT,
    type                TEXT,
    status              TEXT,
    title               TEXT,
    for_corporation     BOOLEAN DEFAULT FALSE,
    availability        TEXT,
    date_issued         TIMESTAMP,
    date_expired        TIMESTAMP,
    days_to_complete    INTEGER,
    start_location_id   BIGINT,
    end_location_id     BIGINT,
    price               DOUBLE DEFAULT 0,
    reward              DOUBLE DEFAULT 0,
    collateral          DOUBLE DEFAULT 0,
    buyout              DOUBLE DEFAULT 0,
    volume              DOUBLE DEFAULT 0,
    items_json          TEXT,           -- enrichment: JSON array of items
    bids_json           TEXT,           -- enrichment: JSON array of bids
    fetched_at          TIMESTAMP DEFAULT now()
);
```

#### PUBLIC `freelance_jobs`

`GET /freelance-jobs`  
**Enrichment [analysis — `analysis/freelance_enrichment.py`]:** `GET /freelance-jobs/{job_id}`

```sql
CREATE TABLE IF NOT EXISTS freelance_jobs (
    job_id          TEXT PRIMARY KEY,
    status          TEXT,
    details_json    TEXT,           -- enrichment: full job detail blob
    fetched_at      TIMESTAMP DEFAULT now()
);
```

#### PUBLIC `incursions`

`GET /incursions`

```sql
CREATE TABLE IF NOT EXISTS incursions (
    constellation_id            INTEGER PRIMARY KEY,
    faction_id                  INTEGER NOT NULL,
    has_boss                    BOOLEAN DEFAULT FALSE,
    infested_solar_systems      INTEGER[],
    influence                   REAL DEFAULT 0,
    staging_solar_system_id     INTEGER,
    state                       TEXT,
    type                        TEXT,
    fetched_at                  TIMESTAMP DEFAULT now()
);
```

#### PUBLIC `industry_facilities`

`GET /industry/facilities`

```sql
CREATE TABLE IF NOT EXISTS industry_facilities (
    facility_id     BIGINT PRIMARY KEY,
    owner_id        BIGINT,
    region_id       INTEGER,
    solar_system_id INTEGER,
    type_id         INTEGER,
    tax             REAL,
    fetched_at      TIMESTAMP DEFAULT now()
);
```

#### PUBLIC `industry_cost_indices`

`GET /industry/systems`

```sql
CREATE TABLE IF NOT EXISTS industry_cost_indices (
    solar_system_id INTEGER NOT NULL,
    activity        TEXT NOT NULL,
    cost_index      DOUBLE NOT NULL,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (solar_system_id, activity)
);
```

#### PUBLIC `loyalty_offers`

`GET /loyalty/stores/{corporation_id}/offers`

```sql
CREATE TABLE IF NOT EXISTS loyalty_offers (
    offer_id            INTEGER NOT NULL,
    corporation_id      BIGINT NOT NULL,
    type_id             INTEGER NOT NULL,
    quantity            INTEGER NOT NULL,
    lp_cost             INTEGER NOT NULL,
    isk_cost            BIGINT DEFAULT 0,
    ak_cost             INTEGER DEFAULT 0,
    required_items_json TEXT,
    fetched_at          TIMESTAMP DEFAULT now(),
    PRIMARY KEY (offer_id, corporation_id)
);
```

#### PUBLIC `market_prices`

`GET /markets/prices`

```sql
CREATE TABLE IF NOT EXISTS market_prices (
    type_id         INTEGER PRIMARY KEY,
    average_price   DOUBLE,
    adjusted_price  DOUBLE,
    fetched_at      TIMESTAMP DEFAULT now()
);
```

#### PUBLIC `market_items`

`GET /markets/{region_id}/types`

```sql
CREATE TABLE IF NOT EXISTS market_items (
    region_id   INTEGER NOT NULL,
    type_id     INTEGER NOT NULL,
    fetched_at  TIMESTAMP DEFAULT now(),
    PRIMARY KEY (region_id, type_id)
);
```

#### PUBLIC `fw_stats` / `fw_systems` / `fw_wars` / `fw_leaderboards`

`GET /fw/stats`, `GET /fw/systems`, `GET /fw/wars`, `GET /fw/leaderboards`

```sql
CREATE TABLE IF NOT EXISTS fw_stats (
    faction_id                  INTEGER PRIMARY KEY,
    kills_last_week             INTEGER DEFAULT 0,
    kills_total                 INTEGER DEFAULT 0,
    kills_yesterday             INTEGER DEFAULT 0,
    pilots                      INTEGER DEFAULT 0,
    systems_controlled          INTEGER DEFAULT 0,
    victory_points_last_week    INTEGER DEFAULT 0,
    victory_points_total        INTEGER DEFAULT 0,
    victory_points_yesterday    INTEGER DEFAULT 0,
    fetched_at                  TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fw_systems (
    solar_system_id             INTEGER PRIMARY KEY,
    contested                   TEXT,
    occupier_faction_id         INTEGER,
    owner_faction_id            INTEGER,
    victory_points              INTEGER DEFAULT 0,
    victory_points_threshold    INTEGER DEFAULT 0,
    fetched_at                  TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fw_wars (
    against_id  INTEGER NOT NULL,
    faction_id  INTEGER NOT NULL,
    PRIMARY KEY (against_id, faction_id)
);

CREATE TABLE IF NOT EXISTS fw_leaderboards (
    category    TEXT NOT NULL,      -- kills, victory_points
    timeframe   TEXT NOT NULL,      -- yesterday, last_week, total
    entity_type TEXT NOT NULL,      -- faction, corporation, character
    entity_id   BIGINT NOT NULL,
    amount      INTEGER NOT NULL,
    fetched_at  TIMESTAMP DEFAULT now(),
    PRIMARY KEY (category, timeframe, entity_type, entity_id)
);
```

#### PUBLIC `sovereignty_campaigns` / `sovereignty_map` / `sovereignty_structures`

`GET /sovereignty/campaigns`, `GET /sovereignty/map`, `GET /sovereignty/structures`

```sql
CREATE TABLE IF NOT EXISTS sovereignty_campaigns (
    campaign_id         INTEGER PRIMARY KEY,
    solar_system_id     INTEGER NOT NULL,
    constellation_id    INTEGER,
    structure_id        BIGINT NOT NULL,
    event_type          TEXT,
    start_time          TIMESTAMP,
    defender_id         BIGINT,
    defender_score      REAL,
    attackers_score     REAL,
    participants_json   TEXT,
    fetched_at          TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sovereignty_map (
    system_id       INTEGER PRIMARY KEY,
    alliance_id     BIGINT,
    corporation_id  BIGINT,
    faction_id      INTEGER,
    fetched_at      TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sovereignty_structures (
    structure_id                    BIGINT PRIMARY KEY,
    alliance_id                     BIGINT,
    solar_system_id                 INTEGER NOT NULL,
    type_id                         INTEGER NOT NULL,
    vulnerability_occupancy_level   REAL,
    vulnerable_start_time           TIMESTAMP,
    vulnerable_end_time             TIMESTAMP,
    fetched_at                      TIMESTAMP DEFAULT now()
);
```

#### PUBLIC `wars`

`GET /wars`  
**Enrichment [analysis — `analysis/war_enrichment.py`]:** `GET /wars/{war_id}`, `GET /wars/{war_id}/killmails`

```sql
CREATE TABLE IF NOT EXISTS wars (
    war_id          INTEGER PRIMARY KEY,
    aggressor_id    BIGINT,
    aggressor_type  TEXT,
    defender_id     BIGINT,
    defender_type   TEXT,
    declared        TIMESTAMP,
    started         TIMESTAMP,
    finished        TIMESTAMP,
    retracted       TIMESTAMP,
    mutual          BOOLEAN DEFAULT FALSE,
    open_for_allies BOOLEAN DEFAULT FALSE,
    allies_json     TEXT,
    killmails_json  TEXT,           -- enrichment
    fetched_at      TIMESTAMP DEFAULT now()
);
```

#### PUBLIC `server_status`

`GET /status`

```sql
CREATE TABLE IF NOT EXISTS server_status (
    id              INTEGER DEFAULT 1 PRIMARY KEY,
    checked_at      TIMESTAMP,
    start_time      TIMESTAMP,
    players         INTEGER DEFAULT 0,
    server_version  TEXT,
    vip             BOOLEAN DEFAULT FALSE
);
```

#### PUBLIC `insurance_prices`

`GET /insurance/prices`

```sql
CREATE TABLE IF NOT EXISTS insurance_prices (
    type_id     INTEGER NOT NULL,
    level       TEXT NOT NULL,
    cost        DOUBLE NOT NULL,
    payout      DOUBLE NOT NULL,
    fetched_at  TIMESTAMP DEFAULT now(),
    PRIMARY KEY (type_id, level)
);
```

**PUBLIC tables already live (migrating to `public_data/` in Phase 5 — no schema changes needed):**
- `market_orders` — `collectors/public_data/market.py` *(was `collectors/market/regions.py`)*
- `market_region_cooldowns` — `collectors/public_data/market.py` *(was `collectors/market/regions.py`)*
- `market_structures` — `collectors/public_data/market.py` *(was `collectors/market/structures.py`)*
- `structures` — `collectors/public_data/structures.py` *(was `collectors/structures/discover.py`)*
- `market_history` — `collectors/public_data/market.py` *(was `collectors/market/history.py`)*

---

### 4.2 PERSONAL DuckDB — `_privateData/<owner_id>/<owner_id>.duckdb`

All tables include `character_id BIGINT NOT NULL` in their primary key.

#### PERSONAL `characters`

**Primary:** `GET /characters/{character_id}`  
**Enrichment [inline]:**
- `GET /characters/{character_id}/roles`
- `GET /characters/{character_id}/implants`
- `GET /characters/{character_id}/location`
- `GET /characters/{character_id}/online`
- `GET /characters/{character_id}/ship`
- `GET /characters/{character_id}/attributes`
- `GET /characters/{character_id}/wallet`

**Enrichment [analysis — `analysis/affiliation_sync.py`]:**
- `POST /characters/affiliation` (batch across all owner DBs to enrich this table)

```sql
CREATE TABLE IF NOT EXISTS characters (
    character_id        BIGINT PRIMARY KEY,
    name                TEXT,
    birthday            TIMESTAMP,
    gender              TEXT,
    race_id             INTEGER,
    bloodline_id        INTEGER,
    ancestry_id         INTEGER,
    security_status     REAL,
    description         TEXT,
    title               TEXT,
    -- /characters/affiliation enrichment
    corporation_id      BIGINT,
    alliance_id         BIGINT,
    faction_id          INTEGER,
    -- /attributes enrichment
    charisma            INTEGER,
    intelligence        INTEGER,
    memory              INTEGER,
    perception          INTEGER,
    willpower           INTEGER,
    bonus_remaps        INTEGER,
    last_remap_date     TIMESTAMP,
    accrued_remap_cooldown_date TIMESTAMP,
    -- /wallet enrichment
    wallet_balance      DOUBLE,
    -- /location enrichment
    solar_system_id     INTEGER,
    station_id          BIGINT,
    structure_id        BIGINT,
    -- /ship enrichment
    ship_type_id        INTEGER,
    ship_item_id        BIGINT,
    ship_name           TEXT,
    -- /online enrichment
    is_online           BOOLEAN DEFAULT FALSE,
    last_login          TIMESTAMP,
    last_logout         TIMESTAMP,
    logins              INTEGER,
    -- /roles enrichment (JSON arrays)
    roles_json          TEXT,
    roles_at_hq_json    TEXT,
    roles_at_base_json  TEXT,
    roles_at_other_json TEXT,
    -- /implants enrichment
    implants            INTEGER[],
    fetched_at          TIMESTAMP DEFAULT now()
);
```

#### PERSONAL `character_assets`

`GET /characters/{character_id}/assets`
**Enrichment [analysis — `analysis/asset_enrichment.py`]:** `POST /characters/{character_id}/assets/locations` (resolve exact coordinates),
`POST /characters/{character_id}/assets/names` (resolve custom names). Both use the same
`esi-assets.read_assets.v1` scope — no additional auth needed.

```sql
CREATE TABLE IF NOT EXISTS character_assets (
    character_id    BIGINT NOT NULL,
    item_id         BIGINT NOT NULL,
    type_id         INTEGER NOT NULL,
    location_id     BIGINT NOT NULL,
    location_type   TEXT,
    location_flag   TEXT,
    quantity        INTEGER NOT NULL DEFAULT 1,
    is_singleton    BOOLEAN DEFAULT FALSE,
    is_blueprint_copy BOOLEAN,
    -- enrichment from POST /assets/names
    name            TEXT,
    -- enrichment from POST /assets/locations
    position_x      DOUBLE,
    position_y      DOUBLE,
    position_z      DOUBLE,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, item_id)
);
```

#### PERSONAL `character_events`

`GET /characters/{character_id}/calendar`  
**Enrichment [inline]:** `GET /characters/{character_id}/calendar/{event_id}`,
`GET /characters/{character_id}/calendar/{event_id}/attendees`

```sql
CREATE TABLE IF NOT EXISTS character_events (
    character_id    BIGINT NOT NULL,
    event_id        INTEGER NOT NULL,
    event_date      TIMESTAMP,
    title           TEXT,
    importance      INTEGER,
    event_response  TEXT,
    -- enrichment from /calendar/{event_id}
    owner_id        BIGINT,
    owner_type      TEXT,
    owner_name      TEXT,
    text            TEXT,
    duration        INTEGER,
    -- enrichment: attendees as JSON array
    attendees_json  TEXT,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, event_id)
);
```

#### PERSONAL `character_agent_research`

`GET /characters/{character_id}/agents_research`

```sql
CREATE TABLE IF NOT EXISTS character_agent_research (
    character_id        BIGINT NOT NULL,
    agent_id            INTEGER NOT NULL,
    points_per_day      REAL,
    remainder_points    REAL,
    skill_type_id       INTEGER,
    started_at          TIMESTAMP,
    fetched_at          TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, agent_id)
);
```

#### PERSONAL `character_blueprints`

`GET /characters/{character_id}/blueprints`

```sql
CREATE TABLE IF NOT EXISTS character_blueprints (
    character_id        BIGINT NOT NULL,
    item_id             BIGINT NOT NULL,
    location_id         BIGINT,
    location_flag       TEXT,
    type_id             INTEGER NOT NULL,
    quantity            INTEGER DEFAULT 1,
    time_efficiency     INTEGER DEFAULT 0,
    material_efficiency INTEGER DEFAULT 0,
    runs                INTEGER DEFAULT -1,
    fetched_at          TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, item_id)
);
```

#### PERSONAL `character_corporation_history`

`GET /characters/{character_id}/corporationhistory` — **public, no scope**

```sql
CREATE TABLE IF NOT EXISTS character_corporation_history (
    character_id    BIGINT NOT NULL,
    record_id       INTEGER NOT NULL,
    corporation_id  BIGINT NOT NULL,
    start_date      TIMESTAMP NOT NULL,
    is_deleted      BOOLEAN DEFAULT FALSE,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, record_id)
);
```

#### PERSONAL `character_jump_fatigue`

`GET /characters/{character_id}/fatigue`

```sql
CREATE TABLE IF NOT EXISTS character_jump_fatigue (
    character_id                BIGINT PRIMARY KEY,
    jump_fatigue_expire_date    TIMESTAMP,
    last_jump_date              TIMESTAMP,
    last_update_date            TIMESTAMP,
    fetched_at                  TIMESTAMP DEFAULT now()
);
```

#### PERSONAL `character_medals`

`GET /characters/{character_id}/medals`

```sql
CREATE TABLE IF NOT EXISTS character_medals (
    character_id    BIGINT NOT NULL,
    medal_id        INTEGER NOT NULL,
    corporation_id  BIGINT NOT NULL,
    title           TEXT,
    description     TEXT,
    date            TIMESTAMP,
    issuer_id       BIGINT,
    reason          TEXT,
    status          TEXT,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, medal_id, corporation_id)
);
```

#### PERSONAL `character_notifications`

`GET /characters/{character_id}/notifications`  
`GET /characters/{character_id}/notifications/contacts`

```sql
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
);

CREATE TABLE IF NOT EXISTS character_notification_contacts (
    character_id        BIGINT NOT NULL,
    notification_id     BIGINT NOT NULL,
    message             TEXT,
    send_date           TIMESTAMP,
    sender_character_id BIGINT,
    standing_level      REAL,
    fetched_at          TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, notification_id)
);
```

#### PERSONAL `character_standings`

`GET /characters/{character_id}/standings`

```sql
CREATE TABLE IF NOT EXISTS character_standings (
    character_id    BIGINT NOT NULL,
    from_id         BIGINT NOT NULL,
    from_type       TEXT NOT NULL,
    standing        REAL NOT NULL,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, from_id, from_type)
);
```

#### PERSONAL `character_clones`

`GET /characters/{character_id}/clones`

```sql
CREATE TABLE IF NOT EXISTS character_clones (
    character_id                BIGINT PRIMARY KEY,
    home_location_id            BIGINT,
    home_location_type          TEXT,
    last_clone_jump_date        TIMESTAMP,
    last_station_change_date    TIMESTAMP,
    jump_clones_json            TEXT,
    fetched_at                  TIMESTAMP DEFAULT now()
);
```

#### PERSONAL `character_contacts`

`GET /characters/{character_id}/contacts`  
**Enrichment [inline]:** `GET /characters/{character_id}/contacts/labels`

```sql
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
);

CREATE TABLE IF NOT EXISTS character_contact_labels (
    character_id    BIGINT NOT NULL,
    label_id        BIGINT NOT NULL,
    label_name      TEXT,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, label_id)
);
```

#### PERSONAL `character_contracts`

`GET /characters/{character_id}/contracts`  
**Enrichment [inline]:** `GET /characters/{character_id}/contracts/{contract_id}/bids`,
`GET /characters/{character_id}/contracts/{contract_id}/items`

```sql
CREATE TABLE IF NOT EXISTS character_contracts (
    character_id        BIGINT NOT NULL,
    contract_id         BIGINT NOT NULL,
    issuer_id           BIGINT NOT NULL,
    issuer_corporation_id BIGINT,
    assignee_id         BIGINT,
    acceptor_id         BIGINT,
    type                TEXT,
    status              TEXT,
    availability        TEXT,
    title               TEXT,
    for_corporation     BOOLEAN DEFAULT FALSE,
    date_issued         TIMESTAMP,
    date_expired        TIMESTAMP,
    date_accepted       TIMESTAMP,
    date_completed      TIMESTAMP,
    days_to_complete    INTEGER,
    start_location_id   BIGINT,
    end_location_id     BIGINT,
    price               DOUBLE DEFAULT 0,
    reward              DOUBLE DEFAULT 0,
    collateral          DOUBLE DEFAULT 0,
    buyout              DOUBLE DEFAULT 0,
    volume              DOUBLE DEFAULT 0,
    items_json          TEXT,
    bids_json           TEXT,
    fetched_at          TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, contract_id)
);
```

#### PERSONAL `character_fittings`

`GET /characters/{character_id}/fittings`

```sql
CREATE TABLE IF NOT EXISTS character_fittings (
    character_id    BIGINT NOT NULL,
    fitting_id      BIGINT NOT NULL,
    name            TEXT,
    description     TEXT,
    ship_type_id    INTEGER,
    items_json      TEXT,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, fitting_id)
);
```

#### PERSONAL `character_freelance_jobs`

`GET /characters/{character_id}/freelance-jobs`  
**Enrichment [analysis — `analysis/freelance_enrichment.py`]:** `GET /freelance-jobs/{job_id}` (public detail shared across DBs)
**Enrichment [inline]:** `GET /characters/{character_id}/freelance-jobs/{job_id}/participation` (personal participation stats)

```sql
CREATE TABLE IF NOT EXISTS character_freelance_jobs (
    character_id        BIGINT NOT NULL,
    job_id              TEXT NOT NULL,
    status              TEXT,
    details_json        TEXT,           -- enrichment from public /freelance-jobs/{job_id}
    participation_json  TEXT,           -- enrichment from /freelance-jobs/{job_id}/participation
    fetched_at          TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, job_id)
);
```

#### PERSONAL `character_industry_jobs`

`GET /characters/{character_id}/industry/jobs`

```sql
CREATE TABLE IF NOT EXISTS character_industry_jobs (
    character_id        BIGINT NOT NULL,
    job_id              INTEGER NOT NULL,
    installer_id        BIGINT,
    facility_id         BIGINT,
    station_id          BIGINT,
    activity_id         INTEGER,
    blueprint_id        BIGINT,
    blueprint_type_id   INTEGER,
    blueprint_location_id BIGINT,
    output_location_id  BIGINT,
    runs                INTEGER,
    cost                DOUBLE,
    licensed_runs       INTEGER,
    probability         REAL,
    product_type_id     INTEGER,
    status              TEXT,
    duration            INTEGER,
    start_date          TIMESTAMP,
    end_date            TIMESTAMP,
    pause_date          TIMESTAMP,
    completed_date      TIMESTAMP,
    completed_character_id BIGINT,
    fetched_at          TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, job_id)
);
```

#### PERSONAL `character_mining`

`GET /characters/{character_id}/mining`

```sql
CREATE TABLE IF NOT EXISTS character_mining (
    character_id    BIGINT NOT NULL,
    date            TIMESTAMP NOT NULL,
    solar_system_id INTEGER NOT NULL,
    type_id         INTEGER NOT NULL,
    quantity        BIGINT NOT NULL,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, date, solar_system_id, type_id)
);
```

#### PERSONAL `character_killmails`

`GET /characters/{character_id}/killmails/recent`
**Enrichment [analysis — `analysis/killmail_enrichment.py`]:** `GET /killmails/{killmail_id}/{killmail_hash}` — public endpoint, resolves
full killmail detail from hash+id pair. High-volume enrichment — opt-in.

```sql
CREATE TABLE IF NOT EXISTS character_killmails (
    character_id    BIGINT NOT NULL,
    killmail_id     BIGINT NOT NULL,
    killmail_hash   TEXT NOT NULL,
    -- enrichment from public /killmails/{killmail_id}/{killmail_hash}
    details_json    TEXT,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, killmail_id)
);
```

#### PERSONAL `character_loyalty_points`

`GET /characters/{character_id}/loyalty/points`

```sql
CREATE TABLE IF NOT EXISTS character_loyalty_points (
    character_id    BIGINT NOT NULL,
    corporation_id  BIGINT NOT NULL,
    loyalty_points  INTEGER NOT NULL,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, corporation_id)
);
```

#### PERSONAL `character_mail` / `character_mail_labels` / `character_mail_lists`

`GET /characters/{character_id}/mail`  
**Enrichment [inline]:** `GET /characters/{character_id}/mail/{mail_id}`  
`GET /characters/{character_id}/mail/labels`  
`GET /characters/{character_id}/mail/lists`

```sql
CREATE TABLE IF NOT EXISTS character_mail (
    character_id    BIGINT NOT NULL,
    mail_id         BIGINT NOT NULL,
    from_id         BIGINT,
    subject         TEXT,
    body            TEXT,               -- enrichment from /mail/{id}
    timestamp       TIMESTAMP,
    is_read         BOOLEAN DEFAULT FALSE,
    labels          BIGINT[],
    recipients_json TEXT,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, mail_id)
);

CREATE TABLE IF NOT EXISTS character_mail_labels (
    character_id    BIGINT NOT NULL,
    label_id        BIGINT NOT NULL,
    name            TEXT,
    color           TEXT,
    unread_count    INTEGER DEFAULT 0,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, label_id)
);

CREATE TABLE IF NOT EXISTS character_mail_lists (
    character_id    BIGINT NOT NULL,
    mailing_list_id BIGINT NOT NULL,
    name            TEXT,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, mailing_list_id)
);
```

#### PERSONAL `character_market_orders` / `character_market_history`

`GET /characters/{character_id}/orders`  
`GET /characters/{character_id}/orders/history`

```sql
CREATE TABLE IF NOT EXISTS character_market_orders (
    character_id    BIGINT NOT NULL,
    order_id        BIGINT NOT NULL,
    type_id         INTEGER NOT NULL,
    region_id       INTEGER,
    location_id     BIGINT,
    volume_total    INTEGER,
    volume_remain   INTEGER,
    min_volume      INTEGER DEFAULT 1,
    price           DOUBLE NOT NULL,
    is_buy_order    BOOLEAN DEFAULT FALSE,
    issued          TIMESTAMP,
    duration        INTEGER,
    order_range     TEXT,
    escrow          DOUBLE,
    is_corporation  BOOLEAN DEFAULT FALSE,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, order_id)
);

CREATE TABLE IF NOT EXISTS character_market_history (
    character_id    BIGINT NOT NULL,
    order_id        BIGINT NOT NULL,
    type_id         INTEGER NOT NULL,
    region_id       INTEGER,
    location_id     BIGINT,
    price           DOUBLE,
    volume_total    INTEGER,
    volume_remain   INTEGER,
    issued          TIMESTAMP,
    state           TEXT,
    is_buy_order    BOOLEAN DEFAULT FALSE,
    escrow          DOUBLE,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, order_id)
);
```

#### PERSONAL `character_colonies`

`GET /characters/{character_id}/planets`  
**Enrichment [inline]:** `GET /characters/{character_id}/planets/{planet_id}`

```sql
CREATE TABLE IF NOT EXISTS character_colonies (
    character_id    BIGINT NOT NULL,
    planet_id       INTEGER NOT NULL,
    planet_type     TEXT,
    solar_system_id INTEGER,
    owner_id        BIGINT,
    upgrade_level   INTEGER,
    num_pins        INTEGER,
    last_update     TIMESTAMP,
    -- enrichment from /planets/{planet_id}
    pins_json       TEXT,
    routes_json     TEXT,
    links_json      TEXT,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, planet_id)
);
```

#### PERSONAL `character_skill_queue`

`GET /characters/{character_id}/skillqueue`

```sql
CREATE TABLE IF NOT EXISTS character_skill_queue (
    character_id    BIGINT NOT NULL,
    queue_position  INTEGER NOT NULL,
    skill_id        INTEGER NOT NULL,
    finished_level  INTEGER NOT NULL,
    start_date      TIMESTAMP,
    finish_date     TIMESTAMP,
    level_start_sp  INTEGER,
    level_end_sp    INTEGER,
    training_start_sp INTEGER,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, queue_position)
);
```

#### PERSONAL `character_skills`

`GET /characters/{character_id}/skills` — **exists in SQLite, needs DuckDB migration**

```sql
CREATE TABLE IF NOT EXISTS character_skills (
    character_id        BIGINT NOT NULL,
    skill_id            INTEGER NOT NULL,
    active_skill_level  INTEGER NOT NULL,
    trained_skill_level INTEGER NOT NULL,
    skillpoints_in_skill BIGINT NOT NULL,
    fetched_at          TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, skill_id)
);
```

#### PERSONAL `character_wallet_journal` / `character_wallet_transactions`

`GET /characters/{character_id}/wallet/journal`  
`GET /characters/{character_id}/wallet/transactions`

```sql
CREATE TABLE IF NOT EXISTS character_wallet_journal (
    character_id    BIGINT NOT NULL,
    id              BIGINT NOT NULL,
    date            TIMESTAMP NOT NULL,
    ref_type        TEXT,
    first_party_id  BIGINT,
    second_party_id BIGINT,
    amount          DOUBLE,
    balance         DOUBLE,
    reason          TEXT,
    context_id      BIGINT,
    context_id_type TEXT,
    description     TEXT,
    tax             DOUBLE,
    tax_receiver_id BIGINT,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, id)
);

CREATE TABLE IF NOT EXISTS character_wallet_transactions (
    character_id    BIGINT NOT NULL,
    transaction_id  BIGINT NOT NULL,
    date            TIMESTAMP NOT NULL,
    type_id         INTEGER NOT NULL,
    location_id     BIGINT NOT NULL,
    unit_price      DOUBLE NOT NULL,
    quantity        INTEGER NOT NULL,
    client_id       BIGINT NOT NULL,
    is_buy          BOOLEAN DEFAULT FALSE,
    is_personal     BOOLEAN DEFAULT TRUE,
    journal_ref_id  BIGINT,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, transaction_id)
);
```

#### PERSONAL `character_fw_stats`

`GET /characters/{character_id}/fw/stats`

```sql
CREATE TABLE IF NOT EXISTS character_fw_stats (
    character_id                BIGINT PRIMARY KEY,
    current_rank                INTEGER,
    highest_rank                INTEGER,
    enlisted_on                 TIMESTAMP,
    faction_id                  INTEGER,
    kills_last_week             INTEGER DEFAULT 0,
    kills_total                 INTEGER DEFAULT 0,
    kills_yesterday             INTEGER DEFAULT 0,
    victory_points_last_week    INTEGER DEFAULT 0,
    victory_points_total        INTEGER DEFAULT 0,
    victory_points_yesterday    INTEGER DEFAULT 0,
    fetched_at                  TIMESTAMP DEFAULT now()
);
```

#### PERSONAL `character_titles`

`GET /characters/{character_id}/titles`

```sql
CREATE TABLE IF NOT EXISTS character_titles (
    character_id    BIGINT NOT NULL,
    title_id        INTEGER NOT NULL,
    name            TEXT,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, title_id)
);
```

#### PERSONAL `character_projects`

`GET /corporations/{corporation_id}/projects/{project_id}/contribution/{character_id}`

```sql
CREATE TABLE IF NOT EXISTS character_projects (
    character_id    BIGINT NOT NULL,
    project_id      INTEGER NOT NULL,
    corporation_id  BIGINT NOT NULL,
    contribution_json TEXT,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (character_id, project_id)
);
```

---

### 4.3 CORPORATION DuckDB — `_privateData/<corporation_id>/<corporation_id>.duckdb`

No `corporation_id` column needed — implicit in the database file.

#### CORP `corp_stats`

`GET /corporations/{corporation_id}` — **public, no scope**

```sql
CREATE TABLE IF NOT EXISTS corp_stats (
    id                  INTEGER DEFAULT 1 PRIMARY KEY,
    alliance_id         BIGINT,
    ceo_id              BIGINT,
    creator_id          BIGINT,
    date_founded        TIMESTAMP,
    description         TEXT,
    faction_id          INTEGER,
    home_station_id     BIGINT,
    member_count        INTEGER,
    member_limit        INTEGER,
    name                TEXT,
    shares              BIGINT,
    tax_rate            REAL,
    ticker              TEXT,
    fetched_at          TIMESTAMP DEFAULT now()
);
```

#### CORP `corp_alliance_history`

`GET /corporations/{corporation_id}/alliancehistory` — **public, no scope**

```sql
CREATE TABLE IF NOT EXISTS corp_alliance_history (
    record_id       INTEGER PRIMARY KEY,
    alliance_id     BIGINT,
    start_date      TIMESTAMP NOT NULL,
    is_deleted      BOOLEAN DEFAULT FALSE,
    fetched_at      TIMESTAMP DEFAULT now()
);
```

#### CORP `corp_assets`

`GET /corporations/{corporation_id}/assets` — paginated
**Enrichment [analysis — `analysis/asset_enrichment.py`]:** `POST /corporations/{corporation_id}/assets/locations` (resolve exact coordinates),
`POST /corporations/{corporation_id}/assets/names` (resolve custom names). Both use the same
`esi-assets.read_corporation_assets.v1` scope — no additional auth needed.

```sql
CREATE TABLE IF NOT EXISTS corp_assets (
    item_id             BIGINT PRIMARY KEY,
    type_id             INTEGER NOT NULL,
    location_id         BIGINT NOT NULL,
    location_type       TEXT,
    location_flag       TEXT,
    quantity            INTEGER NOT NULL DEFAULT 1,
    is_singleton        BOOLEAN DEFAULT FALSE,
    is_blueprint_copy   BOOLEAN,
    -- enrichment from POST /assets/names
    name                TEXT,
    -- enrichment from POST /assets/locations
    position_x          DOUBLE,
    position_y          DOUBLE,
    position_z          DOUBLE,
    fetched_at          TIMESTAMP DEFAULT now()
);
```

#### CORP `corp_blueprints`

`GET /corporations/{corporation_id}/blueprints` — paginated

```sql
CREATE TABLE IF NOT EXISTS corp_blueprints (
    item_id             BIGINT PRIMARY KEY,
    location_id         BIGINT NOT NULL,
    location_flag       TEXT,
    type_id             INTEGER NOT NULL,
    quantity            INTEGER DEFAULT 1,
    time_efficiency     INTEGER DEFAULT 0,
    material_efficiency INTEGER DEFAULT 0,
    runs                INTEGER DEFAULT -1,
    fetched_at          TIMESTAMP DEFAULT now()
);
```

#### CORP `corp_contacts`

`GET /corporations/{corporation_id}/contacts` — paginated  
**Enrichment [inline]:** `GET /corporations/{corporation_id}/contacts/labels`

```sql
CREATE TABLE IF NOT EXISTS corp_contacts (
    contact_id      BIGINT PRIMARY KEY,
    contact_type    TEXT,
    standing        REAL,
    is_watched      BOOLEAN DEFAULT FALSE,
    label_ids       BIGINT[],
    fetched_at      TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS corp_contact_labels (
    label_id    BIGINT PRIMARY KEY,
    label_name  TEXT,
    fetched_at  TIMESTAMP DEFAULT now()
);
```

#### CORP `corp_contracts`

`GET /corporations/{corporation_id}/contracts` — paginated  
**Enrichment [inline]:** `/contracts/{contract_id}/bids`, `/contracts/{contract_id}/items`

```sql
CREATE TABLE IF NOT EXISTS corp_contracts (
    contract_id         BIGINT PRIMARY KEY,
    acceptor_id         BIGINT,
    assignee_id         BIGINT,
    issuer_id           BIGINT NOT NULL,
    issuer_corporation_id BIGINT,
    status              TEXT,
    type                TEXT,
    availability        TEXT,
    for_corporation     BOOLEAN DEFAULT FALSE,
    date_issued         TIMESTAMP,
    date_expired        TIMESTAMP,
    date_accepted       TIMESTAMP,
    date_completed      TIMESTAMP,
    days_to_complete    INTEGER,
    end_location_id     BIGINT,
    start_location_id   BIGINT,
    price               DOUBLE DEFAULT 0,
    reward              DOUBLE DEFAULT 0,
    collateral          DOUBLE DEFAULT 0,
    buyout              DOUBLE DEFAULT 0,
    volume              DOUBLE DEFAULT 0,
    title               TEXT,
    items_json          TEXT,
    bids_json           TEXT,
    fetched_at          TIMESTAMP DEFAULT now()
);
```

#### CORP `corp_divisions`

`GET /corporations/{corporation_id}/divisions`

```sql
CREATE TABLE IF NOT EXISTS corp_divisions (
    division_type   TEXT NOT NULL,
    division_number INTEGER NOT NULL,
    name            TEXT,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (division_type, division_number)
);
```

#### CORP `corp_facilities`

`GET /corporations/{corporation_id}/facilities`

```sql
CREATE TABLE IF NOT EXISTS corp_facilities (
    facility_id BIGINT PRIMARY KEY,
    system_id   INTEGER,
    type_id     INTEGER,
    fetched_at  TIMESTAMP DEFAULT now()
);
```

#### CORP `corp_medals` / `corp_issued_medals`

`GET /corporations/{corporation_id}/medals`  
`GET /corporations/{corporation_id}/medals/issued`

```sql
CREATE TABLE IF NOT EXISTS corp_medals (
    medal_id    INTEGER PRIMARY KEY,
    title       TEXT,
    description TEXT,
    created     TIMESTAMP,
    creator_id  BIGINT,
    fetched_at  TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS corp_issued_medals (
    medal_id        INTEGER NOT NULL,
    character_id    BIGINT NOT NULL,
    issued_at       TIMESTAMP,
    issuer_id       BIGINT,
    reason          TEXT,
    status          TEXT,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (medal_id, character_id)
);
```

#### CORP `corp_members`

`GET /corporations/{corporation_id}/members`  
**Enrichment [inline]:**
- `GET /corporations/{corporation_id}/members/titles`
- `GET /corporations/{corporation_id}/roles`
- `GET /corporations/{corporation_id}/membertracking`

```sql
CREATE TABLE IF NOT EXISTS corp_members (
    character_id            BIGINT PRIMARY KEY,
    start_date              TIMESTAMP,
    -- enrichment from /membertracking
    base_id                 BIGINT,
    location_id             BIGINT,
    logoff_date             TIMESTAMP,
    logon_date              TIMESTAMP,
    ship_type_id            INTEGER,
    -- enrichment from /roles
    roles_json              TEXT,
    grantable_roles_json    TEXT,
    roles_at_hq_json        TEXT,
    roles_at_base_json      TEXT,
    roles_at_other_json     TEXT,
    -- enrichment from /roles/history
    roles_history_json      TEXT,
    -- enrichment from /members/titles
    title_ids               INTEGER[],
    fetched_at              TIMESTAMP DEFAULT now()
);
```

#### CORP `corp_shareholders`

`GET /corporations/{corporation_id}/shareholders`

```sql
CREATE TABLE IF NOT EXISTS corp_shareholders (
    shareholder_id      BIGINT NOT NULL,
    shareholder_type    TEXT NOT NULL,
    share_count         BIGINT NOT NULL,
    fetched_at          TIMESTAMP DEFAULT now(),
    PRIMARY KEY (shareholder_id, shareholder_type)
);
```

#### CORP `corp_standings`

`GET /corporations/{corporation_id}/standings`

```sql
CREATE TABLE IF NOT EXISTS corp_standings (
    from_id     BIGINT NOT NULL,
    from_type   TEXT NOT NULL,
    standing    REAL NOT NULL,
    fetched_at  TIMESTAMP DEFAULT now(),
    PRIMARY KEY (from_id, from_type)
);
```

#### CORP `corp_starbases`

`GET /corporations/{corporation_id}/starbases`  
**Enrichment [inline]:** `GET /corporations/{corporation_id}/starbases/{starbase_id}`

```sql
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
    -- detail from /starbases/{id}
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
);
```

#### CORP `corp_structures`

`GET /corporations/{corporation_id}/structures`

```sql
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
);
```

#### CORP `corp_titles`

`GET /corporations/{corporation_id}/titles`

```sql
CREATE TABLE IF NOT EXISTS corp_titles (
    title_id                INTEGER PRIMARY KEY,
    name                    TEXT,
    roles_json              TEXT,
    grantable_roles_json    TEXT,
    fetched_at              TIMESTAMP DEFAULT now()
);
```

#### CORP `corp_projects`

`GET /corporations/{corporation_id}/projects`  
**Enrichment [inline]:** `GET /corporations/{corporation_id}/projects/{project_id}` (detail),
`GET /corporations/{corporation_id}/projects/{project_id}/contributors` (contributor list)

```sql
CREATE TABLE IF NOT EXISTS corp_projects (
    project_id          INTEGER PRIMARY KEY,
    name                TEXT,
    status              TEXT,
    reward_type_id      INTEGER,
    reward_quantity     INTEGER,
    description         TEXT,
    details_json        TEXT,           -- enrichment from /projects/{project_id}
    contributors_json   TEXT,           -- enrichment from /projects/{project_id}/contributors
    fetched_at          TIMESTAMP DEFAULT now()
);
```

#### CORP `corp_freelance_jobs`

`GET /corporations/{corporation_id}/freelance-jobs`  
**Enrichment [analysis — `analysis/freelance_enrichment.py`]:** `GET /freelance-jobs/{job_id}`

```sql
CREATE TABLE IF NOT EXISTS corp_freelance_jobs (
    job_id          TEXT PRIMARY KEY,
    status          TEXT,
    details_json    TEXT,
    fetched_at      TIMESTAMP DEFAULT now()
);
```

#### CORP `corp_industry_jobs`

`GET /corporations/{corporation_id}/industry/jobs`

```sql
CREATE TABLE IF NOT EXISTS corp_industry_jobs (
    job_id                  INTEGER PRIMARY KEY,
    installer_id            BIGINT,
    facility_id             BIGINT,
    station_id              BIGINT,
    blueprint_id            BIGINT,
    blueprint_type_id       INTEGER,
    blueprint_location_id   BIGINT,
    output_location_id      BIGINT,
    runs                    INTEGER,
    activity_id             INTEGER,
    status                  TEXT,
    start_date              TIMESTAMP,
    end_date                TIMESTAMP,
    pause_date              TIMESTAMP,
    completed_date          TIMESTAMP,
    completed_character_id  BIGINT,
    cost                    DOUBLE,
    licensed_runs           INTEGER,
    probability             REAL,
    product_type_id         INTEGER,
    duration                INTEGER,
    fetched_at              TIMESTAMP DEFAULT now()
);
```

#### CORP `corp_moon_extractions`

`GET /corporations/{corporation_id}/mining/extractions`

```sql
CREATE TABLE IF NOT EXISTS corp_moon_extractions (
    moon_id                 INTEGER NOT NULL,
    structure_id            BIGINT NOT NULL,
    extraction_start_time   TIMESTAMP,
    chunk_arrival_time      TIMESTAMP,
    natural_decay_time      TIMESTAMP,
    fetched_at              TIMESTAMP DEFAULT now(),
    PRIMARY KEY (moon_id, structure_id)
);
```

#### CORP `corp_mining_observers`

`GET /corporations/{corporation_id}/mining/observers`  
**Enrichment [inline]:** `GET /corporations/{corporation_id}/mining/observers/{observer_id}` — paginated

```sql
CREATE TABLE IF NOT EXISTS corp_mining_observers (
    observer_id     BIGINT PRIMARY KEY,
    observer_type   TEXT,
    last_updated    TIMESTAMP,
    fetched_at      TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS corp_mining_ledger (
    observer_id             BIGINT NOT NULL,
    character_id            BIGINT NOT NULL,
    recorded_corporation_id BIGINT,
    type_id                 INTEGER NOT NULL,
    quantity                BIGINT NOT NULL,
    last_updated            TIMESTAMP,
    fetched_at              TIMESTAMP DEFAULT now(),
    PRIMARY KEY (observer_id, character_id, type_id)
);
```

#### CORP `corp_killmails`

`GET /corporations/{corporation_id}/killmails/recent` — paginated
**Enrichment [analysis — `analysis/killmail_enrichment.py`]:** `GET /killmails/{killmail_id}/{killmail_hash}` — public endpoint, resolves
full killmail detail from hash+id pair. High-volume enrichment — opt-in.

```sql
CREATE TABLE IF NOT EXISTS corp_killmails (
    killmail_id     BIGINT PRIMARY KEY,
    killmail_hash   TEXT NOT NULL,
    -- enrichment from public /killmails/{killmail_id}/{killmail_hash}
    details_json    TEXT,
    fetched_at      TIMESTAMP DEFAULT now()
);
```

#### CORP `corp_market_orders` / `corp_market_history`

`GET /corporations/{corporation_id}/orders`  
`GET /corporations/{corporation_id}/orders/history` — paginated

```sql
CREATE TABLE IF NOT EXISTS corp_market_orders (
    order_id        BIGINT PRIMARY KEY,
    type_id         INTEGER NOT NULL,
    location_id     BIGINT NOT NULL,
    region_id       INTEGER,
    volume_total    INTEGER,
    volume_remain   INTEGER,
    min_volume      INTEGER DEFAULT 1,
    price           DOUBLE NOT NULL,
    is_buy_order    BOOLEAN DEFAULT FALSE,
    issued          TIMESTAMP,
    issued_by       BIGINT,
    duration        INTEGER,
    order_range     TEXT,
    escrow          DOUBLE,
    wallet_division INTEGER,
    fetched_at      TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS corp_market_history (
    order_id        BIGINT PRIMARY KEY,
    type_id         INTEGER NOT NULL,
    location_id     BIGINT,
    region_id       INTEGER,
    price           DOUBLE,
    volume_total    INTEGER,
    volume_remain   INTEGER,
    issued          TIMESTAMP,
    state           TEXT,
    is_buy_order    BOOLEAN DEFAULT FALSE,
    escrow          DOUBLE,
    wallet_division INTEGER,
    fetched_at      TIMESTAMP DEFAULT now()
);
```

#### CORP `corp_wallets` / `corp_wallet_journals` / `corp_wallet_transactions`

`GET /corporations/{corporation_id}/wallets`  
`GET /corporations/{corporation_id}/wallets/{division}/journal` — paginated  
`GET /corporations/{corporation_id}/wallets/{division}/transactions` — paginated

```sql
CREATE TABLE IF NOT EXISTS corp_wallets (
    division    INTEGER PRIMARY KEY,
    balance     DOUBLE NOT NULL,
    fetched_at  TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS corp_wallet_journals (
    id              BIGINT NOT NULL,
    division        INTEGER NOT NULL,
    date            TIMESTAMP NOT NULL,
    ref_type        TEXT,
    first_party_id  BIGINT,
    second_party_id BIGINT,
    amount          DOUBLE,
    balance         DOUBLE,
    reason          TEXT,
    context_id      BIGINT,
    context_id_type TEXT,
    description     TEXT,
    tax             DOUBLE,
    tax_receiver_id BIGINT,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (id, division)
);

CREATE TABLE IF NOT EXISTS corp_wallet_transactions (
    transaction_id  BIGINT NOT NULL,
    division        INTEGER NOT NULL,
    date            TIMESTAMP NOT NULL,
    type_id         INTEGER NOT NULL,
    location_id     BIGINT NOT NULL,
    unit_price      DOUBLE NOT NULL,
    quantity        INTEGER NOT NULL,
    client_id       BIGINT NOT NULL,
    is_buy          BOOLEAN DEFAULT FALSE,
    journal_ref_id  BIGINT,
    fetched_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (transaction_id, division)
);
```

#### CORP `corp_customs_offices`

`GET /corporations/{corporation_id}/customs_offices`

```sql
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
);
```

#### CORP `corp_fw_stats`

`GET /corporations/{corporation_id}/fw/stats`

```sql
CREATE TABLE IF NOT EXISTS corp_fw_stats (
    id                          INTEGER DEFAULT 1 PRIMARY KEY,
    current_rank                INTEGER,
    highest_rank                INTEGER,
    enlisted_on                 TIMESTAMP,
    faction_id                  INTEGER,
    kills_last_week             INTEGER DEFAULT 0,
    kills_total                 INTEGER DEFAULT 0,
    kills_yesterday             INTEGER DEFAULT 0,
    victory_points_last_week    INTEGER DEFAULT 0,
    victory_points_total        INTEGER DEFAULT 0,
    victory_points_yesterday    INTEGER DEFAULT 0,
    fetched_at                  TIMESTAMP DEFAULT now()
);
```

#### CORP `corp_container_logs`

`GET /corporations/{corporation_id}/containers/logs` — paginated

```sql
CREATE TABLE IF NOT EXISTS corp_container_logs (
    log_time            TIMESTAMP NOT NULL,
    container_id        BIGINT NOT NULL,
    character_id        BIGINT NOT NULL,
    action              TEXT NOT NULL,
    container_type_id   INTEGER,
    location_flag       TEXT,
    location_id         BIGINT,
    new_config_bitmask  INTEGER,
    old_config_bitmask  INTEGER,
    password_type       TEXT,
    quantity            INTEGER,
    type_id             INTEGER,
    fetched_at          TIMESTAMP DEFAULT now(),
    PRIMARY KEY (log_time, container_id, character_id)
);
```

---

### 4.4 ALLIANCE DuckDB — `_privateData/<alliance_id>/<alliance_id>.duckdb`

#### ALLIANCE `alliance_contacts`

`GET /alliances/{alliance_id}/contacts` — paginated  
**Enrichment [inline]:** `GET /alliances/{alliance_id}/contacts/labels`

```sql
CREATE TABLE IF NOT EXISTS alliance_contacts (
    contact_id      BIGINT PRIMARY KEY,
    contact_type    TEXT,
    standing        REAL NOT NULL,
    label_ids       BIGINT[],
    fetched_at      TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alliance_contact_labels (
    label_id    BIGINT PRIMARY KEY,
    label_name  TEXT,
    fetched_at  TIMESTAMP DEFAULT now()
);
```

---

## 5. Implementation Phases

| Phase | Work | New Jobs | New Tables | Effort |
|-------|------|----------|------------|--------|
| **0** — Infrastructure | Create `core/db/entity_db.py`; migrate existing character tables to DuckDB + character_id | 0 | 0 (migration) | Medium |
| **1** — Wire WIP character collectors | Split collectors.py; create extended.py; wire 1 job | 1 | 15 (personal DuckDB) | Low |
| **2** — New personal collectors | Code ~17 new character collectors | 2 | ~17 (personal DuckDB) | Medium |
| **3** — Corporation collectors | New `collectors/corp/` package; ~12 domain modules | ~10 | ~30 (corp DuckDB) | **High** |
| **4** — Alliance collectors | New `collectors/alliance/` package | 1 | 2 (alliance DuckDB) | Low |
| **5** — Public data collectors | New `collectors/public_data/` package; ~9 modules (incl. migrating `market/`, `structures/` → `public_data/`); update 3 live job import paths | ~6 | ~20 (public DuckDB) | Medium |
| **6** — market_history scheduling | Add `fetch_active_market_history` to `public_data/market.py`; register 1 job (starts disabled) | 1 | 0 | Low |
| **7** — Analysis enrichment | Create `analysis/` package; 9 analysis modules | 9 | 0 (enriches existing) | Medium |
| **Total** | | **~30** new jobs | **~85** new tables | |

---

## 6. Collector Package Layout

```
collectors/
  character/
    __init__.py          # re-exports: populate_all, run_extended_refresh
    populate.py          # MIGRATE — core data to DuckDB + character_id
    comms.py             # mail, mail_labels, mail_lists, notifications, events, contacts
    finance.py           # contracts, market_orders, market_history, wallet_journal, wallet_txn, loyalty
    industry.py          # industry_jobs, mining, blueprints, colonies
    social.py            # standings, fittings, medals, titles, corporation_history, fw_stats
    combat.py            # killmails, fatigue, freelance_jobs
    identity.py          # characters (enriched), clones, agent_research, projects
    skillqueue.py        # skill queue (separate job)
    presence.py          # location, online, ship (optional)
    extended.py          # run_extended_refresh() orchestrator
    collectors.py        # DELETE after split

  corp/
    __init__.py          # get_corp_token_map() + re-exports
    stats.py             # corp_stats, corp_alliance_history
    assets.py            # corp_assets, corp_blueprints
    contacts.py          # corp_contacts, corp_contact_labels, corp_standings
    contracts.py         # corp_contracts
    infrastructure.py    # corp_facilities, corp_starbases, corp_structures, corp_customs_offices
    industry.py          # corp_industry_jobs, corp_moon_extractions, corp_mining_observers, corp_mining_ledger
    members.py           # corp_members, corp_shareholders
    market.py            # corp_market_orders, corp_market_history
    org.py               # corp_divisions, corp_medals, corp_issued_medals, corp_titles, corp_projects
    wallet.py            # corp_wallets, corp_wallet_journals, corp_wallet_transactions, corp_killmails
    misc.py              # corp_fw_stats, corp_freelance_jobs, corp_container_logs

  alliance/
    __init__.py          # get_alliance_token_map() + re-exports
    contacts.py          # alliance_contacts, alliance_contact_labels

  public_data/
    __init__.py          # re-exports
    alliances.py         # alliances (list only — enrichment in analysis/), corporations (enrichment-only via analysis/)
    contracts.py         # public_contracts (per region + bids/items)
    industry.py          # industry_facilities, industry_cost_indices
    loyalty.py           # loyalty_offers
    market.py            # market_prices, market_items, region_orders (market_orders), structure_orders (market_structures), market_history, history_batch — REPLACES collectors/market/
    structures.py        # structures discovery + enrichment — REPLACES collectors/structures/
    fw.py                # fw_stats, fw_systems, fw_wars, fw_leaderboards
    sovereignty.py       # sovereignty_campaigns, sovereignty_map, sovereignty_structures
    universe_extras.py   # incursions, wars, server_status, freelance_jobs, insurance_prices

analysis/
  __init__.py              # re-exports
  affiliation_sync.py      # POST /characters/affiliation batch across all owner DBs
  asset_enrichment.py      # POST .../assets/locations + /assets/names (personal + corp)
  killmail_enrichment.py   # GET /killmails/{id}/{hash} for personal + corp
  alliance_enrichment.py   # GET /alliances/{id} + /corporations for discovered IDs
  corporation_discovery.py # cross-DB corp ID aggregation + GET /corporations/{id}
  public_contract_enrichment.py  # bids + items for public contracts
  war_enrichment.py        # GET /wars/{id} + /wars/{id}/killmails
  freelance_enrichment.py  # shared /freelance-jobs/{job_id} detail
  market_browser.py        # universe-wide market orchestration
```

---

## 7. Corp-Owner & Alliance-Owner Discovery

Corp and alliance collectors need to find which authenticated owners belong to each entity.

**Pre-requisite:** `auth_users` must have `corporation_id` and `alliance_id` columns, populated
during SSO callback and refreshed by `character_refresh`.

```python
# collectors/corp/__init__.py
def get_corp_token_map() -> dict[int, tuple[int, str]]:
    """Returns {corporation_id: (character_id, access_token)} for every corp."""
    con = db.connect()
    try:
        rows = con.execute("""
            SELECT DISTINCT corporation_id, owner_id
            FROM auth_users WHERE corporation_id IS NOT NULL
        """).fetchall()
    finally:
        con.close()
    result = {}
    for corp_id, owner_id in rows:
        if corp_id in result:
            continue
        try:
            char_id, token_data = pick_token(owner_id)
            char_id, fresh_data = fresh_token(owner_id, char_id, token_data)
            result[corp_id] = (char_id, fresh_data["access_token"])
        except Exception:
            logger.warning("Could not get token for corp=%s", corp_id)
    return result
```

Same pattern for `get_alliance_token_map()` in `collectors/alliance/__init__.py`, querying
`alliance_id` instead.

---

## 8. Scheduler Jobs — Complete `_build_catalog()` Additions

```python
# --- Phase 1: Character Extended ---
try:
    from collectors.character.extended import run_extended_refresh
    jobs.append({"job_id": "character_extended_refresh", "label": "Character Extended Data Refresh",
                 "fn": run_extended_refresh, "fn_path": _path(run_extended_refresh), "interval_s": 3600})
except Exception:
    logger.warning("[SchedulerJobs] Could not import character extended — skipping")

# --- Phase 2: Skill Queue ---
try:
    from collectors.character.skillqueue import run_skillqueue_refresh
    jobs.append({"job_id": "character_skillqueue_refresh", "label": "Character Skill Queue Refresh",
                 "fn": run_skillqueue_refresh, "fn_path": _path(run_skillqueue_refresh), "interval_s": 1800})
except Exception:
    logger.warning("[SchedulerJobs] Could not import skillqueue — skipping")

# --- Phase 2: Character Presence (starts DISABLED) ---
try:
    from collectors.character.presence import run_presence_refresh
    jobs.append({"job_id": "character_presence_refresh", "label": "Character Presence Refresh",
                 "fn": run_presence_refresh, "fn_path": _path(run_presence_refresh), "interval_s": 300})
except Exception:
    logger.warning("[SchedulerJobs] Could not import presence — skipping")

# --- Phase 3: Corporation ---
try:
    from collectors.corp.assets import fetch_corp_assets
    jobs.append({"job_id": "corp_assets_refresh", "label": "Corp Assets & Blueprints",
                 "fn": fetch_corp_assets, "fn_path": _path(fetch_corp_assets), "interval_s": 43200})
except Exception:
    logger.warning("[SchedulerJobs] Could not import corp assets — skipping")

try:
    from collectors.corp.contacts import fetch_corp_contacts
    jobs.append({"job_id": "corp_contacts_refresh", "label": "Corp Contacts & Standings",
                 "fn": fetch_corp_contacts, "fn_path": _path(fetch_corp_contacts), "interval_s": 43200})
except Exception:
    logger.warning("[SchedulerJobs] Could not import corp contacts — skipping")

try:
    from collectors.corp.contracts import fetch_corp_contracts
    jobs.append({"job_id": "corp_contracts_refresh", "label": "Corp Contracts",
                 "fn": fetch_corp_contracts, "fn_path": _path(fetch_corp_contracts), "interval_s": 14400})
except Exception:
    logger.warning("[SchedulerJobs] Could not import corp contracts — skipping")

try:
    from collectors.corp.industry import fetch_corp_industry
    jobs.append({"job_id": "corp_industry_refresh", "label": "Corp Industry & Mining",
                 "fn": fetch_corp_industry, "fn_path": _path(fetch_corp_industry), "interval_s": 1800})
except Exception:
    logger.warning("[SchedulerJobs] Could not import corp industry — skipping")

try:
    from collectors.corp.members import fetch_corp_members
    jobs.append({"job_id": "corp_members_refresh", "label": "Corp Members",
                 "fn": fetch_corp_members, "fn_path": _path(fetch_corp_members), "interval_s": 3600})
except Exception:
    logger.warning("[SchedulerJobs] Could not import corp members — skipping")

try:
    from collectors.corp.market import fetch_corp_orders
    jobs.append({"job_id": "corp_market_refresh", "label": "Corp Market Orders",
                 "fn": fetch_corp_orders, "fn_path": _path(fetch_corp_orders), "interval_s": 3600})
except Exception:
    logger.warning("[SchedulerJobs] Could not import corp market — skipping")

try:
    from collectors.corp.infrastructure import fetch_corp_infrastructure
    jobs.append({"job_id": "corp_infrastructure_refresh", "label": "Corp Infrastructure",
                 "fn": fetch_corp_infrastructure, "fn_path": _path(fetch_corp_infrastructure), "interval_s": 21600})
except Exception:
    logger.warning("[SchedulerJobs] Could not import corp infrastructure — skipping")

try:
    from collectors.corp.wallet import fetch_corp_wallet
    jobs.append({"job_id": "corp_wallet_refresh", "label": "Corp Wallet",
                 "fn": fetch_corp_wallet, "fn_path": _path(fetch_corp_wallet), "interval_s": 1800})
except Exception:
    logger.warning("[SchedulerJobs] Could not import corp wallet — skipping")

try:
    from collectors.corp.org import fetch_corp_org
    jobs.append({"job_id": "corp_org_refresh", "label": "Corp Org Data",
                 "fn": fetch_corp_org, "fn_path": _path(fetch_corp_org), "interval_s": 86400})
except Exception:
    logger.warning("[SchedulerJobs] Could not import corp org — skipping")

try:
    from collectors.corp.misc import fetch_corp_misc
    jobs.append({"job_id": "corp_misc_refresh", "label": "Corp Misc Data",
                 "fn": fetch_corp_misc, "fn_path": _path(fetch_corp_misc), "interval_s": 14400})
except Exception:
    logger.warning("[SchedulerJobs] Could not import corp misc — skipping")

try:
    from collectors.corp.stats import fetch_corp_stats
    jobs.append({"job_id": "corp_stats_refresh", "label": "Corp Stats & History",
                 "fn": fetch_corp_stats, "fn_path": _path(fetch_corp_stats), "interval_s": 86400})
except Exception:
    logger.warning("[SchedulerJobs] Could not import corp stats — skipping")

# --- Phase 4: Alliance ---
try:
    from collectors.alliance.contacts import fetch_alliance_contacts
    jobs.append({"job_id": "alliance_contacts_refresh", "label": "Alliance Contacts",
                 "fn": fetch_alliance_contacts, "fn_path": _path(fetch_alliance_contacts), "interval_s": 43200})
except Exception:
    logger.warning("[SchedulerJobs] Could not import alliance contacts — skipping")

# --- Phase 5: Public Data ---
try:
    from collectors.public_data.alliances import fetch_alliances
    jobs.append({"job_id": "alliances_refresh", "label": "Alliance Data",
                 "fn": fetch_alliances, "fn_path": _path(fetch_alliances), "interval_s": 86400})
except Exception:
    logger.warning("[SchedulerJobs] Could not import alliances — skipping")

try:
    from collectors.public_data.fw import fetch_fw_data
    jobs.append({"job_id": "fw_refresh", "label": "Faction Warfare Data",
                 "fn": fetch_fw_data, "fn_path": _path(fetch_fw_data), "interval_s": 3600})
except Exception:
    logger.warning("[SchedulerJobs] Could not import FW — skipping")

try:
    from collectors.public_data.sovereignty import fetch_sovereignty
    jobs.append({"job_id": "sovereignty_refresh", "label": "Sovereignty Data",
                 "fn": fetch_sovereignty, "fn_path": _path(fetch_sovereignty), "interval_s": 1800})
except Exception:
    logger.warning("[SchedulerJobs] Could not import sovereignty — skipping")

try:
    from collectors.public_data.universe_extras import fetch_universe_extras
    jobs.append({"job_id": "universe_extras_refresh", "label": "Universe Extras",
                 "fn": fetch_universe_extras, "fn_path": _path(fetch_universe_extras), "interval_s": 3600})
except Exception:
    logger.warning("[SchedulerJobs] Could not import universe extras — skipping")

try:
    from collectors.public_data.industry import fetch_industry_data
    jobs.append({"job_id": "industry_data_refresh", "label": "Industry Facilities & Costs",
                 "fn": fetch_industry_data, "fn_path": _path(fetch_industry_data), "interval_s": 3600})
except Exception:
    logger.warning("[SchedulerJobs] Could not import industry data — skipping")

try:
    from collectors.public_data.market import fetch_market_meta
    jobs.append({"job_id": "market_meta_refresh", "label": "Market Prices & Items",
                 "fn": fetch_market_meta, "fn_path": _path(fetch_market_meta), "interval_s": 3600})
except Exception:
    logger.warning("[SchedulerJobs] Could not import market meta — skipping")

# Phase 5 also requires updating the import paths for the 3 existing live jobs:
# UPDATE "market_refresh"          → fn: collectors.public_data.market.fetch_region_orders
# UPDATE "structure_market_refresh" → fn: collectors.public_data.market.fetch_structure_orders
# UPDATE "structure_discovery"      → fn: collectors.public_data.structures.discover_structures
# (job_ids and intervals stay the same; only fn + fn_path change)

# --- Phase 6: Market History Batch (starts DISABLED) ---
try:
    from collectors.public_data.market import fetch_active_market_history
    jobs.append({"job_id": "market_history_refresh", "label": "Market History Batch",
                 "fn": fetch_active_market_history, "fn_path": _path(fetch_active_market_history), "interval_s": 86400})
except Exception:
    logger.warning("[SchedulerJobs] Could not import market history batch — skipping")

# --- Phase 7: Analysis Enrichment (all start DISABLED) ---
try:
    from analysis.affiliation_sync import run_affiliation_sync
    jobs.append({"job_id": "affiliation_sync", "label": "Character Affiliation Sync",
                 "fn": run_affiliation_sync, "fn_path": _path(run_affiliation_sync), "interval_s": 3600})
except Exception:
    logger.warning("[SchedulerJobs] Could not import affiliation_sync — skipping")

try:
    from analysis.asset_enrichment import run_asset_enrichment
    jobs.append({"job_id": "asset_enrichment", "label": "Asset Name & Position Enrichment",
                 "fn": run_asset_enrichment, "fn_path": _path(run_asset_enrichment), "interval_s": 43200})
except Exception:
    logger.warning("[SchedulerJobs] Could not import asset_enrichment — skipping")

try:
    from analysis.killmail_enrichment import run_killmail_enrichment
    jobs.append({"job_id": "killmail_enrichment", "label": "Killmail Detail Enrichment",
                 "fn": run_killmail_enrichment, "fn_path": _path(run_killmail_enrichment), "interval_s": 86400})
except Exception:
    logger.warning("[SchedulerJobs] Could not import killmail_enrichment — skipping")

try:
    from analysis.alliance_enrichment import run_alliance_enrichment
    jobs.append({"job_id": "alliance_enrichment", "label": "Alliance Detail Enrichment",
                 "fn": run_alliance_enrichment, "fn_path": _path(run_alliance_enrichment), "interval_s": 86400})
except Exception:
    logger.warning("[SchedulerJobs] Could not import alliance_enrichment — skipping")

try:
    from analysis.corporation_discovery import run_corporation_discovery
    jobs.append({"job_id": "corporation_discovery", "label": "Corporation Discovery & Enrichment",
                 "fn": run_corporation_discovery, "fn_path": _path(run_corporation_discovery), "interval_s": 86400})
except Exception:
    logger.warning("[SchedulerJobs] Could not import corporation_discovery — skipping")

try:
    from analysis.public_contract_enrichment import run_public_contract_enrichment
    jobs.append({"job_id": "public_contract_enrichment", "label": "Public Contract Items & Bids",
                 "fn": run_public_contract_enrichment, "fn_path": _path(run_public_contract_enrichment), "interval_s": 14400})
except Exception:
    logger.warning("[SchedulerJobs] Could not import public_contract_enrichment — skipping")

try:
    from analysis.war_enrichment import run_war_enrichment
    jobs.append({"job_id": "war_enrichment", "label": "War Detail & Killmail Enrichment",
                 "fn": run_war_enrichment, "fn_path": _path(run_war_enrichment), "interval_s": 86400})
except Exception:
    logger.warning("[SchedulerJobs] Could not import war_enrichment — skipping")

try:
    from analysis.freelance_enrichment import run_freelance_enrichment
    jobs.append({"job_id": "freelance_enrichment", "label": "Freelance Job Detail Enrichment",
                 "fn": run_freelance_enrichment, "fn_path": _path(run_freelance_enrichment), "interval_s": 14400})
except Exception:
    logger.warning("[SchedulerJobs] Could not import freelance_enrichment — skipping")

try:
    from analysis.market_browser import run_market_browser
    jobs.append({"job_id": "market_browser_refresh", "label": "Universe Market Browser",
                 "fn": run_market_browser, "fn_path": _path(run_market_browser), "interval_s": 3600})
except Exception:
    logger.warning("[SchedulerJobs] Could not import market_browser — skipping")
```

**Total new jobs: 30** (3 personal + 11 corp + 1 alliance + 6 public + 9 analysis)

---

## 9. Pre-requisites

| Requirement | Phase | Notes |
|-------------|-------|-------|
| `core/db/entity_db.py` created | 0 | DuckDB connection manager for per-entity DBs. Provides `connect_entity(id)`, analogous to `core.db.public.connect()` for per-entity files. |
| Existing character SQLite tables migrated to DuckDB | 0 | `character_skills`, `character_wallet`, `character_assets` → owner DuckDB with `character_id` column |
| `auth_users.corporation_id` column | 3 | `ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS corporation_id BIGINT` |
| `auth_users.alliance_id` column | 4 | `ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS alliance_id BIGINT` |
| `collectors/character/collectors.py` split | 1 | Must precede scheduler wiring |
| `collectors/character/extended.py` created | 1 | Entry point for `character_extended_refresh` job |
| `market_orders` table populated | 5 | `market_history_refresh` depends on existing market data; populated by `fetch_region_orders` in `collectors/public_data/market.py` |
| Phases 1–6 collectors wired | 7 | Analysis modules read from tables created by collectors; all target tables must exist |
| `analysis/` registered in `applications/_api.py` | 7 | Applications import analysis functions via `_api.py` |

---

## 10. Verification Checklist

### Phase 0 — Infrastructure
- [ ] `core/db/entity_db.py` provides `connect_entity()` returning fresh DuckDB connections
- [ ] Existing `character_skills`, `character_wallet`, `character_assets` migrated to `<owner_id>.duckdb` with `character_id` column
- [ ] Auth token storage in SQLite remains functional (no regressions)

### Phase 1 — Wire WIP
- [ ] `collectors/character/collectors.py` is deleted (or import-warning stub)
- [ ] Each sub-module has its own `SCOPE_COLLECTORS` list
- [ ] `character_extended_refresh` job appears in scheduler UI
- [ ] Run job manually; confirm all 15 WIP collectors execute for at least one owner
- [ ] Tables created in `_privateData/<owner_id>/<owner_id>.duckdb`

### Phase 2 — New Personal
- [ ] New character tables appear in DB Viewer
- [ ] `character_skillqueue_refresh` fires at 30 min intervals
- [ ] `character_presence_refresh` starts **disabled**
- [ ] `characters` table populated with enrichment (affiliation, attributes, wallet, location, etc.)

### Phase 3 — Corporation
- [ ] `auth_users.corporation_id` populated after `character_refresh` runs
- [ ] `_privateData/<corporation_id>/` directories created on first corp collector run
- [ ] All ~11 corp jobs appear in scheduler UI
- [ ] Corp DuckDB files appear in DB Viewer private database list

### Phase 4 — Alliance
- [ ] `auth_users.alliance_id` populated
- [ ] `alliance_contacts_refresh` job appears in scheduler
- [ ] `_privateData/<alliance_id>/<alliance_id>.duckdb` created

### Phase 5 — Public
- [ ] All ~6 public jobs appear in scheduler
- [ ] Public tables (`alliances`, `fw_stats`, `sovereignty_map`, etc.) populated
- [ ] `corporations` table created (populated by `analysis/corporation_discovery.py` in Phase 7)

### Phase 6 — Market History
- [ ] `market_history_refresh` appears in scheduler, starts **disabled**
- [ ] Enable manually; confirm history rows added
- [ ] ETag caching produces 304s on second run

### Phase 7 — Analysis Enrichment
- [ ] All 9 analysis jobs appear in scheduler UI, all start **disabled**
- [ ] `affiliation_sync` reads character IDs from all owner DBs, batches POST, writes back
- [ ] `asset_enrichment` populates name/position columns on `character_assets` and `corp_assets`
- [ ] `killmail_enrichment` populates `details_json` on `character_killmails` and `corp_killmails`
- [ ] `alliance_enrichment` populates `alliances` table in public DB from discovered IDs
- [ ] `corporation_discovery` populates `corporations` table in public DB from cross-DB aggregation
- [ ] `public_contract_enrichment` populates `items_json`/`bids_json` on `public_contracts`
- [ ] `war_enrichment` populates detail columns + `killmails_json` on `wars`
- [ ] `freelance_enrichment` populates `details_json` across all three freelance tables
- [ ] `market_browser` orchestrates region-wide market collection
- [ ] No analysis module creates tables — all use `ALTER TABLE ADD COLUMN IF NOT EXISTS` or write to existing columns

---

## 11. File Manifest

```
core/
  db/
    entity_db.py         # NEW — DuckDB connection manager for per-entity databases
    public.py            # UPDATE — add corporation_id, alliance_id to auth_users

collectors/
  character/
    __init__.py          # UPDATE — add run_extended_refresh export
    populate.py          # MIGRATE — DuckDB + character_id
    comms.py             # NEW
    finance.py           # NEW
    industry.py          # NEW
    social.py            # NEW
    combat.py            # NEW
    identity.py          # NEW
    skillqueue.py        # NEW
    presence.py          # NEW
    extended.py          # NEW
    collectors.py        # DELETE after migration

  corp/
    __init__.py          # NEW — get_corp_token_map()
    stats.py             # NEW — corp_stats, corp_alliance_history
    assets.py            # NEW — corp_assets, corp_blueprints
    contacts.py          # NEW — corp_contacts, corp_contact_labels, corp_standings
    contracts.py         # NEW — corp_contracts
    infrastructure.py    # NEW — corp_facilities, corp_starbases, corp_structures, corp_customs_offices
    industry.py          # NEW — corp_industry_jobs, corp_moon_extractions, corp_mining_*
    members.py           # NEW — corp_members, corp_shareholders
    market.py            # NEW — corp_market_orders, corp_market_history
    org.py               # NEW — corp_divisions, corp_medals, corp_issued_medals, corp_titles, corp_projects
    wallet.py            # NEW — corp_wallets, corp_wallet_journals, corp_wallet_transactions, corp_killmails
    misc.py              # NEW — corp_fw_stats, corp_freelance_jobs, corp_container_logs

  alliance/
    __init__.py          # NEW — get_alliance_token_map()
    contacts.py          # NEW — alliance_contacts, alliance_contact_labels

  public_data/
    __init__.py          # NEW
    alliances.py         # NEW — alliances, corporations
    contracts.py         # NEW — public_contracts
    industry.py          # NEW — industry_facilities, industry_cost_indices
    loyalty.py           # NEW — loyalty_offers
    market.py            # REPLACES collectors/market/ — market_prices, market_items, region_orders (market_orders), structure_orders (market_structures), market_history, history_batch
    structures.py        # REPLACES collectors/structures/ — structures discovery + enrichment
    fw.py                # NEW — fw_stats, fw_systems, fw_wars, fw_leaderboards
    sovereignty.py       # NEW — sovereignty_campaigns, sovereignty_map, sovereignty_structures
    universe_extras.py   # NEW — incursions, wars, server_status, freelance_jobs, insurance_prices

  market/
    history_batch.py     # DELETE — merged into public_data/market.py

core/
  tasks/
    jobs.py              # UPDATE — add ~30 new job entries

analysis/
  __init__.py              # NEW
  affiliation_sync.py      # NEW — POST /characters/affiliation batch
  asset_enrichment.py      # NEW — asset name/position enrichment (personal + corp)
  killmail_enrichment.py   # NEW — killmail detail enrichment (personal + corp)
  alliance_enrichment.py   # NEW — alliance detail + member corp enrichment
  corporation_discovery.py # NEW — cross-DB corp ID discovery + enrichment
  public_contract_enrichment.py  # NEW — public contract items/bids
  war_enrichment.py        # NEW — war detail + killmail enrichment
  freelance_enrichment.py  # NEW — shared freelance job detail enrichment
  market_browser.py        # NEW — universe-wide market orchestration
```

**Total new files:** 39 *(includes `public_data/structures.py`; `market/history_batch.py` folded into `public_data/market.py` — net unchanged)*  
**Deleted packages:** `collectors/market/` (regions.py, structures.py, history.py), `collectors/structures/` (discover.py) — absorbed by `collectors/public_data/`  
**Updated files:** 4  
**New public DuckDB tables:** ~20 (added `insurance_prices`)  
**New personal DuckDB tables per owner:** ~32 (15 WIP wired + 17 new)  
**New corp DuckDB tables per corporation:** ~30  
**New alliance DuckDB tables per alliance:** 2  
**New scheduler jobs:** ~30 (21 collector + 9 analysis)  
**New enrichment columns (not new tables):** asset name/position (personal + corp), killmail details (personal + corp), freelance participation (personal), corp project contributors, corp member roles history  
**Analysis modules (enrich existing tables, own no DDL):** 9
