# EVE Data Framework — Contributor & Agent Guide

This document is the authoritative reference for **human contributors** and **AI coding agents** working in this repository. Read it in full before making any changes.

> **AI agents:** `_esi_docs/` contains the full official ESI documentation — rate limiting, pagination, best practices, SSO, and more. **Always consult `_esi_docs/` before writing or reviewing any ESI-related code.** Start with `_esi_docs/services/esi/` for API behaviour and `_esi_docs/services/sso/` for auth.
> **IMPORTANT — about this file:** Do **not** modify `AGENTS.md` yourself. If you believe a change is needed (outdated section, missing information, incorrect detail), relay the specific proposed change to the user and let them decide. This file is the ground truth — it must stay accurate and intentional.

> Current documentation located at: https://developers.eveonline.com/docs/
> ESI api: https://developers.eveonline.com/api-explorer#/

---

## Table of Contents

1. [Repository Overview](#repository-overview)
2. [Directory Map](#directory-map)
3. [Layering Rules & Import Discipline](#layering-rules--import-discipline)
4. [Code Conventions](#code-conventions)
5. [Database Architecture](#database-architecture)
6. [Making ESI Requests](#making-esi-requests)
7. [Authentication & Tokens](#authentication--tokens)
8. [Background Task Queue](#background-task-queue)
9. [Scheduler](#scheduler)
10. [Applications Layer](#applications-layer)
11. [Analysis / Collectors Layer](#analysis--collectors-layer)
12. [Plugin Framework](#plugin-framework)
13. [ESI Client & Code Generation](#esi-client--code-generation)
14. [Configuration](#configuration)
15. [Security Rules](#security-rules)
16. [Common Tasks for AI Agents](#common-tasks-for-ai-agents)
    - [Integrating a New Core Interface / Adapter](#integrating-a-new-core-interface--adapter)
    - [Creating a New Analysis Collector](#creating-a-new-analysis-collector)
    - [Creating a New Application](#creating-a-new-application)
    - [Registering a New Scheduled Job](#registering-a-new-scheduled-job)
    - [Updating the README](#updating-the-readme)
    - [Keeping AGENTS.md Accurate](#keeping-agentsmd-accurate)

---

## Repository Overview

**EVE Data Framework** is a self-hosted Flask web application that interfaces with the EVE Online ESI REST API. It is structured into clean architectural layers:

| Layer | Package | Purpose |
|---|---|---|
| **Core** | `core/` | Infrastructure: DB connections, ESI wrappers, SDE caches, task queue, scheduler, plugin framework |
| **Analysis** | `analysis/` | Data-collection workers: market, structures, SDE pipeline, character data |
| **Applications** | `applications/` | User-facing web tools — auto-discovered via `pkgutil` |
| **Web** | `core/web/` | Flask app factory, SSO auth, Jinja2 templates |
| **Config** | `core/config.py` / `config.yaml` | Runtime settings, environment variables |
| **Entry** | `main.py` | Startup: load config, init DB/SDE, start task queue writer, start Flask |
| **Codegen** | `utils/build/` | ESI client + domain collector code generation (run via `build.py`) |

### Tech Stack

- **Python 3.12+** — all async-free; threading via `ThreadPoolExecutor`
- **Flask** — web server, thread-safe, `threaded=True`
- **SQLAlchemy** — ORM; SQLite per character; `PublicBase`/`PrivateBase` declarative bases
- **DuckDB** — single shared public store (SDE, market orders, structures, ESI spec metadata, scheduler state)
- **requests** — all HTTP; wrapped by `core/queue/esi_req.py` (rate limiter + caching)
- **`config.yaml`** — runtime configuration; loaded once at startup (gitignored, never committed)

---

## Directory Map

```
main.py                  # startup: load config, init DB, start queue writer, start Flask
config.yaml              # runtime config  [GITIGNORED — never commit]
example.config.yaml      # annotated template — copy to config.yaml
requirements.txt         # pip dependencies
build.py                 # refresh ESI spec + regenerate codegen packages

core/                    # ── INFRASTRUCTURE ──────────────────────────────────
  config.py              # load_config(), RuntimeSettings, ensure_dependencies(), get_runtime_settings()
  db/
    __init__.py          # ensure_schema(), warm_caches(), initialize_all()
    publicDB.py          # DuckDB: connect(), CRUD helpers, identity-table DDL
    privateDB.py         # SQLite per owner: initialize_private_database(), get_private_session()
    models/
      __init__.py        # re-exports: PublicBase, PrivateBase, User, SiteAdmin, Character
      identity.py        # User, SiteAdmin (DuckDB ORM), Character (SQLite ORM)
  esi/
    __init__.py          # (empty)
    auth.py              # OAuth token storage (Fernet-encrypted), CredentialManager, TokenDBManager
    registry.py          # fetch_openapi_spec(), refresh_esi_spec_registry()
    generated/           # AUTO-GENERATED — do not edit by hand
      client.py          # execute_operation(), fetch_all_pages()
      manifest.py        # OPERATIONS dict, ALL_SCOPES, COMPATIBILITY_DATE
      operations.py      # typed operation definitions
      schemas.py         # TypedDict-compatible schema definitions
    personal/            # AUTO-GENERATED per-character domain wrappers
    corp/                # AUTO-GENERATED corporation-scoped domain wrappers
    public/              # AUTO-GENERATED public domain wrappers
  queue/
    __init__.py          # re-exports: Task, enqueue, get_task, cancel_task, rate_stream, log_stream, db_write, db_executemany
    esi_req.py           # esi_request(), esi_get(), esi_post() — ALL ESI HTTP goes here
    scheduler.py         # enqueue(), get_task(), get_tasks_for_owner(), cancel_task(), clear_tasks()
    streams.py           # rate_stream(), log_stream() — SSE generators
    writer.py            # serialised DuckDB write thread: start_writer(), stop_writer(), db_write(), db_executemany()
  sde/
    __init__.py          # re-exports all of core.sde.cache
    cache.py             # in-memory SDE caches: name_from_type_id, region_id_from_system_id, etc.
  scheduler/
    __init__.py          # SchedulerEngine class, get_engine() singleton
    db.py                # ensure_tables(), upsert_job_registration()
    jobs.py              # job catalog — add new scheduled jobs here
  plugin/
    __init__.py          # (docstring only)
    base.py              # BaseTool, ToolManifest, ToolRegistry, ACCESS_LEVELS
    web.py               # re-exports: base_ctx, require_login, require_admin, require_role
  web/
    __init__.py          # create_app() — Flask app factory
    app.py               # start_webUI(settings) — entry point called by main.py
    auth.py              # EVE SSO OAuth2 flow (auth_bp) + require_login/admin/role decorators
    context.py           # base_ctx(active_page) — sidebar template context helper
    home.py              # home_bp — unauthenticated landing page
    setup.py             # setup_bp — first-run credential wizard
    templates/           # base.html, home.html, setup.html (shared)

analysis/                # ── DATA COLLECTION ─────────────────────────────────
  __init__.py            # (docstring only — no re-exports)
  sde_loader.py          # SDE pipeline: download → unzip → prune → DuckDB warehouse
  character/
    __init__.py          # re-exports: populate_all
    populate.py          # per-character ESI → private SQLite (skills, wallet, assets)
  market/
    __init__.py          # re-exports: fetch_all_market_data, update_structure_market_orders
    regions.py           # NPC station market orders — owns market_orders, market_region_cooldowns
    structures.py        # player-structure market orders — owns market_structures, enriches structures
  structures/
    __init__.py          # re-exports: discover_structures
    discover.py          # discover + enrich public structures — owns structures table

applications/            # ── USER-FACING TOOLS ───────────────────────────────
  __init__.py            # pkgutil auto-discovery, tool_registry singleton
  _base.py               # re-exports: BaseTool, ToolManifest, base_ctx, require_*, get_runtime_settings
  _adapters.py           # core infrastructure singletons for the applications layer (db, sde, tasks, …)
  dashboard/             # nav_section="overview" — character overview; access_level="user", required_role="dashboard"
  queue_viewer/          # nav_section="tools"    — live job progress + ESI rate SSE; access_level="user", required_role="queue"
  admin_panel/           # nav_section="admin"    — logs, stats, user mgmt; access_level="admin"
  db_browser/            # nav_section="admin"    — DuckDB/SQLite browser; access_level="admin"
  esi_browser/           # nav_section="admin"    — ESI operation explorer; access_level="admin"
  scheduler/             # nav_section="admin"    — background job management; access_level="admin", required_role="scheduler"
  market_browser/        # nav_section="apps"     — live market orders; access_level="public"
  industry_calculator/   # nav_section="apps"     — manufacturing cost calc; access_level="user", required_role="industry"
  isk_per_hour/          # nav_section="apps"     — ISK/hr rankings; access_level="user", required_role="isk_per_hour"

utils/                   # ── UTILITIES & CODE GENERATION ─────────────────────
  build/
    __init__.py
    esi_codegen.py       # generate() — produces core/esi/generated/
    domain_codegen.py    # generate_collectors() — produces core/esi/personal|corp|public/
  __init__.py

# ── DATA DIRECTORIES ────────────────────────────────────────────────────────
_sde/                    # local SDE YAML files (gitignored)
_publicData/
  public.duckdb          # DuckDB warehouse (gitignored)
  client_cred            # Fernet-encrypted OAuth credentials  [NEVER COMMIT]
  key                    # Fernet symmetric key                [NEVER COMMIT]
  esi_specs/             # cached ESI OpenAPI spec snapshots
_privateData/<owner_id>/
  <owner_id>.db          # per-character SQLite                [NEVER COMMIT]
```

---

## Layering Rules & Import Discipline

The three main layers have strict import rules. **Never violate these.**

### `core/`

- Contains only infrastructure. No imports from `applications/` or `analysis/`.
- Sub-modules within `core/` may import from each other (e.g. `core.db` imports `core.config`).

### `analysis/`

- Data collection workers. Import from `core.*` only.
- Use `core.queue.esi_req` functions (`esi_get`, `esi_post`), `core.esi.auth` helpers, and `core.sde` directly.
- Use `core.db.publicDB` directly **only** for owned-table DDL and write operations.
- Never import from `applications/`.

### `applications/`

- User-facing tools. **Import ONLY from `applications._base` and `applications._adapters`.**
- Never import from `core.*` directly in an application's routes or `__init__`.
- Worker files within an application may import from `analysis.*` to trigger data collection.

### Import paths quick reference

```python
# ✅ Correct — application routes.py
from applications._base import base_ctx, require_role
from applications._adapters import db, sde, tasks, esi

# ✅ Correct — analysis worker
from core.queue.esi_req import esi_get
from core.db import publicDB
import core.sde as sde

# ❌ Wrong — application importing from core directly
from core.db.publicDB import connect          # forbidden in applications/
```

---

## Code Conventions

- **All ESI HTTP → `esi_request` / `esi_get` / `esi_post`** via `core.queue.esi_req`. Never use `requests` directly.
- **Logging**: `logger = logging.getLogger(__name__)` at module level. No bare `print()` in production code.
- **Thread safety**: fresh `connect()` per thread for DuckDB; `threading.Lock()` for shared mutable state.
- **No raw SQL with user input** — always parameterised: `con.execute("WHERE id = ?", [val])`.
- **Token handling**: 401 → token expired (stop, raise, do not retry); 403 → no permission (not retryable, return None).
- **Table DDL belongs to analysis workers** — never add domain table DDL to `core/db/publicDB.py`.
- **`access_level` and `required_role` go in `ToolManifest`** — set them directly in the `ToolManifest` constructor in each application's `__init__.py`. There is no `auth.json` file.
- **`@require_role` on new routes** — prefer over bare `@require_login`. Use `@require_admin` only for genuinely admin-only routes.
- **Do not edit auto-generated packages** — `core/esi/generated/`, `core/esi/personal/`, `core/esi/corp/`, `core/esi/public/` are overwritten each `build.py` run.
- **Config is gitignored** — `config.yaml` must never be committed. Use `example.config.yaml` for documentation and defaults.

---

## Database Architecture

### Public — DuckDB (`_publicData/public.duckdb`)

Single file, shared across all threads. **Get a fresh connection per thread; connections are not thread-safe.**

```python
from core.db import publicDB

con = publicDB.connect()
try:
    rows = con.execute("SELECT type_id, name_en FROM dim_types WHERE type_id = ?", [34]).fetchall()
finally:
    con.close()
```

For write operations (INSERT / UPDATE / DELETE) dispatched from multiple threads, use the serialised writer:

```python
from core.queue.writer import db_write, db_executemany

db_write("INSERT INTO my_table VALUES (?, ?)", [1, "value"])
db_executemany("INSERT INTO my_table VALUES (?, ?)", [(1, "a"), (2, "b")])
```

### Private — SQLite (per owner)

```python
from core.db.privateDB import get_private_session

session = get_private_session(owner_id)
try:
    char = session.query(Character).filter_by(character_id=owner_id).first()
finally:
    session.close()
```

### ORM Models (`core/db/models/`)

| Base | Model | Storage |
|---|---|---|
| `PublicBase` | `User`, `SiteAdmin` | DuckDB |
| `PrivateBase` | `Character` | SQLite per owner |

Domain tables (market_orders, structures, etc.) have **no ORM models** — DDL is owned by analysis collectors and written via raw DuckDB queries.

### Decentralised Table Ownership

Each collector or application **owns** the DDL for its tables via an `ensure_tables(con)` function.

| Table | Owner |
|---|---|
| `users`, `site_admins`, `user_roles` | `core/db/publicDB.py` |
| `scheduler_jobs` | `core/scheduler/db.py` |
| `structures` | `analysis/structures/discover.py` |
| `market_orders`, `market_region_cooldowns` | `analysis/market/regions.py` |
| `market_structures` | `analysis/market/structures.py` |
| `structures` cooldown columns | `analysis/market/structures.py` (`ensure_columns`) |
| `isk_per_hour_results` | `applications/isk_per_hour/worker.py` |
| `character_skills`, `character_wallet`, `character_assets` | `analysis/character/populate.py` |
| SDE dimension tables (`dim_types`, etc.) | `analysis/sde_loader.py` |
| `esi_routes`, `esi_schemas`, `esi_scopes` | `core/esi/registry.py` |

### Enrichment Pattern

When a collector adds columns to a table it does not own, use `ALTER TABLE ADD COLUMN IF NOT EXISTS` and cross-call the owning module's `ensure_tables` first:

```python
def ensure_columns(con) -> None:
    from analysis.structures.discover import ensure_tables as _ensure_structures
    _ensure_structures(con)
    con.execute("""
        ALTER TABLE structures ADD COLUMN IF NOT EXISTS my_col TIMESTAMP
    """)
```

---

## Making ESI Requests

**Never use `requests` directly.** All ESI HTTP must go through `core/queue/esi_req.py`.

```python
from core.queue.esi_req import esi_get, esi_post, esi_request

resp = esi_get("https://esi.evetech.net/latest/markets/10000002/orders/",
               params={"page": 1, "order_type": "all"})

# With auth header
resp = esi_request("GET", url, headers={"Authorization": f"Bearer {access_token}"})
```

Or via the typed generated client (preferred for well-typed calls):

```python
from core.esi.generated.client import execute_operation, fetch_all_pages

result = execute_operation("GetMarketsRegionIdOrders",
                           path_params={"region_id": 10000002},
                           query_params={"order_type": "all"})

all_orders = fetch_all_pages("GetMarketsRegionIdOrders",
                              path_params={"region_id": 10000002},
                              query_params={"order_type": "all"})
```

### Response Handling

```python
resp = esi_get(url, params=params)
if resp.status_code == 401:
    raise TokenExpiredError(...)       # stop using this token
if resp.status_code in (403, 404):
    return None                         # no access or not found — not retryable
if not resp.ok:
    logger.warning("ESI %s for %s", resp.status_code, url)
    return None
return resp.json()
```

### Pagination (X-Pages)

```python
resp = esi_get(url, params={**base_params, "page": 1})
total_pages = int(resp.headers.get("X-Pages", 1))
results = resp.json()
for page in range(2, total_pages + 1):
    r = esi_get(url, params={**base_params, "page": page})
    results.extend(r.json())
```

> See `_esi_docs/services/esi/pagination/` for cursor-based and from-id pagination schemes.

### Rate Limiting

The `esi_req.py` module automatically:

- Enforces a floating-window token bucket per `(rate_limit_group, app:character)` pair.
- Reads `X-Ratelimit-*` headers and adjusts dynamically.
- Backs off on `429` responses for `Retry-After` seconds.
- Tracks `X-ESI-Error-Limit-Remain` and logs a warning below 20.
- Caches ETags and sends `If-None-Match` on repeat requests (304 = 1 token instead of 2).

---

## Authentication & Tokens

### EVE SSO Flow

`core/web/auth.py` handles the OAuth 2.0 Authorization Code flow via `auth_bp`:

- `/login` — redirect to CCP's auth page with a CSRF `state` token
- `/callback` — validate `state`, exchange code for tokens, persist encrypted tokens
- `/logout` — clear session
- `/add_toon` — link additional characters to the same owner account
- `/switch_character/<int:character_id>` — change which character is "active"

CSRF protection: `OAuthStateCache` issues each `state` token once and consumes it on callback within a 5-minute window.

### Token Storage

`core/esi/auth.py` manages:

- `CredentialManager` — Fernet-encrypts and stores `client_id`/`client_secret` in `_publicData/client_cred`.
- `TokenDBManager` — stores per-character access/refresh tokens Fernet-encrypted in the owner's private SQLite `characters` table.

### Token Refresh

```python
from core.esi.auth import fresh_token, pick_token

# Pick any character token for an owner
char_id, token_data = pick_token(owner_id)

# Get a fresh (auto-refreshed) access token
char_id, fresh_data = fresh_token(owner_id, char_id, token_data)
access_token = fresh_data["access_token"]
```

### Role Hierarchy

| Principal | Access |
|-----------|--------|
| `site_owner` | Full unconditional access — bypasses all checks |
| `site_admin` | Full access — bypasses named-role checks |
| Regular user | Only tools whose role they hold |
| Unauthenticated | Only `minimum_level="public"` tools |

```python
from core.db.publicDB import get_user_roles, grant_user_roles, revoke_user_role

roles = get_user_roles(owner_id)                       # list[str]
grant_user_roles(owner_id, ["industry"], granted_by=admin_id)
revoke_user_role(owner_id, "isk_per_hour")
```

---

## Background Task Queue

```python
from core.queue import enqueue

task_id = enqueue("My Task", worker_fn, arg1, arg2, owner_id=owner_id, queue="public")
```

Two FIFO queues (`tq-pub` and `tq-prv`) run concurrently. Each queue is strictly serial (FIFO within the queue). `logging` calls and `print()` from worker threads are captured and streamed via SSE to `/stream/<task_id>`.

```python
from core.queue import get_task, cancel_task, get_all_tasks, clear_tasks

task = get_task(task_id)   # returns Task dataclass or None
cancel_task(task_id)       # signals pending task; running tasks complete normally
```

Use `queue="public"` for market data, SDE, and other public tasks. Use `queue="private"` (default) for per-owner character work.

---

## Scheduler

`core/scheduler/` runs a background thread (`_TICK_INTERVAL = 30s`) that fires jobs when their `next_run` is due. Job metadata is persisted in `scheduler_jobs` (DuckDB) so enabled/disabled state and intervals survive restarts.

### Job Catalog

All jobs are declared in `core/scheduler/jobs.py`. To add a new job, append an entry to `_build_catalog()`:

```python
try:
    from analysis.my_domain.worker import my_worker_fn
    jobs.append({
        "job_id": "my_domain_refresh",
        "label": "My Domain Refresh",
        "fn": my_worker_fn,
        "fn_path": _path(my_worker_fn),
        "interval_s": 3600,  # 1 hour
    })
except Exception:
    logger.warning("[SchedulerJobs] Could not import my_domain — skipping job")
```

The `try/except` guard prevents import errors in any one collector from blocking startup.

### Public Interface

```python
from core.scheduler import get_engine

engine = get_engine()
engine.list_jobs()              # list[dict]
engine.set_enabled("job_id", True)
engine.run_now("job_id")        # returns task_id (str)
```

Via the adapter (applications):

```python
from applications._adapters import scheduler

scheduler.list_jobs()
scheduler.set_enabled("market_refresh", False)
task_id = scheduler.run_now("character_refresh")
```

---

## Applications Layer

### Auto-Discovery

`applications/__init__.py` uses `pkgutil.iter_modules` to discover all sub-packages. Any package that exposes a module-level `Tool` attribute (a `BaseTool` instance) and does not start with `_` is auto-registered into the global `tool_registry`. Auto-registration happens on import — no manual registration step required.

### `ToolManifest` Fields

```python
ToolManifest(
    id="my_tool",             # URL-safe stable identifier
    name="My Tool",           # display name in sidebar
    icon="★",                 # single emoji/character
    description="...",        # one-line tooltip description
    url_prefix="/tools/my_tool",
    required_scopes=[],       # ESI scopes required (empty = no ESI auth needed)
    nav_weight=50,            # lower = higher in nav list
    nav_section="apps",       # "overview" | "tools" | "apps" | "admin" | "" (hidden)
    access_level="user",      # "public" | "user" | "admin" | "site_owner"
    required_role="my_tool",  # named role string, or None for level-only check
)
```

### Access-Control Decorators

```python
from applications._base import require_login, require_admin, require_role

@my_bp.route("/")
@require_role("my_tool")   # preferred — named role; admins bypass automatically
def index(): ...

@my_bp.route("/admin-only")
@require_admin             # site admin or site owner only
def admin_view(): ...

@my_bp.route("/any-user")
@require_login             # any authenticated user (no role check)
def user_view(): ...
```

Prefer `@require_role` on all new routes. Only use bare `@require_login` when genuinely any authenticated user should have access regardless of roles.

### `nav_section` Values

| Value | Sidebar Group |
|-------|--------------|
| `"overview"` | Overview (top of nav) |
| `"tools"` | Tools |
| `"apps"` | Apps (scope-gated if `required_scopes` is set) |
| `"admin"` | Admin |
| `""` | Hidden from nav entirely |

### Jinja2 and JavaScript

Templates inherit from `base.html` in `core/web/templates/`. Put JavaScript in `applications/<name>/static/` — never inline in templates. Pass data to JavaScript via `data-*` attributes on DOM elements:

```html
<div id="app-data" data-owner="{{ owner_id }}" data-task-id="{{ task_id }}"></div>
```

```javascript
const el = document.getElementById("app-data");
const ownerId = el.dataset.owner;
```

---

## Analysis / Collectors Layer

### Structure

```
analysis/<domain>/
  __init__.py    # re-export entry-point functions
  worker.py      # ensure_tables(), data collection functions
```

### Table Ownership Pattern

Every collector that writes to DuckDB must implement `ensure_tables(con)` and call it before any writes:

```python
import logging
from core.db import publicDB

logger = logging.getLogger(__name__)


def ensure_tables(con) -> None:
    """Idempotent DDL — safe to call multiple times."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS my_collector_data (
            record_id    BIGINT PRIMARY KEY,
            type_id      INTEGER,
            recorded_at  TIMESTAMP DEFAULT now()
        )
    """)


def collect_data() -> None:
    """Public entry point — called by scheduler or enqueue."""
    con = publicDB.connect()
    try:
        ensure_tables(con)
        # ... fetch from ESI and write ...
    finally:
        con.close()
```

### ESI Pagination in Collectors

```python
from core.queue.esi_req import esi_get

def _fetch_all_pages(url: str, base_params: dict) -> list:
    resp = esi_get(url, params={**base_params, "page": 1})
    if not resp.ok:
        return []
    results = resp.json()
    total = int(resp.headers.get("X-Pages", 1))
    for page in range(2, total + 1):
        r = esi_get(url, params={**base_params, "page": page})
        if r.ok:
            results.extend(r.json())
    return results
```

### Adding a New Collector to `analysis/__init__.py`

If the collector has a clean public interface, re-export it:

```python
# analysis/__init__.py
from analysis.my_domain.worker import collect_data as my_collect_data
```

Otherwise leave `analysis/__init__.py` alone — schedulers and routes import directly from the module.

---

## Plugin Framework

`core/plugin/` provides the base classes that wire infrastructure to applications.

### `BaseTool` and `ToolManifest`

`BaseTool` is the abstract base class every application tool must inherit. It:

1. Declares a class-level `manifest: ToolManifest`.
2. Overrides `create_blueprint() -> Blueprint`.

`ToolManifest` is a frozen dataclass carrying nav metadata, access level, and OAuth scope requirements.

`ToolRegistry` is the global singleton that collects all `BaseTool` instances and exposes them to the Flask app factory and sidebar renderer.

### Infrastructure Singletons (`applications/_adapters.py`)

All singletons live directly in `applications/_adapters.py` and are imported from `core.*` without an intermediate adapter layer.

| Singleton | Key Methods / Notes |
|-----------|--------------------|
| `db` | `query()`, `query_one()`, `scalar()`, `private_query()`, `market_price()`, `connect()` |
| `sde` | `core.sde` module — all SDE lookup functions |
| `raw_esi` | `get()`, `post()`, `request()` |
| `token_resolution` | `resolve_default_owner_id()`, `pick_token()`, `fresh_token()` |
| `esi` | `execute(op_id, ...)`, `fetch_pages(op_id, ...)` |
| `tokens` | `get(owner_id, character_ids=None)` |
| `tasks` | `enqueue(name, fn, *args, owner_id, queue)` |
| `char_data` | `get_character()`, `get_scopes()` |
| `esi_registry` | `get_status()` |
| `db_admin` | `list_tables()`, `query_sql()`, `list_users()`, `upsert_site_admin()`, … |
| `esi_manifest` | `get_operations()`, `get_operation(op_id)`, `get_meta()` |
| `queue_info` | `get_all_tasks()`, `get_task()`, `cancel_task()`, `rate_stream()`, `log_stream()` |
| `scheduler` | `list_jobs()`, `set_enabled()`, `run_now()` |

### Exposing New Core Functionality

No adapter class is needed. Add one import line to `applications/_adapters.py` and add the name to `__all__`:

```python
# applications/_adapters.py
from core.my_module import my_function  # ← one line

__all__ = [..., "my_function"]
```

Then use it in an application:

```python
from applications._adapters import my_function
```

---

## ESI Client & Code Generation

### `core/esi/generated/client.py`

```python
from core.esi.generated.client import execute_operation, fetch_all_pages

# Single call (auto-paginates if only one page)
result = execute_operation(
    "GetMarketsRegionIdOrders",
    path_params={"region_id": 10000002},
    query_params={"order_type": "all"},
)

# Fetch all pages explicitly
all_items = fetch_all_pages(
    "GetCharactersCharacterIdAssets",
    path_params={"character_id": 12345},
    token="Bearer <access_token>",
)
```

### Regenerating

```powershell
python build.py              # fetch spec + regenerate all generated packages
python build.py --force      # force regenerate even if spec is current
python build.py --spec-only  # only fetch the latest ESI OpenAPI spec
python build.py --gen-only   # only run core/esi/generated/ codegen, skip collector packages
python build.py --collectors # only regenerate core/esi/personal|corp|public/
python build.py --fullclean  # delete all data + generated files (including __pycache__), then exit
python build.py --date YYYY-MM-DD  # pin to a specific ESI compatibility date
```

> **Never hand-edit** `core/esi/generated/`, `core/esi/personal/`, `core/esi/corp/`, or `core/esi/public/`.

### Spec Registry (`core/esi/registry.py`)

Fetches and parses the ESI OpenAPI spec into `_publicData/esi_specs/<date>/` and populates the DuckDB tables `esi_routes`, `esi_schemas`, `esi_scopes`.

---

## Configuration

Runtime settings come from `config.yaml` (gitignored), loaded via `core.config.load_config()`. The `example.config.yaml` file is the annotated template. Key sections:

| Section | Purpose |
|---------|---------|
| `Runtime` | Flask host/port, debug mode, session secret |
| `Python Console` | Console log levels — `global_log_level`, `werkzeug_log_level`, plus any named logger |
| `Web Console` | `admin_panel_global_log_level` — threshold for the in-browser live log |
| `Environment Variables` | Language, data folder paths (written to `os.environ`) |
| `Auth` | `default_roles` granted to new users on first login |
| `SDE` | Toggle which SDE datasets load at startup |
| `Structures` | Cooldown durations for inaccessible structures |
| `Market` | Cooldown settings for market collection |

Access settings at runtime:

```python
from core.config import get_runtime_settings

settings = get_runtime_settings()
print(settings.web_port)     # int
print(settings.debug_mode)   # bool
```

---

## Security Rules

These rules are non-negotiable. Any code review must verify compliance:

1. **Never commit secrets** — `config.yaml`, `_publicData/key`, `_publicData/client_cred`, `_privateData/` are all gitignored. Never add them to source control.
2. **Never use `requests` directly** — all outbound ESI HTTP goes through `core.queue.esi_req`.
3. **Always use parameterised queries** — `con.execute("WHERE id = ?", [val])`. Never interpolate user input into SQL strings.
4. **Validate state on SSO callback** — `OAuthStateCache` must consume the token; duplicates must be rejected.
5. **Never log refresh tokens** — access tokens in debug log at `TRACE` level maximum; refresh tokens never.
6. **`client_secret` stays server-side** — never expose it in templates, JavaScript, or API responses.
7. **Fernet key rotation** — if `_publicData/key` is compromised, all stored tokens must be re-issued.
8. **Token 401 = stop, 403 = skip** — 401 means the token is expired (do not retry with the same token); 403 means access denied (not retryable at all).

---

## Common Tasks for AI Agents

This section provides step-by-step recipes for the most frequent contribution types. Follow these patterns precisely — the codebase has strict architectural constraints.

---

### Integrating a New Core Interface

Use this when you need to expose a new piece of core infrastructure to applications (e.g. a new database helper, a new external API function).

**Step 1 — Implement the functionality in `core/`.**

Decide which `core/` sub-module is the right home. Database-related helpers go in `core/db/publicDB.py`; ESI-related helpers go in `core/esi/`.

**Step 2 — Add an import to `applications/_adapters.py`.**

```python
from core.my_module import my_function

__all__ = [..., "my_function"]
```

No adapter class is needed. Applications then import it normally:

```python
from applications._adapters import my_function
```

If the function needs to be grouped under an existing namespace object (e.g. on `db.my_helper`) add it to the relevant `SimpleNamespace` or inline class in `_adapters.py`.

---

### Creating a New Analysis Collector

Use this when adding a new data-collection domain (new ESI endpoint family, new data type, etc.).

**Step 1 — Create the package.**

```
analysis/my_domain/
  __init__.py
  worker.py
```

**Step 2 — Implement `ensure_tables` and the entry point in `worker.py`.**

```python
# analysis/my_domain/worker.py
import logging
from core.db import publicDB
from core.queue.esi_req import esi_get

logger = logging.getLogger(__name__)


def ensure_tables(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS my_domain_data (
            id          BIGINT PRIMARY KEY,
            type_id     INTEGER NOT NULL,
            value       DOUBLE,
            fetched_at  TIMESTAMP DEFAULT now()
        )
    """)


def fetch_my_domain_data() -> None:
    """Collect data and write to DuckDB. Called by scheduler or manually."""
    con = publicDB.connect()
    try:
        ensure_tables(con)
        resp = esi_get("https://esi.evetech.net/latest/my/endpoint/")
        if not resp.ok:
            logger.warning("ESI %s fetching my_domain", resp.status_code)
            return
        rows = [(item["id"], item["type_id"], item["value"]) for item in resp.json()]
        con.executemany("INSERT OR REPLACE INTO my_domain_data VALUES (?, ?, ?, now())", rows)
    finally:
        con.close()
```

**Step 3 — Re-export from `analysis/my_domain/__init__.py`.**

```python
from analysis.my_domain.worker import fetch_my_domain_data
```

**Step 4 — Register a scheduled job** (if the collection should run on a schedule).

See [Registering a New Scheduled Job](#registering-a-new-scheduled-job) below.

**Step 5 — Optionally enqueue from an application route.**

```python
from applications._adapters import tasks
from analysis.my_domain.worker import fetch_my_domain_data

task_id = tasks.enqueue("My Domain Refresh", fetch_my_domain_data, queue="public")
```

---

### Creating a New Application

Use this to add a new user-facing web tool to the dashboard.

**Step 1 — Create the package directory.**

```
applications/my_tool/
  __init__.py
  routes.py
  templates/
    my_tool.html
  static/
    my_tool.js   (optional)
```

**Step 2 — Write `__init__.py`.**

```python
from applications._base import BaseTool, ToolManifest
from applications.my_tool import routes


class MyTool(BaseTool):
    manifest = ToolManifest(
        id="my_tool",
        name="My Tool",
        icon="★",
        description="One-sentence description.",
        url_prefix="/tools/my_tool",
        required_scopes=[],
        nav_weight=60,
        nav_section="apps",
        access_level="user",
        required_role="my_tool",
    )

    def create_blueprint(self):
        return routes.my_bp


Tool = MyTool()
```

Set `required_role=None` if no named role is required (access_level check only). `access_level` values: `"public"` | `"user"` | `"admin"` | `"site_owner"`.

**Step 3 — Write `routes.py`.**

```python
from flask import Blueprint, render_template
from applications._base import base_ctx, require_role
from applications._adapters import db, sde

my_bp = Blueprint("my_tool", __name__,
                  template_folder="templates",
                  static_folder="static")


@my_bp.route("/")
@require_role("my_tool")
def index():
    return render_template("my_tool.html", **base_ctx("my_tool"))
```

**Step 4 — Write the template.**

```html
{% extends "base.html" %}
{% block title %}My Tool{% endblock %}
{% block content %}
<div class="pg-hd"><h1>My Tool</h1></div>
<div class="pg-body">
  <!-- content here -->
</div>
{% endblock %}
{% block scripts %}
<script src="{{ url_for('my_tool.static', filename='my_tool.js') }}"></script>
{% endblock %}
```

**Step 5 — Verify auto-discovery.**

Start the server. Your tool should appear in the sidebar under the declared `nav_section`. Check the admin panel or Flask startup logs for any import errors. The `Tool = MyTool()` line **must** execute at import time without error.

**Step 6 — Add the new role to `example.config.yaml`.**

Document the new role name in `example.config.yaml` under the `Auth` section comment so site admins know to add it to `default_roles` if desired.

---

### Registering a New Scheduled Job

**Step 1 — Open `core/scheduler/jobs.py`.**

Find `_build_catalog()`. Add a new try/except block:

```python
try:
    from analysis.my_domain.worker import fetch_my_domain_data
    jobs.append({
        "job_id": "my_domain_refresh",           # stable — changing this creates a new DB row
        "label": "My Domain Data Refresh",
        "fn": fetch_my_domain_data,
        "fn_path": _path(fetch_my_domain_data),
        "interval_s": 3600,                       # default interval in seconds
    })
except Exception:
    logger.warning("[SchedulerJobs] Could not import my_domain — skipping job")
```

The `try/except` guard is mandatory — it prevents import failures in any collector from blocking startup.

**Step 2 — Restart the server.**

`register_all_jobs(engine)` is called from `core/web/__init__.py` (inside `create_app`) during startup. The new job row will be upserted into `scheduler_jobs` and visible in the Scheduler admin panel (`/admin/scheduler`).

---

### Updating the README

The README (`README.md`) is the primary public-facing document. It should always reflect the **current state** of the codebase — not aspirational or historical state.

**When to update the README:**

- After adding a new application (add it to the Built-In Applications table)
- After adding a new analysis collector (update the architecture overview)
- After adding a new configuration option (update the Configuration Reference)
- After changing any URL prefix, role name, or access level
- After adding a new scheduled job
- After any structural change to `core/` or `analysis/`

**How to gather changes since the last README update:**

1. Check the git log for commits since the last README modification:
   ```powershell
   git log --oneline -- README.md     # find the last README commit hash
   git log --oneline <hash>..HEAD     # all commits since then
   ```
2. For each commit, inspect the diff:
   ```powershell
   git show <commit-hash> --stat      # what files changed
   git show <commit-hash>             # full diff
   ```
3. Read the changed files in the current workspace to understand the current state.
4. Update only the sections of the README that are affected — do not rewrite sections that are still accurate.

**README structure to preserve:**

The README has a user-facing-first structure: Installation → First-Run Setup → Dashboard → Site Admin → Config → Apps → Scheduler → Architecture → Developer guides → Security → Licensing. Do not move developer content above the user-facing sections.

**Do not add** timestamp annotations, "Last updated" headers, or change logs to the README. The git history is the changelog.

---

### Keeping AGENTS.md Accurate

**Do not modify `AGENTS.md` yourself.** If you identify an inaccuracy or missing section, relay the specific proposed change to the user with a clear explanation of what is wrong and what the correct content should be. The user will decide whether and how to update it.

This rule exists because `AGENTS.md` is the authoritative guide for all contributors — including future AI agents. An agent silently "correcting" this file based on its own understanding could introduce errors that propagate to all future work.

If you are asked to update `AGENTS.md` explicitly by the user, make targeted edits — do not rewrite sections that are still accurate.

---

*See also `_esi_docs/` for full ESI API documentation, and `README.md` for user-facing installation and usage instructions.*
