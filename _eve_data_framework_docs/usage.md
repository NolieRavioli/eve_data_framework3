# Usage Guide

This guide covers every major feature of the EVE Data Framework UI, organized by subsystem. All features are accessible from the sidebar after logging in.

---

## Table of Contents

1. [Navigation & Sidebar](#navigation--sidebar)
2. [Dashboard](#dashboard)
3. [Market Browser](#market-browser)
4. [Task Manager](#task-manager)
5. [Database Viewer](#database-viewer)
6. [SDE Browser](#sde-browser)
7. [Site Admin Guide](#site-admin-guide)
8. [Admin Panel](#admin-panel)
9. [System](#system)
10. [Authentication & Characters](#authentication--characters)
11. [Public Access](#public-access)

---

## Built-In Applications

<!-- inject:readme_apps_table -->

---

## Navigation & Sidebar

The sidebar is automatically populated from all registered applications. It is divided into sections:

| Section | Contents |
|---------|----------|
| **Overview** | Dashboard, Market Browser |
| **Tools** | Task Manager, Database Viewer, SDE Browser |
| **Admin** | Admin Panel, System |

Tools only appear in the sidebar if the current user holds the required role (or is a site admin). Tools marked `access_level: public` appear for all visitors including unauthenticated users.

The active page is highlighted. Each tool entry shows its icon (emoji), name, and a hover tooltip with its description.

---

## Dashboard

**URL:** `/dashboard/` — **Role required:** `dashboard`

The Dashboard is the main character data hub. It requires at least one character to be linked via EVE SSO.

### Character Grid

The index page displays a card for each character linked to your account:

- **Character portrait** (fetched from EVE image server)
- **Character name**
- **Wallet balance** (ISK, formatted)
- **Total skillpoints**
- **Active training skill** (skill name + level training to)
- **Training completion time** (local time)

An aggregate row shows your account totals across all characters.

### Character Sheet

Click any character card to open the full character sheet at `/dashboard/character/<id>`.

**Tabs:**

#### Overview
- Character biography, corporation, alliance
- ESI scopes granted at login
- Token expiry status
- Quick-access links to external sites (zKillboard, EVERef, Dotlan)

#### Skills
- Skills grouped by skill group
- Per-skill: trained level (I–V), active level, skillpoints in skill
- Total SP sum at the top of each group
- Color-coded: fully trained skills (V) highlighted

#### Assets
- Hierarchical asset tree: locations → containers → items
- Per-item: type name, quantity, location flag
- Location resolved from SDE (station name, solar system, region)
- Blueprint originals vs. copies distinguished

#### Wallet
- Current ISK balance
- Last updated timestamp
- Journal available if scope `esi-wallet-read-character-wallet-v1` is granted

### Refreshing Character Data

Character data (skills, wallet, assets) is collected automatically by the scheduler every 24 hours. To trigger an immediate refresh, go to the **Task Manager** and run the `character_refresh` job manually, or navigate to `/tasks` and enqueue from there.

---

## Market Browser

**URL:** `/market/` — **Access level:** `public` (no login required)

The Market Browser displays live market orders collected from ESI. It supports both NPC station market orders and player-owned structure orders (if structure market collection is enabled and tokens are available).

### Region & Type Selection

The top of the page has:
- **Region selector** — dropdown of all market regions. Defaults to The Forge (Jita).
- **Type search bar** — full-text search across type names. Uses the SDE in-memory cache (instant).
- **Market group tree** — collapsible tree of market categories → groups → types. Click a leaf to load orders.

### Order Table

Once a type is selected, the page displays:

| Column | Notes |
|--------|-------|
| **Price** | ISK per unit, formatted with commas |
| **Volume Remain** | Units available |
| **Location** | Station or structure name (resolved from SDE/structures table) |
| **Order Range** | Sell: `station` / `region` / etc. Buy: `region`, jump counts |
| **Expires** | ISO date (computed from `issued` + `duration`) |

- **Sell orders** sorted ascending by price (best sell at top)
- **Buy orders** sorted descending by price (best buy at top)
- **Best sell / best buy** summary shown above the table

### Market History

Below the order table is a **Price History** chart (if history data is available). Clicking **Load History** triggers an on-demand ESI fetch for that type + region, which is then cached in `market_history` on DuckDB.

The chart shows:
- Daily high / low price range (candlestick-style)
- 30-day moving average
- Volume bars

### Ephemeral Buffer

When the scheduler is actively collecting a region, orders for that region are available in-memory before the DuckDB write completes. The market browser queries the ephemeral buffer first, so you may see partially-collected data during a collection run. Once the run completes, data is committed to disk automatically.

---

## Task Manager

**URL:** `/tasks/` — **Role required:** `tasks`

The Task Manager is the primary interface for monitoring background work and configuring the scheduler.

### My Tasks

Lists all tasks submitted by the current user (or all tasks for admins). Each row shows:

- **Task name**
- **Status** — `pending`, `running`, `complete`, `failed`, `cancelled`
- **Duration** — how long it took (or has been running)
- **Queue** — `public` or `private`
- **Actions** — cancel (pending only), view log

### Task Log

Clicking a task opens `/tasks/<task_id>`, which shows:

- Real-time streaming log (SSE) while the task is running
- Full historical log once complete
- ESI rate stats at the moment the task ran
- Final status and error (if failed)

The log stream auto-scrolls to the bottom. Refresh manually if the stream disconnects.

### Scheduler

**URL:** `/tasks/scheduler/` — **Admin only**

Displays all registered scheduled jobs:

| Column | Notes |
|--------|-------|
| **Job ID** | Internal stable identifier |
| **Label** | Human-readable name |
| **Enabled** | Toggle with the switch |
| **Interval** | How often the job fires (editable) |
| **Last Run** | UTC timestamp of last execution |
| **Next Run** | Scheduled next execution time |
| **Actions** | Run Now, enable/disable |

**Run Now** enqueues the job immediately (ignoring `next_run`), then redirects you to the task log.

**Default scheduled jobs:**

| Job ID | Description | Interval |
|--------|-------------|----------|
| `market_refresh` | NPC region market orders | 1 hour |
| `structure_market_refresh` | Player structure market orders | 1 hour |
| `structure_discovery` | Discover public structures | 24 hours |
| `character_refresh` | Character skills, wallet, assets | 24 hours |
| `esi_spec_refresh` | ESI spec + codegen update | 24 hours (disabled by default) |

### ESI Explorer

**URL:** `/tasks/api/explorer` — **Admin only**

A built-in API explorer for the EVE ESI. Browse all available operations from the generated ESI manifest:

- Search operations by name, path, or tag
- Select an operation to see its parameters, required scopes, response schema, and caching metadata
- Execute operations directly:
  - Fill in path parameters and query parameters
  - Optionally provide an authorization token (Bearer)
  - See the raw JSON response

This is useful for debugging ESI calls and exploring what data is available.

### ESI Rate Monitor

Displays the current state of the ESI rate limiter:
- Requests in the last minute (floating window)
- Remaining error limit (`X-ESI-Error-Limit-Remain`)
- Current backoff time (if any 429s were received)
- Per-endpoint rate limit group stats

---

## Database Viewer

**URL:** `/db/` — **Role required:** `database`

The Database Viewer provides read-only inspection of both the public DuckDB warehouse and per-character private SQLite databases.

### Stats Overview

The index page shows:
- **Row counts** for all tables in the warehouse
- **File size** of `public.duckdb` and per-character SQLite files
- **Write rate** — DB units written per second (sampled from the bus)
- **Task attribution** — which running or recent task wrote the most rows

### Private Database Browser

**URL:** `/db/private/`

Browse your own character's SQLite database:
- Table list with row counts
- Schema inspector (column names, types)
- SQL query tool (up to 500 rows returned)

Available private tables after character data is collected:
- `character_skills` — trained and active levels per skill
- `character_wallet` — current balance + history
- `character_assets` — full asset tree

### Public Warehouse Browser

**URL:** `/db/public/` — **Admin only**

Same interface targeting the shared DuckDB warehouse. Shows all tables including:
- All SDE tables
- Market orders and history
- Structures
- Scheduler jobs
- ESI cache and registry
- Auth tables

SQL queries run as read-only (SELECT only) with a 500-row cap for safety.

---

## SDE Browser

**URL:** `/sde/` — **Role required:** `sde`

The SDE Browser allows interactive lookup of any static game data loaded from CCP's Static Data Export.

### Index

Shows the current SDE dataset status:
- Which datasets are loaded (types, groups, categories, universe, blueprints, etc.)
- Row counts per table
- Last loaded timestamp
- **Trigger SDE Update** button (enqueues a full re-download and rebuild of the warehouse)

### Lookup

**URL:** `/sde/lookup`

Full-text search across types, solar systems, and regions. Accepts:
- **Type ID** — e.g. `34` → returns Tritanium
- **Type name** — e.g. `Tritanium` → exact or prefix match
- **System name** — e.g. `Jita`
- **Region name** — e.g. `The Forge`

Results show the match category (type / system / region) and link to the detail page.

### Type Detail

**URL:** `/sde/lookup/type/<type_id>`

Displays full SDE data for a specific type:
- **Name** (English and other available languages)
- **Group** → **Category** hierarchy
- **Market group** path (breadcrumb)
- **Attributes** — mass, volume, capacity, portion size, base price
- **Dogma attributes** (if `load_type_dogma` is enabled in config)
- **Reprocessing materials** (if `load_type_materials` is enabled)
- **Blueprint** — if this type is the output of a blueprint (if `load_blueprints` is enabled)

### System Detail

**URL:** `/sde/lookup/system/<system_id>`

- System name, security status (color-coded high/low/null)
- Region → Constellation → System hierarchy
- List of planets (resolved to type names)
- List of stargates (with destination system and region)
- NPC stations in system

### Region Detail

**URL:** `/sde/lookup/region/<region_id>`

- Region name and faction (if any)
- List of constellations (linked)
- List of systems within the region

---

## Site Admin Guide

<!-- inject:readme_site_admin -->

---

## Admin Panel

**URL:** `/admin/` — **Admin access only**

The Admin Panel is for managing users, their roles, and monitoring the system.

### Dashboard

Overview of:
- Total registered users (owners)
- How many have admin status
- Current database stats (size, write rate)
- SDE and ESI spec readiness

### User List

**URL:** `/admin/users`

Shows all registered accounts. Each row shows:
- Owner ID
- Linked character count
- Admin status (badge)
- Actions: View, promote/demote admin

### User Detail

**URL:** `/admin/users/<owner_id>`

Full profile for a specific user:

**Roles section:**
- Current named roles (listed with grant date and granted-by)
- Input to grant additional roles (comma-separated role names)
- Revoke button per role

**Characters section:**
- All characters linked to this owner
- Each character's name, scopes list, token expiry

**Admin section:**
- Promote to site admin / demote
- Mark as site owner (only current site owner can do this)
- **Delete user** — removes the account, all roles, and all private data. **Irreversible.** Site owner only.

### Live Logs

**URL:** `/admin/logs` — accessible from the admin nav

Displays the real-time event bus log. Tabs correspond to bus topics:

| Tab | Topic | Contents |
|-----|-------|---------|
| System | `log/system` | Config, startup, lifecycle events |
| ESI | `log/esi` | Every ESI request + rate limiter state |
| DB | `log/db` | DuckDB writes, reads, errors |
| Scheduler | `log/scheduler` | Job ticks, job fires |
| Market | `log/market` | Market collector progress |
| Auth | `log/auth` | Login, token refresh, SSO events |
| All | `log/*` | All log entries merged |

Log entries stream live via WebSocket (`/bus`). The buffer holds the last 2000 entries per topic.

---

## System

**URL:** `/system/` — **Admin access only**

Operational system management for site administrators.

### Status Overview

- **Python version** and process PID
- **Process uptime** (days, hours, minutes)
- **Memory usage** (RSS, VMS)
- **CPU usage** (% across all cores)
- **Current git commit** hash and message
- **Latest GitHub release** (fetched from GitHub API; highlighted if a newer version is available)

### Subsystem Status

| Subsystem | What it checks |
|-----------|----------------|
| SDE | DuckDB `sde_types` exists and has rows |
| ESI | Generated `manifest.py` exists and is current |
| Database | DuckDB is writable (test write + delete) |

Status indicators: `ready` (green), `degraded` (yellow), `unavailable` (red).

### Actions

| Button | What it does |
|--------|-------------|
| **Update System** | `git pull`, `pip install -r requirements.txt`, then restart process |
| **Update SDE** | Re-download SDE JSONL from CCP S3, rebuild DuckDB warehouse |
| **Update ESI Spec** | Fetch latest ESI OpenAPI spec, regenerate typed client code |
| **Regenerate Config Template** | Overwrite `example.config.yaml` with current defaults |
| **Restart** | Graceful process restart |

Updates run as background tasks and can be monitored in the Task Manager.

### Bus Topic Browser

Scrollable list of all registered bus topics with entry counts. Click a topic to drill into its recent history.

---

## Authentication & Characters

### Logging In

Navigate to `/login` (or click "Login with EVE Online" on the landing page). You will be redirected to the official EVE Online SSO portal to authorize the application.

### Linking Additional Characters

Once logged in, go to `/add_toon` to add another EVE character to your account. All characters share the same `owner_id` but have separate tokens, scopes, and private databases.

### Switching Characters

The `/switch_character/<id>` route changes which character is "active" in your session. The Dashboard will use the active character as the primary display.

### Logging Out

`/logout` clears the session. Tokens remain stored in the private database — logging back in uses the same account without requiring re-authorization.

### Token Expiry

ESI access tokens expire every 20 minutes. The framework auto-refreshes tokens on demand using the stored refresh token. You will only see a token error if the refresh token itself becomes invalid (e.g. you revoke access on the EVE SSO portal) — in that case, simply log in again.

---

## Public Access

Routes marked `access_level: public` do not require login:

- `/` — landing page
- `/market/` — Market Browser (full functionality without authentication)

Public access is designed for read-only display of shared market data. All character-specific features require login.
