# EVE Data Framework

[![Latest Release](https://img.shields.io/github/v/release/NolieRavioli/eve_data_framework3?style=flat-square)](https://github.com/NolieRavioli/eve_data_framework3/releases/latest)

A self-hosted web application and data platform for EVE Online. The framework provides:

- **EVE SSO authentication** — multi-character OAuth 2.0 with Fernet-encrypted token storage
- **Shared DuckDB warehouse** — SDE dimension tables, live market orders, structure data, and ESI spec metadata
- **Per-character private SQLite databases** — skills, wallet, assets, and token credentials per owner
- **Background task queue** — two FIFO executor queues with live SSE log streaming to the browser
- **Cron-style scheduler** — recurring background jobs for market/structure/character data collection
- **Auto-discovered Flask applications** — pluggable web tools with role-based access control

---

## Table of Contents

1. [Installation](#installation)
2. [First-Run Setup](#first-run-setup)
3. [Accessing the Dashboard](#accessing-the-dashboard)
4. [Site Admin Guide](#site-admin-guide)
5. [Configuration Reference](#configuration-reference)
6. [Built-In Applications](#built-in-applications)
7. [Background Scheduler](#background-scheduler)
8. [Architecture Overview](#architecture-overview)
9. [Developer Guide — Creating Applications](#developer-guide--creating-applications)
10. [Developer Guide — Creating Analysis Collectors](#developer-guide--creating-analysis-collectors)
11. [Developer Guide — Core Layer](#developer-guide--core-layer)
12. [ESI Client & Code Generation](#esi-client--code-generation)
13. [Security Notes](#security-notes)
14. [Licensing](#licensing)

---

## Installation

### Prerequisites

- Python 3.12 or later
- `pip` (included with Python)
- Network access to EVE Online ESI (`esi.evetech.net`) and SSO (`login.eveonline.com`)
- An active EVE Online developer application (register at [developers.eveonline.com](https://developers.eveonline.com))

### Clone and install dependencies

```bash
git clone https://github.com/NolieRavioli/eve_data_framework3.git
cd eve_data_framework3
pip install -r requirements.txt
```

### Configure

Copy the example config and open it in your editor:

```bash
# Linux / macOS
cp example.config.yaml config.yaml && nano config.yaml

# Windows (PowerShell)
Copy-Item example.config.yaml config.yaml ; notepad config.yaml
```

The minimum required change is to enter your EVE developer application credentials (see [First-Run Setup](#first-run-setup)).

> **Note:** `config.yaml` is gitignored. It will never be committed. Keep your `client_id` and `client_secret` out of source control.

### Start the server

```bash
python main.py
```

The server starts on `http://127.0.0.1:5000` by default. To accept connections from other machines on your network, change `host` in `config.yaml`:

```yaml
Runtime:
  host: "0.0.0.0"
  port: 5000
```

---

## First-Run Setup

On the very first launch with a fresh database, the framework will display a **setup wizard** at `http://127.0.0.1:5000/setup`. This wizard walks through:

1. **Registering your EVE developer application credentials** — paste in your `client_id` and `client_secret` from [developers.eveonline.com](https://developers.eveonline.com). The callback URL you register on CCP's portal should be `http://<your-host>/auth/callback`.
2. **Logging in with your EVE character** — the first character to log in becomes the **site owner** and gains unconditional admin access.
3. **Triggering the initial SDE load** — downloads and unpacks the Static Data Export from CCP's servers into `_sde/` and builds the DuckDB warehouse. This can take several minutes depending on which SDE sections are enabled.

After setup, subsequent starts skip directly to the login page.

---

## Accessing the Dashboard

Navigate to `http://<host>:<port>/` in a browser. If you are not logged in you will be redirected to the login page. Click **Login with EVE Online** to start the SSO flow.

Once authenticated, you will land on the **Dashboard**, which shows your linked characters and quick-links to enabled applications.

To add additional characters to your account, use the **Add Toon** link on the dashboard.

---

## Site Admin Guide

### User Management

Site admins can manage other users through the **Admin Panel** (`/admin`):

- **Promote to site admin** — grants a user admin-level access across all applications.
- **Grant / revoke roles** — control which applications each user can access. Roles map 1-to-1 to application role names.
- **View logs** — the admin panel exposes a live log console streamed via SSE.

### Default Roles

Every new user is automatically granted the roles listed under `Auth.default_roles` in `config.yaml`:

```yaml
Auth:
  default_roles:
    - dashboard
    - queue
```

Change this list to grant or restrict access to applications for new users by default.

### Granting Roles Programmatically

```python
from core.auth import grant_user_roles, revoke_user_role

grant_user_roles(owner_id, ["dashboard", "database", "sde", "tasks"], granted_by=admin_owner_id)
revoke_user_role(owner_id, "tasks")
```

### Triggering Manual Data Collection

Data collection happens automatically on the scheduler (see [Background Scheduler](#background-scheduler)). To trigger a refresh manually, visit the **Scheduler** tab (`/tasks/scheduler/`) and click **Run Now** on any job. You can also use the **Task Manager** (`/tasks`) to monitor running jobs and stream their logs live.

### Regenerating the ESI Spec

If ESI adds new routes or changes its schema, regenerate the typed client:

```powershell
python build.py --force
```

This fetches the latest OpenAPI spec, regenerates the typed Python client in `core/esi/generated/`, and regenerates the domain-specific wrappers in `core/esi/personal/`, `core/esi/corp/`, and `core/esi/public/`.

---

## Configuration Reference

All runtime settings live in `config.yaml` (gitignored). A fully annotated template is provided in `example.config.yaml`. Key sections:

### `Runtime`

| Key | Default | Description |
|-----|---------|-------------|
| `host` | `"127.0.0.1"` | Flask bind address. Set to `"0.0.0.0"` to accept remote connections. |
| `port` | `5000` | TCP port. |
| `debug` | `false` | Enable Flask debug mode (never use in production). |
| `auto_install` | `false` | Auto-run `pip install -r requirements.txt` if modules are missing. |
| `trace_esi` | `false` | Print every outbound ESI HTTP call to stdout. |
| `secret_key` | random | Flask session secret. Set a persistent value so sessions survive restarts. |

### `Python Console`

Controls what appears in the terminal/console output. The root `global_log_level` sets the console `StreamHandler` threshold; per-logger keys silence or amplify individual loggers.

| Key | Default | Description |
|-----|---------|-------------|
| `global_log_level` | `INFO` | Threshold for all console output. |
| `werkzeug_log_level` | `INFO` | Werkzeug request log level (`WARNING` to silence per-request lines). |
| *(any logger name)* | — | Override the level of any named logger, e.g. `core.esi.rate: WARNING`. |

### `Web Console`

Controls the in-browser live log in the admin panel.

| Key | Default | Description |
|-----|---------|-------------|
| `admin_panel_global_log_level` | `DEBUG` | Minimum level captured into the admin panel live console. |

### `Environment Variables`

| Key | Default | Description |
|-----|---------|-------------|
| `LANGUAGE` | `"en"` | Primary language for SDE text fields. |
| `SUPPORTED_LANGUAGES` | `"en"` | Comma-separated languages; SDE pruner keeps only these. |
| `PUBLIC_DATA_FOLDER` | `"_publicData"` | Directory for DuckDB file and OAuth credentials. |
| `EVE_PRIVATE_DATABASE_FOLDER` | `"_privateData/"` | Root directory for per-owner SQLite files. |
| `SDE_PATH` | `"_sde/"` | Local SDE JSONL file directory. |

### `Auth`

```yaml
Auth:
  default_roles:
    - dashboard
    - queue
```

### `SDE`

Toggle which SDE datasets load at startup. Set a section to `false` to skip it (will lazy-load on first use):

```yaml
SDE:
  database_file: "_publicData/public.duckdb"
  load_types: true        # type ID <-> name maps          (~26 MB, ~4s)
  load_groups: true       # item group hierarchy            (~0.3 MB, fast)
  load_categories: true   # item categories                 (~0.1 MB, fast)
  load_market_groups: true # market group tree              (~0.3 MB, fast)
  load_universe: true     # solar-system -> region map      (~15s)
  load_blueprints: true   # manufacturing blueprints        (~8s)
  load_type_materials: true # reprocessing materials        (~3s)
  load_type_dogma: true   # item dogma attributes           (~60s+)
```

### `Structures` and `Market`

Cooldown settings that prevent re-fetching recently inaccessible structures. See `example.config.yaml` for full details.

---

## Built-In Applications

| Application | URL Prefix | Access | Description |
|-------------|------------|--------|-------------|
| `market_browser` | `/market` | Public (no login) | Browse live market orders by region and item type |
| `dashboard` | `/dashboard` | Role: `dashboard` | Character overview and quick links to all tools |
| `task_viewer` | `/tasks` | Role: `tasks` | Background task queue, live rate monitoring, scheduler (admin), and ESI explorer (admin) |
| `db_viewer` | `/db` | Role: `database` | DB queue stats, read stats; admin-tier schema browser and query tool |
| `admin_panel` | `/admin` | Admin only | User management — roles, admin promotion, user list |
| `sde_browser` | `/sde` | Admin only | SDE table browser, lookup tool, and reload trigger |
| `system` | `/system` | Admin only | Process metrics, git version, and system update |

---

## Background Scheduler

The scheduler (`core/tasks/engine.py`) runs a background thread that ticks every 30 seconds and fires registered jobs when their `next_run` is due. Job state (enabled, last run, next run, interval) is persisted in the DuckDB `scheduler_jobs` table so customizations survive restarts.

### Default Jobs

| Job | Default Interval | Worker |
|-----|-----------------|--------|
| Market Data Refresh | 1 hour | `analysis.market.regions.fetch_all_market_data` |
| Structure Discovery | 24 hours | `analysis.structures.discover.discover_structures` |
| Character Data Refresh | 24 hours | refreshes all owners via `analysis.character.populate.populate_all` |

Manage jobs through the **Scheduler** tab in the Task Manager (`/tasks/scheduler/`) or the `scheduler` adapter in code:

```python
from applications._api import scheduler

scheduler.list_jobs()              # list[dict] — all registered jobs
scheduler.set_enabled("market_refresh", True)
scheduler.run_now("structure_discovery")  # returns task_id
```

---

## Architecture Overview

```
main.py                  # startup: load config, init DB, start Flask
config.yaml              # runtime configuration (gitignored)
example.config.yaml      # annotated template — copy to config.yaml
requirements.txt

core/                    # infrastructure — never import from applications/
  config.py              # load_config(), RuntimeSettings, ensure_dependencies()
  auth/
    __init__.py          # re-exports: require_login, require_admin, require_role, pick_token, fresh_token, get_token, resolve_default_owner_id
    decorators.py        # require_login, require_admin, require_role — Flask route decorators
    identity.py          # user/admin/role CRUD: link_public_user, get_user_roles, grant_user_roles, revoke_user_role, …
    credentials.py       # CredentialManager — Fernet-encrypts/decrypts client_id/client_secret
    tokens.py            # TokenDBManager, get_token(), pick_token(), fresh_token(), resolve_default_owner_id()
    sso.py               # auth_bp — EVE SSO OAuth2 flow: /login, /callback, /logout, /add_toon, /switch_character
  bus/
    __init__.py          # re-exports topics, BusHandler, registry fns, websocket helpers
    topics.py            # LOG_DB, LOG_ESI, LOG_SCHEDULER, ESI_RATE, DB_STATS, SYSTEM_PROCESS, QUEUE_TASKS, classify()
    handler.py           # BusHandler(logging.Handler) — ring-buffer per-topic, publish(), subscribe()
    registry.py          # TopicConfig, register_topic(), get_topic_config()
    websocket.py         # /bus WebSocket endpoint, register_websock(), attach_all_websocks()
    process_pub.py       # SYSTEM_PROCESS periodic publisher
  db/
    public.py            # DuckDB connect(), CRUD helpers, identity-table DDL
    private.py           # SQLite per-owner: initialize_private_database(), get_private_session()
    models/identity.py   # User, SiteAdmin (DuckDB ORM), Character (SQLite ORM)
    sde.py               # in-memory SDE lookup caches
    reader.py            # query_rows(), query_one(), query_scalar(), get_db_file_stats()
    writer.py            # DuckDB write thread (serialises public DB writes)
    stats.py             # get_table_stats(), start_db_stats_publisher()
    market_buffer.py     # ephemeral in-process market buffer
  esi/
    request.py           # esi_request(), esi_get(), esi_post() — ALL ESI HTTP
    rate.py              # ESIRateLimiter — floating-window token bucket, ETag caching, 429 backoff
    cache.py             # DuckDB-backed response cache (esi_cache table)
    registry.py          # ESI OpenAPI spec fetcher and DuckDB registry
    generated/           # AUTO-GENERATED — do not edit by hand
    personal/            # AUTO-GENERATED domain wrappers (character-scoped)
    corp/                # AUTO-GENERATED domain wrappers (corporation-scoped)
    public/              # AUTO-GENERATED domain wrappers (public)
  tasks/
    queue.py             # Task class, enqueue(), get_task(), cancel_task(), clear_tasks()
    engine.py            # SchedulerEngine, get_engine()
    jobs.py              # job catalog — add new scheduled jobs here
    persist.py           # scheduler_jobs table DDL
    output.py            # task log routing and IO
    context.py           # thread-local task context
    sde_loader.py        # SDE pipeline: download → unzip → prune → DuckDB warehouse
  web/
    __init__.py          # create_app() — Flask app factory
    app.py               # start_webUI() entry point
    context.py           # base_ctx() sidebar helper
    home.py / setup.py   # home and setup wizard blueprints

analysis/                # empty — reserved for future use
collectors/              # data collection workers
  character/populate.py  # per-owner ESI → private SQLite (skills, wallet, assets)
  market/
    regions.py           # NPC region market orders
    structures.py        # player-structure market orders
    history.py           # market order history (daily price snapshots)
  structures/discover.py # discover + enrich public structures

applications/            # user-facing web tools (auto-discovered)
  _api.py                # single interface: BaseTool, ToolManifest, base_ctx, require_* and all adapters
  dashboard/             # character overview — nav_section="overview"
  task_viewer/           # task queue + scheduler + ESI explorer — nav_section="tools"
  db_viewer/             # DB stats + query browser — nav_section="tools"
  admin_panel/           # user management — nav_section="admin"
  sde_browser/           # SDE table browser + update trigger — nav_section="admin"
  system/                # process metrics + system update — nav_section="admin"
  market_browser/        # live market order browser — nav_section="overview"

utils/build/             # ESI client code generation (run via build.py)
```

### Layering Rules

- `core/` — infrastructure. No imports from `applications/` or `collectors/`.
- `collectors/` — data collectors. Import from `core.*` only.
- `applications/` — web applications. Import from `applications._api` **only** — never directly from `core.*`.

---

## Developer Guide — Creating Applications

Each application lives in `applications/<name>/` and is auto-discovered by `pkgutil` on startup.

### Required files

```
applications/my_tool/
  __init__.py      # defines Tool = MyTool()
  routes.py        # Flask blueprint
  templates/       # Jinja2 templates
  static/          # JavaScript, CSS (optional)
```

### `__init__.py`

```python
from applications._api import BaseTool, ToolManifest
from applications.my_tool import routes

class MyTool(BaseTool):
    manifest = ToolManifest(
        id="my_tool",
        name="My Tool",
        icon="?",
        description="Does something useful.",
        url_prefix="/tools/my_tool",
        required_scopes=[],
        nav_weight=50,
        nav_section="apps",
        access_level="user",
        required_role="my_tool",
    )

    def create_blueprint(self):
        return routes.my_bp

Tool = MyTool()
```

`access_level` values: `"public"` | `"user"` | `"admin"` | `"site_owner"`

Set `required_role=None` if no named role is required (access_level check only).

`nav_section` values: `"overview"` | `"tools"` | `"apps"` | `"admin"` | `""` (hidden)

### `routes.py`

```python
from flask import Blueprint, render_template
from applications._api import base_ctx, require_role, db, sde

my_bp = Blueprint("my_tool", __name__,
                  template_folder="templates",
                  static_folder="static")

@my_bp.route("/")
@require_role("my_tool")
def index():
    rows = db.query("SELECT type_id, name FROM sde_types LIMIT 10")
    return render_template("my_tool.html", rows=rows, **base_ctx("my_tool"))
```

Use `@require_role("role")` for named-role access (admins bypass automatically).
Use `@require_admin` for admin-only routes. Avoid bare `@require_login` on new routes.

### Template

```html
{% extends "base.html" %}
{% block title %}My Tool{% endblock %}
{% block content %}
  <div class="pg-hd"><h1>My Tool</h1></div>
  <div class="pg-body">...</div>
{% endblock %}
{% block scripts %}
<script src="{{ url_for('my_tool.static', filename='my_tool.js') }}"></script>
{% endblock %}
```

### Available adapters (`applications._api`)

| Adapter | Type | Description |
|---------|------|-------------|
| `db` | `_LiveDBAdapter` | `query()`, `query_one()`, `scalar()`, `private_query()`, `market_price()` |
| `sde` | `core.db.sde` module | All SDE lookup functions directly |
| `raw_esi` | `_LiveRawESIAdapter` | `get()`, `post()`, `request()` — rate-limited HTTP |
| `esi` | `_LiveESIAdapter` | `execute(op_id, ...)`, `fetch_pages(op_id, ...)` — typed client |
| `tokens` | `_LiveTokenAdapter` | `get(owner_id)` — raw token map |
| `token_resolution` | `_LiveTokenResolutionAdapter` | `pick_token()`, `fresh_token()` |
| `tasks` | `_LiveTaskAdapter` | `enqueue(name, fn, *args, owner_id, queue)` |
| `char_data` | `_LiveCharacterDataAdapter` | `get_character()`, `get_scopes()` |
| `esi_registry` | `_LiveESIRegistryAdapter` | `get_status()` |
| `db_admin` | `_LiveDBAdminAdapter` | Admin-level DB inspection helpers |
| `esi_manifest` | `_LiveESIManifestAdapter` | `get_operations()`, `get_operation(op_id)`, `get_meta()` |
| `queue_info` | `_LiveQueueInfoAdapter` | `get_all_tasks()`, `get_tasks_for_owner()`, `get_task()`, `cancel_task()`, `clear_tasks()`, `get_esi_rate_stats()` |
| `scheduler` | `_LiveSchedulerAdapter` | `list_jobs()`, `set_enabled()`, `run_now()` |

### Background workers from an application

Long-running work (data fetches, calculations) should be enqueued rather than blocking a request:

```python
from applications._api import tasks

def my_worker(owner_id: int) -> None:
    # runs in background thread — logging is streamed to the browser
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Starting my_worker for owner %s", owner_id)
    # ... do work ...

@my_bp.route("/run")
@require_role("my_tool")
def run_task():
    from flask import session
    owner_id = session["owner_id"]
    task_id = tasks.enqueue("My Task", my_worker, owner_id, owner_id=owner_id)
    return {"task_id": task_id}
```

---

## Developer Guide — Creating Analysis Collectors

Analysis collectors are data pipeline workers that populate DuckDB or per-owner SQLite. They live in `collectors/<domain>/`.

### Structure

```
collectors/my_domain/
  __init__.py       # re-exports entry points
  worker.py         # table DDL + data collection functions
```

### Table Ownership Pattern

```python
# analysis/my_domain/worker.py
import logging
import core.db.public as db

logger = logging.getLogger(__name__)

def ensure_tables(con) -> None:
    """Idempotent DDL — always call before any writes."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS my_table (
            id INTEGER PRIMARY KEY,
            value DOUBLE,
            fetched_at TIMESTAMP DEFAULT now()
        )
    """)

def fetch_my_data() -> None:
    """Entry point called by the scheduler or manually."""
    con = db.connect()
    try:
        ensure_tables(con)
        # ... collect data and write ...
    finally:
        con.close()
```

### Enrichment Pattern

If your collector adds columns to a table owned by another collector:

```python
def ensure_columns(con) -> None:
    from collectors.structures.discover import ensure_tables as _ensure_structures
    _ensure_structures(con)
    con.execute("""
        ALTER TABLE structures ADD COLUMN IF NOT EXISTS my_col TIMESTAMP
    """)
```

### Making ESI Requests

**Never use `requests` directly.** Import `esi_get`/`esi_request` directly from `core.esi`:

```python
from core.esi import esi_get, esi_request

resp = esi_get("https://esi.evetech.net/latest/markets/10000002/orders/",
               params={"page": 1, "order_type": "all"})
if not resp.ok:
    logger.warning("ESI %s: %s", resp.status_code, resp.url)
    return

data = resp.json()
total_pages = int(resp.headers.get("X-Pages", 1))
```

### Registering a Scheduled Job

Add an entry to `core/tasks/jobs.py`:

```python
try:
    from collectors.my_domain.worker import fetch_my_data
    jobs.append({
        "job_id": "my_domain_refresh",
        "label": "My Domain Data Refresh",
        "fn": fetch_my_data,
        "fn_path": _path(fetch_my_data),
        "interval_s": 3600,
    })
except Exception:
    logger.warning("[SchedulerJobs] Could not import my_domain — skipping job")
```

The scheduler will auto-upsert the job on next startup.

---

## Developer Guide — Core Layer

The `core/` layer is the infrastructure backbone. Applications import from `applications._api` — they should not import from `core.*` directly. Analysis workers import from `core.*` directly.

### Key modules

| Module | Purpose |
|--------|---------|
| `core.config` | `load_config()`, `RuntimeSettings`, `get_runtime_settings()` |
| `core.auth` | `require_login`, `require_admin`, `require_role`, SSO flow (`auth_bp`), user/role CRUD |
| `core.auth.tokens` | `get_token()`, `pick_token()`, `fresh_token()`, `resolve_default_owner_id()` |
| `core.auth.credentials` | `CredentialManager` — Fernet-encrypts/decrypts OAuth client credentials |
| `core.db.public` | DuckDB connections and CRUD helpers |
| `core.db.private` | Per-owner SQLite session factory |
| `core.db.models` | `User`, `SiteAdmin` (DuckDB ORM), `Character` (SQLite ORM) |
| `core.db.reader` | Read helpers — `query_rows()`, `query_one()`, `query_scalar()`, `get_db_file_stats()` |
| `core.db.writer` | Serialised DuckDB write thread — `db_write()`, `db_executemany()` |
| `core.db.sde` | SDE cache lookups — `name_from_type_id()`, `region_id_from_system_id()`, etc. |
| `core.esi` | Re-exports `esi_get()`, `esi_post()`, `esi_request()` — all ESI HTTP |
| `core.esi.rate` | `ESIRateLimiter` — floating-window token bucket, ETag caching, 429 backoff |
| `core.esi.registry` | Fetch and parse ESI OpenAPI spec |
| `core.esi.generated.client` | `execute_operation()`, `fetch_all_pages()` — typed ESI calls |
| `core.tasks.queue` | `enqueue()`, `get_task()`, `cancel_task()`, `clear_tasks()`, task queue internals |
| `core.tasks.engine` | `SchedulerEngine`, `get_engine()` — background job scheduler |
| `core.bus` | Pub/sub event bus — `BusHandler`, topic ring buffers, WebSocket at `/bus` |

### Adding a new private DB model

Subclass `PrivateBase` in `core/db/models/identity.py` (or a new model file imported there):

```python
from core.db.models import PrivateBase
from sqlalchemy import Column, Integer, String

class MyCharacterData(PrivateBase):
    __tablename__ = "my_character_data"
    id = Column(Integer, primary_key=True)
    character_id = Column(Integer, nullable=False)
    value = Column(String)
```

`initialize_private_database(owner_id)` will automatically create the table on first use.

### DuckDB Thread Safety

DuckDB connections are **not thread-safe**. Always get a fresh connection per operation:

```python
import core.db.public as db

con = db.connect()
try:
    rows = con.execute("SELECT * FROM sde_types WHERE type_id = ?", [34]).fetchall()
finally:
    con.close()
```

For writes that must be serialised (to avoid DuckDB write contention), use the write thread:

```python
from core.db.writer import db_write, db_executemany

db_write("INSERT INTO my_table VALUES (?, ?)", [1, "value"])
db_executemany("INSERT INTO my_table VALUES (?, ?)", [(1, "a"), (2, "b")])
```

---

## ESI Client & Code Generation

### Typed Client

```python
from core.esi.generated.client import execute_operation, fetch_all_pages

# Single page
result = execute_operation("GetMarketsRegionIdOrders",
                           path_params={"region_id": 10000002},
                           query_params={"order_type": "all"})

# All pages automatically
orders = fetch_all_pages("GetMarketsRegionIdOrders",
                          path_params={"region_id": 10000002},
                          query_params={"order_type": "all"})
```

### Regenerating

```powershell
python build.py              # fetch spec + regenerate all generated packages
python build.py --force      # force regenerate even if spec is current
python build.py --spec-only  # only fetch the latest ESI spec
python build.py --collectors # only regenerate core/esi/personal|corp|public/
```

> **Do not hand-edit** `core/esi/generated/`, `core/esi/personal/`, `core/esi/corp/`, or `core/esi/public/` — every build run overwrites them.

---

## Security Notes

| File/Path | Risk | Mitigation |
|-----------|------|-----------|
| `_publicData/key` | Fernet symmetric key — decrypts all OAuth tokens | **Never commit.** Listed in `.gitignore`. |
| `_publicData/client_cred` | Encrypted `client_id`/`client_secret` | **Never commit.** Listed in `.gitignore`. |
| `_privateData/` | Per-user SQLite databases with tokens and character data | **Never commit.** Listed in `.gitignore`. |
| `config.yaml` | Contains host, port, session secret | **Never commit.** Listed in `.gitignore`. |

Additional protections:

- **CSRF** — SSO callback validates the `state` parameter via a time-limited `OAuthStateCache` that consumes each token exactly once within a 5-minute window.
- **SQL injection** — all DuckDB queries use parameterised `con.execute("... WHERE id = ?", [val])`. No user input is interpolated into SQL strings.
- **Token encryption** — OAuth tokens are Fernet-encrypted before being written to disk. The symmetric key never leaves the server.
- **Rate limiting** — `esi_req.py` enforces ESI's floating-window token bucket and automatically backs off on 429 responses.

---

## Licensing

This project is released under the MIT License. See `LICENCE.md` for the full text.

EVE Online and all associated materials are property of CCP hf. This project is not affiliated with or endorsed by CCP hf.
