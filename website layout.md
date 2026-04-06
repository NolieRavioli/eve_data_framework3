# EVE Data Framework — Target Web Endpoint Reference

> **This is a design document.** It describes the *eventual* URL surface of the framework — not the current implementation. Routes marked `[TBD]` are planned but not yet built. Nothing in this document implies an implementation schedule.

---

## Conventions

### Auth Level Notation

| Tag | Meaning |
|-----|---------|
| `[public]` | No authentication required |
| `[user]` | Any authenticated user |
| `[role:X]` | Authenticated + holds named role `X` |
| `[admin]` | Site admin or site owner |
| `[site_owner]` | Site owner only (unconditional) |

Admins bypass all named-role checks. The site owner bypasses everything.

### WebSocket Notation

WebSocket endpoints are prefixed with **`WS`** and list their bus topic subscriptions in parentheses, e.g.:

```
WS /esi/ws   [role:queue]   (topics: esi/rate [owner-filtered], queue/tasks [owner-filtered])
```

### Status Tags

- `[TBD]` — planned route, not yet implemented
- *(no tag)* — exists or is the clear next implementation target

---

## Part 1 — Core Framework

> Routes that are part of the framework itself. Not auto-discovered application plugins.

---

### `/` — Home

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/` | `[public]` | Unauthenticated landing page. Shows login prompt, framework name/version, and EVE server status card. |

---

### `/setup` — First-Run Wizard

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/setup` | `[public]` | First-run setup wizard. Shown when no `client_id`/`client_secret` are configured. Entry fields for EVE developer application credentials. |
| POST | `/setup` | `[public]` | Save credentials (Fernet-encrypted to `_publicData/client_cred`). Redirect to `/setup/owner` on success. |
| GET | `/setup/owner` | `[public]` | Owner-selection step. Prompt to log in with the first character to designate the site owner. |

---

### `/auth/` — Authentication

> Implements the EVE Online OAuth 2.0 Authorization Code flow. Will live in `core/auth/`.

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/auth/login` | `[public]` | Redirect to CCP's EVE SSO with a CSRF `state` token. |
| GET | `/auth/callback` | `[public]` | OAuth2 callback: validate `state`, exchange code for tokens, persist encrypted tokens, create session. |
| GET | `/auth/logout` | `[user]` | Clear session. Redirect to `/`. |
| GET | `/auth/add_toon` | `[user]` | Begin SSO flow to link an additional character to the current owner account. |
| GET | `/auth/switch_character/<int:character_id>` | `[user]` | Change which character is the active character for the current session. |

---

### `/bus` — Event Bus WebSocket

| Type | Route | Auth | Topics | Description |
|------|-------|------|--------|-------------|
| WS | `/bus` | `[user]`, topic-gated | any subscribed | Raw multiplexed event bus. Client sends `{"action":"subscribe","topics":["topic/name"]}`. Access to each topic is checked against its registered `access_level` and `required_role`. Supports `subscribe`, `unsubscribe`, `history` actions. |

---

## Part 2 — Default Applications

> Shipped with the framework. Auto-discovered via `applications/` plugin system.

---

### `/dashboard` — Account Overview

**Access:** `[role:dashboard]`

The primary view for authenticated users. Shows a unified overview of all characters linked to the current owner account.

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/dashboard/` | `[role:dashboard]` | Overview: all linked characters with portraits, corp/alliance, net worth summary, active skill training, recent activity feed, aggregate stats across all characters. |
| GET | `/dashboard/character/<int:character_id>` | `[role:dashboard]` | Character sheet: name, portrait, corporation, alliance, security status, total SP, active clone, implants, jump fatigue, last known location. |
| GET | `/dashboard/character/<int:character_id>/skills` | `[role:dashboard]` | `[TBD]` Skill queue (training name, ETA) + full trained-skills tree grouped by category. |
| GET | `/dashboard/character/<int:character_id>/wallet` | `[role:dashboard]` | `[TBD]` Wallet balance card + paginated journal + transaction history. |
| GET | `/dashboard/character/<int:character_id>/assets` | `[role:dashboard]` | `[TBD]` Asset list grouped by location (station/structure/space). Estimated ISK value using market price lookup. |
| GET | `/dashboard/character/<int:character_id>/mail` | `[role:dashboard]` | `[TBD]` EVE mail: inbox, sent, labels/folders. Message body rendering. |
| GET | `/dashboard/character/<int:character_id>/contracts` | `[role:dashboard]` | `[TBD]` Open and completed contracts (item exchange, auction, courier). |
| GET | `/dashboard/character/<int:character_id>/calendar` | `[role:dashboard]` | `[TBD]` EVE calendar events with response status. |
| GET | `/dashboard/character/<int:character_id>/contacts` | `[role:dashboard]` | `[TBD]` Contact list with standings and labels, sorted by standing. |
| GET | `/dashboard/character/<int:character_id>/notifications` | `[role:dashboard]` | `[TBD]` EVE notification feed with type-based formatting (structure attacks, war decs, etc.). |
| GET | `/dashboard/character/<int:character_id>/industry` | `[role:dashboard]` | `[TBD]` Active and completed industry jobs (manufacturing, research, copying, invention). |
| GET | `/dashboard/character/<int:character_id>/market` | `[role:dashboard]` | `[TBD]` Personal market orders (open, expired, fulfilled) + market transaction history. |
| GET | `/dashboard/character/<int:character_id>/blueprints` | `[role:dashboard]` | `[TBD]` Blueprint library: originals and copies with ME/TE levels, location. |
| GET | `/dashboard/character/<int:character_id>/pi` | `[role:dashboard]` | `[TBD]` Planetary interaction: active colonies, extractors, factories, product summary. |
| GET | `/dashboard/character/<int:character_id>/mining` | `[role:dashboard]` | `[TBD]` Mining ledger: ore types mined by day, estimated value, location. |
| GET | `/dashboard/character/<int:character_id>/loyalty` | `[role:dashboard]` | `[TBD]` Loyalty point balances per NPC corporation. |
| GET | `/dashboard/character/<int:character_id>/research` | `[role:dashboard]` | `[TBD]` Research agent slots: agent name, skill, points per day, total accumulated. |
| GET | `/dashboard/character/<int:character_id>/fittings` | `[role:dashboard]` | `[TBD]` Saved ship fittings with EFT export. |
| GET | `/dashboard/character/<int:character_id>/standings` | `[role:dashboard]` | `[TBD]` Standings with NPC factions, corps, and player entities. |
| GET | `/dashboard/character/<int:character_id>/killmails` | `[role:dashboard]` | `[TBD]` Kill and loss history with zkillboard-style summary cards. |
| WS | `/dashboard/ws` | `[role:dashboard]` | `[TBD]` (topics: TBD character data update events) Live push for skill training completion, wallet changes, notification count. |

---

### `/admin` — User Management

**Access:** `[admin]`

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/admin/` | `[admin]` | User list: all registered owners with character count, roles, admin status, last login. Links to per-user panels and other admin tools. |
| GET | `/admin/<int:owner_id>` | `[admin]` | Per-user panel: linked characters with portraits, currently held roles (with grant/revoke UI), site-admin status toggle, account creation date. |
| POST | `/admin/<int:owner_id>/roles/grant` | `[admin]` | Grant one or more named roles to an owner. Body: `{"roles": ["dashboard", "queue"]}`. |
| POST | `/admin/<int:owner_id>/roles/revoke` | `[admin]` | Revoke a single named role. Body: `{"role": "queue"}`. |
| POST | `/admin/<int:owner_id>/promote` | `[admin]` | Elevate owner to site admin. Idempotent. |
| POST | `/admin/<int:owner_id>/demote` | `[admin]` | Remove site admin status. Cannot demote site owner. |

---

### `/db` — Database Statistics & Browser

Two tiers: personal view (all users) and global admin view.

#### Personal view — `/db`

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/db/` | `[user]` | Personal DB statistics. Overview cards for each operation type (READ / INSERT / UPDATE / DELETE / UPSERT / TRUNCATE / DDL / BULK_LOAD) showing counts and weighted db-units. Per-task breakdown table: `task_id \| reads \| inserts \| updates \| deletes \| upserts \| truncates \| ddl \| bulk_loads \| db-units`. |
| WS | `/db/ws` | `[user]` | (topic: `db/stats`, filtered to current owner) Live push of the stats tables above. |

#### Admin view — `/db/admin`

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/db/admin/` | `[admin]` | Global DB statistics. Same overview cards summed across all owners. Per-owner breakdown table with the same columns. Includes a `SYSTEM` row for operations attributed to no user (SDE loads, schema migrations, scheduler maintenance). |
| WS | `/db/admin/ws` | `[admin]` | (topic: `db/stats`, global — all owners) Live push of global stats. |

#### Database browsers

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/db/public/` | `[admin]` | Public DuckDB schema browser: table list with row counts, DDL view per table, column types. |
| POST | `/db/public/query` | `[admin]` | Execute a read-only SQL query against public DuckDB. Returns paginated results as JSON or HTML table. Parameterised only — no raw interpolation. |
| GET | `/db/<int:owner_id>/` | `[admin or self]` | Private SQLite schema browser for a specific owner. Non-admins may only view their own `owner_id`. |
| POST | `/db/<int:owner_id>/query` | `[admin or self]` | Execute a read-only SQL query against an owner's private SQLite database. |

---

### `/esi` — ESI Queue & API Explorer

Two tiers: personal (role-gated) and global admin view.

#### Personal view — `/esi`

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/esi/` | `[role:queue]` | Personal ESI queue. Rate-limit cards for own characters — cards are hidden when bucket usage is zero. Active and completed task list. |
| GET | `/esi/<task_id>` | `[role:queue]` + ownership | Task progress page: name, status badge, ESI rate mini-bar, full live log stream. |
| POST | `/esi/<task_id>/cancel` | `[role:queue]` + ownership | Signal a pending task to be cancelled. |
| POST | `/esi/clear` | `[role:queue]` | Remove all completed and failed tasks owned by the current user. |
| WS | `/esi/ws` | `[role:queue]` | (topics: `esi/rate` [owner-filtered], `queue/tasks` [owner-filtered]) Live rate cards and task list updates. |
| WS | `/esi/<task_id>/ws` | `[role:queue]` + ownership | (topic: `task/<task_id>/log`) Live log stream for a single task: log lines, ESI rate snapshots, ESI request entries, terminal status. |

#### Admin view — `/esi/admin`

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/esi/admin/` | `[admin]` | Global ESI queue: rate-limit cards across all owners and characters, per-owner grouped summary, full task list across all users. |
| WS | `/esi/admin/ws` | `[admin]` | (topics: `esi/rate` [global], `queue/tasks` [all owners]) Live global queue updates. |

#### ESI Explorer — `/esi/explore`

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/esi/explore/` | `[admin]` | ESI operation browser. All operations grouped by ESI tag (Markets, Characters, Corporations, …), searchable by path/description/scope. |
| GET | `/esi/explore/<operation_id>` | `[admin]` | Operation detail: HTTP method, full path, description, query/path parameters with types, response schema, required EVE SSO scopes, example response. |
| POST | `/esi/explore/<operation_id>/run` | `[admin]` | Execute an ESI operation using the current user's access token (if the required scope is available). Returns raw JSON response + response headers (including rate-limit headers). |

---

### `/scheduler` — Background Job Management

**Access:** `[role:scheduler]` or `admin`

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/scheduler/` | `[role:scheduler]` | All registered jobs. Columns: job ID, label, interval, enabled toggle, last run timestamp, next scheduled run, last run status. |
| GET | `/scheduler/<job_id>` | `[role:scheduler]` | `[TBD]` Job detail: description, function path, full run history log with timestamps and exit status. |
| POST | `/scheduler/<job_id>/toggle` | `[role:scheduler]` | Enable or disable a job (state persisted to DuckDB `scheduler_jobs` table). |
| POST | `/scheduler/<job_id>/run-now` | `[role:scheduler]` | Enqueue an immediate run of the job outside its normal schedule. Returns `{"task_id": "..."}`. Redirect to `/esi/<task_id>` for progress. |
| POST | `/scheduler/<job_id>/interval` | `[role:scheduler]` | 

---

### `/sde` — Static Data Edition

**Access:** `[admin]`

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/sde/` | `[admin]` | SDE status card: current dataset version/date, per-table row counts (`dim_types`, `dim_groups`, `dim_categories`, `dim_regions`, `dim_constellations`, `dim_systems`, `dim_stations`, …), last loaded timestamp. Includes an ID↔name lookup tool (type, system, region). 'Update SDE' button. |
| POST | `/sde/update` | `[admin]` | Enqueue the SDE loader pipeline (download → extract → prune → load to DuckDB). Returns `{"task_id": "..."}`. Redirect to `/esi/<task_id>` for progress. |
| GET | `/sde/lookup` | `[admin]` | Search by name or numeric ID across types, systems, and regions. Query param: `?q=<search>`. Returns JSON or HTML. |
| GET | `/sde/lookup/type/<int:type_id>` | `[admin]` | Type detail: name, group, category, base price, packaged volume, mass, description. |
| GET | `/sde/lookup/system/<int:system_id>` | `[admin]` | Solar system detail: name, region, constellation, security status, star type. |
| GET | `/sde/lookup/region/<int:region_id>` | `[admin]` | Region detail: name, region ID, constellation list. |

---

### `/system` — Python Runtime

**Access:** `[admin]`

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/system/` | `[admin]` | Runtime overview: CPU usage %, RAM (RSS and VMS) in MB, thread count, per-thread identity where available. GitHub version check card: current running version (git tag/commit) vs latest release on the configured repository. 'Update System to Latest Release' button (confirmation prompt, site_owner only). Live bus log console with client-side topic filter checkboxes. |
| POST | `/system/update` | `[site_owner]` | Trigger a full automated update: git pull from the configured repository URL, dependency install, hot restart. Requires a second-factor confirmation token (randomised per page load, shown in the confirmation prompt). Streams progress to a task log. |
| WS | `/system/ws/process` | `[admin]` | (topic: `system/process`) CPU/RAM/thread metrics pushed every 10 seconds by the process publisher daemon. |

> The live bus log console on `/system/` connects directly to `WS /bus` with client-side topic filtering — no dedicated WS endpoint needed.

---

## Part 3 — Extended Applications

> Optional modules not bundled with the core framework. Auto-discovered from `applications/` if present.

---

### `/market` — Market Browser

**Access:** `[public]` (browsing) · `[role:queue]` (triggering refresh)

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/market/` | `[public]` | Landing: hub/region selector. Shows last-updated timestamp per region, total order count. |
| GET | `/market/orders` | `[public]` | Live order book. Filterable by region, type name/ID, order type (buy/sell/all). Paginated. |
| GET | `/market/search` | `[public]` | Search by item name → matching type list with current best buy/sell prices and spread. |
| GET | `/market/type/<int:type_id>` | `[public]` | `[TBD]` Price history chart + current full order book (buy wall / sell wall) for a specific type. |
| GET | `/market/tree` | `[public]` | Market category and group hierarchy browser. |
| GET | `/market/group/<int:group_id>/types` | `[public]` | All types within a market group with their current best price. |
| POST | `/market/refresh_all` | `[role:queue]` | Enqueue a full market data refresh (all configured regions + accessible structures). Returns `{"task_id": "..."}`. |

---

## Part 4 — Collectors & Analysis

> No HTTP routes. Backend processes only. Output surfaces through application routes listed above.

### Collectors

Currently all of `analysis/` is, in practice, **collectors**: modules that fetch raw ESI data and write it into DuckDB or private SQLite with minimal transformation. Examples:

- `analysis/market/regions.py` — fetches regional NPC market orders, writes `market_orders`
- `analysis/market/structures.py` — fetches player-structure orders, enriches `structures`
- `analysis/character/populate.py` — pulls skills, wallet, assets per character into private SQLite

Collectors are essentially shared background tasks — usable by any application. They could reasonably be considered `core/tasks/` material, but they are kept in `analysis/` because they are not fundamental to the *framework* (a deployment with no characters still boots and runs without them).

### Analysis (future)

True **analysis** modules are categorically different from collectors. An analysis module:
- Takes collected raw data as input
- Produces derived tables that did not exist in ESI
- May involve significant computation (graph traversal, optimisation algorithms, statistical modelling)

**Example:** A trade-route finder using A\* search with ISK/m³ optimisation would pre-compute traversal tables, route costs, and regional price matrices — data that no amount of raw ESI collection produces on its own. This warrants its own schema, its own `ensure_tables`, and likely its own application route (`/trade/`).

### Open architectural question

The current `analysis/` folder name implies analysis but contains only collectors. As the framework gains true analysis applications, the split becomes:

| Folder | Role | Imports from |
|--------|------|-------------|
| `collectors/` (future) | Pure ESI ingestion → DuckDB/SQLite | `core.*` only |
| `analysis/` (future, true) | Derived computation → domain tables | `core.*`, `collectors.*` |

This split is not yet implemented. For now, `analysis/` covers both roles.

---

## Appendix A — WebSocket / Bus Topology

| URL | Auth | Topics | Notes |
|-----|------|--------|-------|
| `WS /bus` | `[user]`, topic-gated | any subscribed | Raw multiplexed bus; per-topic access checks |
| `WS /db/ws` | `[user]` | `db/stats` (owner-filtered) | Personal DB stats live feed |
| `WS /db/admin/ws` | `[admin]` | `db/stats` (global) | All-owner DB stats |
| `WS /esi/ws` | `[role:queue]` | `esi/rate` (owner-filtered), `queue/tasks` (owner-filtered) | Personal ESI rate cards + task list |
| `WS /esi/<task_id>/ws` | `[role:queue]` + ownership | `task/<task_id>/log` | Single-task live log stream |
| `WS /esi/admin/ws` | `[admin]` | `esi/rate` (global), `queue/tasks` (all) | Global queue dashboard |
| `WS /system/ws/process` | `[admin]` | `system/process` | CPU/RAM/thread metrics (10s cadence) |
| `WS /dashboard/ws` | `[role:dashboard]` | TBD character update topics | `[TBD]` |

---

## Appendix B — DB Operation Categories & Units

DB-units are a weighted composite metric across all database operation types. Weights are configurable in `config.yaml` under the `DB Units` section.

### Benchmark results

Measured via `tests/test_db_bench.py` against real production patterns — file-backed DuckDB, live writer thread, actual `publicDB` helpers. Averaged across 3 runs. **Weight** = ms/row(op) / ms/row(Coalesce_Blocking) — batched INSERT through the writer thread is the baseline at 1.0.

`MarketCooldowns` and `MarketRegionRefresh` were absent from some runs due to ordering variance; those averages use the 2 runs in which they appeared.

```
  Test                             Rows    Wall (s)    ms/row   Weight
  MarketRegionRefresh (DataFrame) 50,000     0.281     0.0056     0.04
  Coalesce_Blocking   (INSERT)    20,000     2.929     0.1465     1.00  ← baseline
  Coalesce_Nowait     (INSERT)    20,000     2.887     0.1444     0.99
  StrucDisc_Phase1_Seed (UPSERT)     500     0.668     1.3372     9.13
  StructureMarketOrders (UPSERT)   1,000     1.369     1.3688     9.34
  StrucDisc_Phase2_Enrich (1-row)    100     0.221     2.2102    15.09
  MarketCooldowns_Nowait  (1-row)    200     0.482     2.4090    16.44
  DDL_CreateIfNotExists               50     0.015     0.2955     2.02
  DDL_AlterAddColumn                  50     0.012     0.2405     1.64
  CharData_Skills  (SQLite)          500     0.026     0.0524     0.36
  CharData_Assets  (SQLite)        2,000     0.083     0.0417     0.28
```

> `read`, `update`, `delete`, `truncate` are not included in the new benchmark (no production code path to mirror).
> Those weights are carried forward from the original in-memory benchmark where they were measured as near-zero per-row costs.

### Key findings

- **DataFrame bulk INSERT is 25× cheaper than plain batched INSERT** (0.0056 vs 0.1465 ms/row). A 50k-order Jita refresh writes in ~281ms total. This is why `replace_market_orders_for_region()` uses `db_write_dataframe()` and not `executemany`.
- **Batched upsert with a PRIMARY KEY costs ~9× a plain insert.** DuckDB cannot vectorise its executor when PK conflict resolution is required — both `INSERT OR REPLACE` and `ON CONFLICT DO UPDATE` through the writer land at ~1.35ms/row vs 0.147ms/row for a no-conflict insert. Acceptable at structure scale; would be catastrophic at market-order scale.
- **Single-row sequential writes cost ~16× a plain insert.** Each `db_write` or `db_executemany([1_row])` call is its own `BEGIN/COMMIT` in the writer thread. Never call these in a per-row loop over large datasets.
- **DDL costs ~1.8× per call** (including DuckDB connection open/close in the benchmark). `ensure_tables()` running before each collector write is fine at startup cadence.
- **Coalesced nowait is essentially free vs blocking** (0.1444 vs 0.1465 ms/row). The writer thread successfully batches 20 fire-and-forget chunks into one transaction with negligible overhead.
- **SQLite row-by-row** (~0.04–0.06 ms/row) is faster than batched DuckDB upserts with PK conflict. Character data writes are not a bottleneck regardless of character count.

### Weights

| Operation | `config.yaml` key | Weight | Notes |
|-----------|------------------|--------|-------|
| Read (`SELECT`) | `read` | 0.001 | Free as SQL — cost is per statement, not per row |
| Insert (`INSERT`) | `insert` | 1.0 | Baseline — batched `executemany` through writer |
| Upsert (PK conflict) | `upsert` | 9.0 | `INSERT OR REPLACE` / `ON CONFLICT DO UPDATE` with PK |
| Update (`UPDATE … WHERE`) | `update` | 0.0002 | Free as SQL — single statement regardless of rows affected |
| Delete (`DELETE … WHERE`) | `delete` | 0.003 | Free as SQL — single statement regardless of rows affected |
| Truncate | `truncate` | 4.69 | Scales with reset-iteration count; from original benchmark |
| DDL (`CREATE`/`ALTER TABLE`) | `ddl` | 1.8 | Avg of CREATE IF NOT EXISTS and ALTER ADD COLUMN |
| Bulk load (DataFrame) | `bulk_load` | 0.04 | Vectorised columnar import via `db_write_dataframe` |

**db-units total** for a task or owner = Σ(operation_count × weight) across all operation types.

Example `config.yaml` block:

```yaml
DB Units:
  read: 0.001
  insert: 1.0
  upsert: 9.0
  update: 0.0002
  delete: 0.003
  truncate: 4.69
  ddl: 1.8
  bulk_load: 0.04
```

---

## Appendix C — Role Reference

| Role string | Grants access to |
|-------------|-----------------|
| `dashboard` | `/dashboard` and all `/dashboard/character/<id>/*` sub-routes |
| `queue` | `/esi`, `/esi/<task_id>`, `WS /esi/ws`, `WS /esi/<task_id>/ws`, `POST /market/refresh_all` |
| `scheduler` | `/scheduler` — list, detail, toggle, run-now |
| *(admin access level)* | `/admin`, `/db/admin`, `/db/public`, `/db/<owner_id>` (any), `/esi/admin`, `/esi/explore`, `/sde`, `/system` and all sub-routes |
| `site_owner` | Unconditional access to every route including `POST /system/update` |

> Named roles are additive. An admin bypasses all named-role checks automatically.
