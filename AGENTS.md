# EVE Data Framework — Agent Guide

This document is the primary reference for AI agents (and humans) working inside this repository.
Read this before modifying any file.

> **For agents:** `_esi_docs/` contains the full official ESI documentation — rate limiting, pagination,
> best practices, SSO, and more. **Always consult `_esi_docs/` before writing or reviewing any ESI-related code.**
> Start with `_esi_docs/services/esi/` for API behaviour and `_esi_docs/services/sso/` for auth.

---

## Repository Overview

**EVE Data Framework** is a self-hosted Flask web application that interfaces with the EVE Online ESI REST API. It provides a web dashboard, EVE SSO authentication, a DuckDB public warehouse (SDE + market/structure data), per-character private SQLite databases, and a background task queue with live SSE log streaming.

The codebase is organised into clean architectural layers:

| Layer | Package | Purpose |
|---|---|---|
| **Core** | `core/` | Infrastructure: DB connections, ESI wrappers, SDE caches, task queue, plugin framework |
| **Analysis** | `analysis/` | Data-collection workers: market, structures, SDE pipeline, character data ingestion |
| **Applications** | `applications/` | User-facing tools (market browser, industry calc, ISK/hr) — auto-discovered via pkgutil |
| **Web** | `core/web/` | Flask app factory, SSO auth, Jinja2 templates |
| **Config** | `config.py` / `config.yaml` | Runtime settings, environment variables, SDE toggles |
| **Entry** | `main.py` | Startup: load SDE, ensure public DB, start Flask |
| **Codegen** | `codegen/` | ESI client codegen + domain collector codegen |

### Forwarding Shims

Legacy import paths (`db/`, `esi/`, `sde.py`, `tasks/`, `workers/`) are thin forwarding shims that re-export from `core/` or `analysis/`. New code should import from `core.*` or `analysis.*` directly.

### Tech Stack

- **Python 3.12+** — all async-free; threading via `ThreadPoolExecutor`
- **Flask** — web server, thread-safe, `threaded=True`
- **SQLAlchemy** — ORM; SQLite per character; `PublicBase`/`PrivateBase` declarative bases
- **DuckDB** — single shared public store (SDE, market orders, structures, ESI spec metadata)
- **requests** — all HTTP; wrapped by `core/queue/esi_req.py` (rate limiter)
- **`config.yaml`** — runtime configuration; loaded once at startup

### Key Environment Variables (set via `config.yaml`)

| Variable | Default | Meaning |
|---|---|---|
| `PUBLIC_DATA_FOLDER` | `_publicData` | DuckDB file + OAuth credential files |
| `EVE_PRIVATE_DATABASE_FOLDER` | `_privateData/` | Per-owner SQLite root |
| `SDE_PATH` | `_sde/` | Local SDE YAML files |
| `LANGUAGE` | `en` | Primary language for SDE text fields |
| `SUPPORTED_LANGUAGES` | `en` | Comma-separated list; SDE pruner keeps only these |

---

## Directory Map

```
main.py                  # startup: load SDE, ensure public DB, start Flask
config.py                # load_config(), RuntimeSettings, ensure_dependencies()
config.yaml              # configuration toggles
requirements.txt         # pip dependencies
build.py                 # refresh ESI spec + regenerate codegen packages

core/                    # ── INFRASTRUCTURE ──────────────────────────────────
  db/
    __init__.py          # ensure_schema(), warm_caches(), initialize_all()
    publicDB.py          # DuckDB: connect(), ensure_public_database(), CRUD helpers
    privateDB.py         # SQLite per owner: initialize_private_database(), get_private_session()
    models/
      __init__.py        # re-exports: PublicBase, PrivateBase, User, SiteAdmin, Character
      identity.py        # User, SiteAdmin (DuckDB ORM), Character (SQLite ORM)
  esi/
    __init__.py
    auth.py              # OAuth token storage (Fernet-encrypted), refresh helpers
    registry.py          # fetch_openapi_spec(), refresh_esi_spec_registry()
  queue/
    __init__.py
    esi_req.py           # esi_request(), esi_get(), esi_post() — ALL ESI HTTP goes here
    manager.py           # enqueue(), get_task(), cancel_task(), ThreadPoolExecutor queues
  sde/
    __init__.py          # startup_load_sde(), refresh_all_caches(), lookup helpers
    cache.py             # in-memory SDE caches: name_from_type_id, region_id_from_system_id, etc.
  plugin/
    __init__.py
    base.py              # BaseTool, ToolManifest (access_level, required_role, nav_section), ToolRegistry
    ports.py             # DELETED — Protocol stubs removed; adapters are the interface
    adapters.py          # singletons: db, sde, raw_esi, token_resolution, esi, tokens, tasks, etc.
    web.py               # re-exports: base_ctx, require_login, require_admin, require_role
  web/                   # ── WEB FRAMEWORK ───────────────────────────────────
    __init__.py          # Flask app factory: create_app() — registers auth_bp + tool_registry
    app.py               # start_webUI(settings) — entry point called by main.py
    auth.py              # EVE SSO OAuth2 flow (auth_bp) + require_login / require_admin / require_role decorators
    context.py           # base_ctx(active_page) — sidebar template context helper
    templates/           # Shared base template only (base.html)

analysis/                # ── DATA COLLECTION ─────────────────────────────────
  __init__.py
  sde_loader.py          # SDE pipeline: download → unzip → prune → build DuckDB warehouse
  character/
    __init__.py           # re-exports: populate_all
    populate.py           # per-character ESI → private SQLite (skills, wallet, assets)
  market/
    __init__.py           # re-exports: fetch_all_market_data, update_structure_market_orders
    publicRegions.py      # NPC station market orders — owns market_orders, market_region_cooldowns
    privateStructures.py  # player-structure market orders — owns market_structures, enriches structures
  structures/
    __init__.py           # re-exports: discover_structures
    publicDiscovery.py    # discover + enrich public structures — owns structures table

applications/            # ── USER-FACING TOOLS ───────────────────────────────
  __init__.py            # pkgutil auto-discovery of Tool instances
  _base.py               # re-exports: BaseTool, ToolManifest, base_ctx, require_login, require_admin
  _adapters.py           # re-exports adapter singletons from core.plugin.adapters
  _ports.py              # DELETED — no production usage
  dashboard/             # nav_section="overview" — character overview; templates/ has dashboard.html; auth.json: role="dashboard"
  queue_viewer/          # nav_section="tools"    — task progress + ESI rate SSE; auth.json: role="queue"
  admin_panel/           # nav_section="admin"    — logs, stats, user mgmt; auth.json: minimum_level="admin"
  db_browser/            # nav_section="admin"    — DuckDB/SQLite browser; auth.json: minimum_level="admin"
  esi_browser/           # nav_section="admin"    — ESI operation explorer; auth.json: minimum_level="admin"
  market_browser/        # nav_section="apps"     — browse live market orders; auth.json: role=null, minimum_level="public"
  industry_calculator/   # nav_section="apps"     — manufacturing cost calculator; auth.json: role="industry"
  isk_per_hour/          # nav_section="apps"     — ISK/hr rankings; auth.json: role="isk_per_hour"

codegen/                 # ── CODE GENERATION ─────────────────────────────────
  esi_codegen.py         # generates core/esi/generated/ package from ESI OpenAPI spec
  domain_codegen.py      # generates core/esi/personal|corp|public/ packages

# ── FORWARDING SHIMS (legacy import paths — all removed) ────────────────────
db/                      # DELETED — use core.db
esi/                     # DELETED — use core.esi / core.queue
sde.py                   # DELETED — use core.sde
tasks/                   # DELETED — use core.queue
workers/                 # DELETED — use core.esi.auth + analysis
web/                     # DELETED — use core.web
utils/build/             # → codegen

# ── DATA DIRECTORIES ────────────────────────────────────────────────────────
_sde/                    # local SDE YAML files
_publicData/
  public.duckdb          # DuckDB warehouse
  client_cred            # Fernet-encrypted OAuth credentials  [NEVER COMMIT]
  key                    # Fernet symmetric key                [NEVER COMMIT]
  esi_specs/             # cached ESI OpenAPI spec snapshots
_privateData/<owner_id>/
  <owner_id>.db          # per-character SQLite                [NEVER COMMIT]
```

---

## Decentralised Table Ownership

Each collector (or application) **owns** the DDL for its tables via an `ensure_tables(con)` function. Core infrastructure (`core/db/publicDB._ensure_public_schema`) only creates identity tables (`users`, `site_admins`, `user_roles`) and views.

| Table | Owner |
|---|---|
| `users`, `site_admins`, `user_roles` | `core/db/publicDB.py` |
| `structures` | `analysis/structures/publicDiscovery.py` |
| `market_orders`, `market_region_cooldowns` | `analysis/market/publicRegions.py` |
| `market_structures` | `analysis/market/privateStructures.py` |
| `structures` cooldown columns | `analysis/market/privateStructures.ensure_columns()` |
| `isk_per_hour_results` | `applications/isk_per_hour/worker.py` |
| `character_skills`, `character_wallet`, `character_assets` | `analysis/character/populate.py` |
| SDE dimension tables | `analysis/sde_loader.py` (_bootstrap_schema) |

### Enrichment Pattern

When a collector needs to add columns to a table it doesn't own, it uses `ensure_columns(con)` with `ALTER TABLE ADD COLUMN IF NOT EXISTS`. Before adding columns, it cross-calls the owning collector's `ensure_tables(con)` to guarantee the base table exists:

```python
def ensure_columns(con) -> None:
    from analysis.structures.publicDiscovery import ensure_tables as _ensure_structures
    _ensure_structures(con)
    con.execute("ALTER TABLE structures ADD COLUMN IF NOT EXISTS forbidden_until TIMESTAMP")
```

### Adding a New Analysis Domain

1. Create `analysis/<domain>/` with `__init__.py` and worker modules.
2. Add `ensure_tables(con)` — idempotent DDL using `CREATE TABLE IF NOT EXISTS`.
3. Call `ensure_tables` at the top of each worker function before any writes.
4. Use `core.plugin.adapters` for shared operations — `raw_esi` for ESI HTTP, `sde` for SDE lookups, `token_resolution` for auth. Only use `core.db.publicDB` directly for owned-table DDL and writes.
5. Enqueue via `core.queue.manager.enqueue("Task Name", worker_fn, ...)`.

---

## Making ESI Requests

**Never use `requests` directly.** All ESI HTTP must go through `core/queue/esi_req.py`:

```python
from core.queue.esi_req import esi_request, esi_get, esi_post

resp = esi_get(url, params={"datasource": "tranquility"})
resp = esi_request("GET", url, headers={"Authorization": f"Bearer {token}"})
```

Or use the auto-generated typed client:

```python
from core.esi.generated.client import execute_operation
result = execute_operation("GetCharactersCharacterId", character_id=12345, token=access_token)
```

### Response Handling

```python
resp = esi_request("GET", url, headers=headers)
if resp.status_code == 401:
    raise _TokenExpired(...)    # stop using this token
if resp.status_code in (403, 404):
    return None                  # no access or not found
if not resp.ok:
    logger.warning("HTTP %s for %s", resp.status_code, url)
    return None
return resp.json()
```

### Pagination

ESI offers three pagination schemes. See `_esi_docs/services/esi/pagination/` for the canonical docs.

#### X-Pages (most routes)

```python
resp = esi_get(url, params={**base_params, "page": 1})
total_pages = int(resp.headers.get("X-Pages", 1))
results = resp.json()
for page in range(2, total_pages + 1):
    r = esi_get(url, params={**base_params, "page": page})
    results.extend(r.json())
```

> **Cache caveat**: if the `Expires` time elapses mid-fetch, page 1 may regenerate and overlap with later pages. Check how close page 1 is to expiry before fetching the full set.

#### Cursor-based (select routes, use for polling)

Tokens are **opaque server-generated bookmarks** — never decode or construct them.

```python
# --- initial full backfill ---
results = []
resp = esi_get(url)          # no pagination params on first call
while True:
    data = resp.json()
    cursor = data.get("cursor", {})
    results.extend(data["items"])   # field name varies by route
    before_token = cursor.get("before")
    after_token = cursor.get("after")   # save this for polling
    if not before_token or not data["items"]:
        break
    resp = esi_get(url, params={"before": before_token})

# --- subsequent polling for new/changed records ---
# Use the last `after_token` saved above; stop when the page is empty.
resp = esi_get(url, params={"after": after_token})
new_items = resp.json().get("items", [])
```

Records are ordered by `last_modified` ascending; `after` returns newer records, `before` returns older ones. Tokens remain valid indefinitely.

#### From-id (wallet/journal routes — historical, backward only)

```python
results = []
resp = esi_get(url)          # most recent records first
while True:
    page_data = resp.json()
    if not page_data:
        break
    results.extend(page_data)
    last_id = page_data[-1]["id"]    # field is usually transaction_id / id
    resp = esi_get(url, params={"from_id": last_id})
    # Stop when the only record returned is the from_id record itself
    if len(resp.json()) <= 1:
        break
```

Navigates **backwards in time only** (oldest record last). The `from_id` record itself is always included in the response.

---

## ESI Services Reference

> **All ESI behaviour is documented in `_esi_docs/`.** When in doubt — rate limits, pagination schemes,
> caching rules, error handling, SSO flow — read the source docs before writing code.
> Key paths: `_esi_docs/services/esi/` (API), `_esi_docs/services/sso/` (auth), `_esi_docs/guides/` (formulae & concepts).

### Versioning

Every ESI request can include an `X-Compatibility-Date` header (ISO date, `YYYY-MM-DD`). This pins the API behaviour to the spec as it existed on that date, protecting against silent breaking changes.

- Compute the current API date as `now() − 11 h` (the spec rolls over at 11:00 UTC).
- If custom headers cannot be set, the `compatibility_date` query parameter does the same job.
- Dates in the future are rejected; there is also a minimum floor (oldest available version).

### User-Agent

All ESI requests **must** carry a `User-Agent` header. `esi_req.py` automatically injects `User-Agent: EVE-Data-Framework/4.0` when the caller does not supply one. For browser environments use `X-User-Agent`; when headers are unavailable entirely, the `user_agent` query parameter is accepted.

Recommended format: `AppName/1.2.3 (contact@email; +https://github.com/repo)`

### Caching

ESI is a cache-aware API. Circumventing the cache can result in a ban.

| Header | Meaning |
|--------|---------|
| `Expires` | Earliest time new data will be available — do not re-fetch before this. |
| `Last-Modified` | When the cached resource was last updated. |
| `ETag` | Hash of the response body. Send back as `If-None-Match` on repeat requests. |

`esi_req.py` stores `ETag` values in its in-process cache and automatically injects `If-None-Match` on subsequent requests to the same URL. A `304 Not Modified` response (1 token) refreshes the cache TTL and returns the stored payload — cheaper than a full `200` reply (2 tokens).

### Rate Limiting

ESI uses a **floating-window token bucket** per `(rate_limit_group, applicationID:characterID)` pair. Tokens consumed by a request are released back to the bucket after the window expires.

| Status | Token cost | Notes |
|--------|-----------|-------|
| 2XX    | 2 tokens  | |
| 3XX    | 1 token   | Promotes `If-None-Match` / `If-Modified-Since` usage |
| 4XX    | 5 tokens  | Excludes 429 responses |
| 5XX    | 0 tokens  | Server errors do not penalise the caller |

**Rate-limit response headers** (present on routes with bucket-limiting enabled):

| Header | Format | Meaning |
|--------|--------|---------|
| `X-Ratelimit-Group` | string | Route group identifier |
| `X-Ratelimit-Limit` | `150/15m` | Total tokens / window size |
| `X-Ratelimit-Remaining` | integer | Tokens remaining in current window |
| `X-Ratelimit-Used` | integer | Tokens consumed by this request |
| `Retry-After` | seconds | Present on 429; how long to wait before retrying |

`esi_req.py` reads these headers, dynamically configures named per-group buckets, and backs off automatically on 429. The `get_stats()` call on the global limiter returns per-group snapshots.

Best practices:
- Do not operate at the limit — leave headroom.
- If `X-Ratelimit-Remaining` nears zero, start slowing down.
- Spread periodic requests over time; avoid `*/5`-style cron bursts.
- Respect `Expires` to avoid redundant requests.

### Error Limit (separate from rate limiting)

ESI enforces a **fixed-window error limit** independently of the per-group bucket: at most **100 non-2xx/3xx responses per minute** across all routes. Once breached, every route returns `420` until the window resets.

The error-limit headers are **mutually exclusive** with the rate-limit headers above — a response carries one set or the other, never both.

| Header | Meaning |
|--------|---------|
| `X-ESI-Error-Limit-Remain` | Non-error responses still allowed this window |
| `X-ESI-Error-Limit-Reset` | Seconds until the error window resets |

`esi_req.py` reads these on every response, logs a `WARNING` when `Remain` drops below 20, and exposes `error_limit_remain` / `error_limit_reset` in `get_stats()`. On a `420` response it sleeps for `X-ESI-Error-Limit-Reset` seconds before retrying (up to `max_retries`).

### SSO (OAuth 2.0)

Authorization Code flow. Token handling: `core/esi/auth.py`. Tokens are Fernet-encrypted at rest.

**Security rules:**
- Verify `state` parameter on every callback (CSRF protection)
- Never log `refresh_token`
- `client_secret` stays server-side only

---

## Database Architecture

### Public — DuckDB (`_publicData/public.duckdb`)

```python
from core.db.publicDB import connect
con = connect()
try:
    rows = con.execute("SELECT type_id, name_en FROM dim_types WHERE type_id = ?", [34]).fetchall()
finally:
    con.close()
```

Get a fresh connection per thread — DuckDB connections are not thread-safe.

### Private — SQLite (per owner)

```python
from core.db.privateDB import get_private_session
session = get_private_session(owner_id)
try:
    char = session.query(Character).filter_by(character_id=owner_id).first()
finally:
    session.close()
```

### Models (`core/db/models/`)

| Base | Model | Storage |
|---|---|---|
| `PublicBase` | `User`, `SiteAdmin` | DuckDB |
| `PrivateBase` | `Character` | SQLite per owner |

Domain tables (market_orders, structures, etc.) have no ORM models — DDL is owned by collectors and written via raw DuckDB queries.

---

## Background Tasks & SSE

```python
from core.queue.manager import enqueue
task_id = enqueue("My Task", worker_fn, arg1, queue="public")
```

Two FIFO queues (public + private) run concurrently. `logging` and `print()` inside workers are captured and streamed via SSE to `/stream/<task_id>`.

---

## Applications (Auto-Discovery)

Applications are auto-discovered via `pkgutil` in `applications/__init__.py`. Each sub-package exposes a `Tool` attribute (an instance of `BaseTool`) and a Flask `Blueprint`.

### `access_level` values

The `ToolManifest.access_level` field controls the **minimum privilege** required to see and use a tool:

| Value | Visibility |
|-------|-----------|
| `"public"` | No login required |
| `"user"` | Logged-in users — further gated by `required_role` if set |
| `"admin"` | Site admin or site owner |
| `"site_owner"` | Site owner only |

These values are set automatically from each application's `auth.json` — do not hard-code them in `ToolManifest` constructors.

### Role-Based Access Control (`auth.json`)

Every application package contains an `auth.json` file that defines its access requirements. `BaseTool.__init__` reads this file automatically when the `Tool` singleton is instantiated:

```json
// auth.json schema
{
  "role": "my_role",    // named role users must hold (null = no role required)
  "minimum_level": "user" // access_level value: "public" | "user" | "admin" | "site_owner"
}
```

**Role hierarchy:**

| Principal | Access |
|-----------|--------|
| `site_owner` | Full access — bypasses all role and level checks |
| `site_admin` | Full access — bypasses named-role checks |
| Regular user | Access only to tools whose role they hold |
| Unauthenticated | Only `minimum_level="public"` tools |

**Default roles** for new users are configured in `config.yaml`:

```yaml
Auth:
  default_roles: [dashboard, queue]
```

Roles are stored in the `user_roles` DuckDB table. Helpers:

```python
from core.db.publicDB import get_user_roles, grant_user_roles, revoke_user_role

roles = get_user_roles(owner_id)                        # list[str]
grant_user_roles(owner_id, ["industry"], granted_by=admin_id)
revoke_user_role(owner_id, "isk_per_hour")
```

### `nav_section` values

The `ToolManifest.nav_section` field controls **where** the tool appears in the sidebar:

| Value | Sidebar group |
|-------|-----------|
| `"overview"` | Overview group (e.g. Dashboard) |
| `"tools"` | Tools group (e.g. Task Queue) |
| `"apps"` | Apps group; scope-gated if `required_scopes` is set |
| `"admin"` | Admin group |
| `""` | Hidden from nav (background workers, no UI entry point) |

`access_level` and `nav_section` are independent — an app can be in any nav group with any access level.

### Import Discipline

Applications must **never** import from `core.*` directly. All framework access goes through:

- **`applications._base`** — `BaseTool`, `ToolManifest`, `base_ctx`, `require_login`, `require_admin`, `require_role`
- **`applications._adapters`** — adapter singletons: `db`, `sde`, `raw_esi`, `token_resolution`, `esi`, `tokens`, `tasks`, `char_data`, `esi_registry`, `db_admin`, `esi_manifest`, `queue_info`, `scheduler`
- **`applications._ports`** — DELETED

This keeps a clean architectural boundary between the application and infrastructure layers.

### Adding a new application

1. Create `applications/<name>/` with `__init__.py`, `routes.py`, `templates/`, `static/`, optional `worker.py`.
2. Create `applications/<name>/auth.json` declaring the role and minimum access level.
3. Define a class inheriting `BaseTool` with a `ToolManifest` and `create_blueprint()`. Do **not** set `access_level` or `required_role` in the manifest — they are loaded from `auth.json` automatically.
4. Put your Jinja2 templates in `applications/<name>/templates/`. They inherit from `base.html` (shared in `core/web/templates/`).
5. Put JavaScript in `applications/<name>/static/`. Reference via `{{ url_for('<bp_name>.static', filename='<name>.js') }}` in a `{% block scripts %}` block.
6. Set `Tool = YourTool()` as a module-level attribute in `__init__.py`.
7. The application will be auto-registered on import.

```python
# applications/my_tool/__init__.py
from applications._base import BaseTool, ToolManifest
from applications.my_tool import routes

class MyTool(BaseTool):
    manifest = ToolManifest(
        id="my_tool", name="My Tool", icon="★",
        description="Does something useful.",
        url_prefix="/tools/my_tool",
        required_scopes=[],
        nav_weight=10,
        nav_section="apps",
        # access_level and required_role are set from auth.json — omit here
    )
    def create_blueprint(self):
        return routes.my_bp

Tool = MyTool()
```

```json
// applications/my_tool/auth.json
{
  "role": "my_tool",
  "minimum_level": "user"
}
```

```python
# applications/my_tool/routes.py
from flask import Blueprint, render_template
from applications._base import base_ctx, require_login
from applications._adapters import db, sde

my_bp = Blueprint("my_tool", __name__, template_folder="templates", static_folder="static")

@my_bp.route("/")
@require_login
def index():
    return render_template("my_tool.html", **base_ctx("my_tool"))
```

```html
{# applications/my_tool/templates/my_tool.html #}
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

JavaScript goes in `applications/<name>/static/` — never inline in templates. For Jinja2 data the JS needs,
use `data-*` attributes on a DOM element and read them in the external `.js` file.

### Access-control decorators

```python
from applications._base import require_login, require_admin, require_role

@my_bp.route("/")
@require_login          # any authenticated user
def index(): ...

@my_bp.route("/")
@require_role("my_tool") # authenticated user with the named role (admins bypass)
def index(): ...

@my_bp.route("/admin")
@require_admin          # site admin or site owner only
def admin_view(): ...
```

Prefer `@require_role` over `@require_login` for all new routes — it enforces named-role access and still allows admins through.

---

## Regenerate the ESI Client

```powershell
python build.py              # fetch spec + regenerate core/esi/generated/ + domain wrappers
python build.py --force      # force regenerate
python build.py --spec-only  # only fetch spec
python build.py --collectors # only regenerate core/esi/personal|corp|public/ packages
```

**Do not hand-edit `core/esi/generated/` or `core/esi/personal|corp|public/`** — changes are overwritten on next codegen run.

---

## Code Conventions

- **All ESI HTTP → `esi_request` / `esi_get` / `esi_post`** (via `core.queue.esi_req` or `raw_esi` adapter)
- **Applications import from `applications._base` / `applications._adapters`** — never `core.*` directly
- **Analysis workers use adapters for shared ops** — ESI HTTP (`raw_esi`), SDE lookups (`sde`), auth/token resolution (`token_resolution`) go through `core.plugin.adapters`; only owned-table DDL and writes use `core.db.publicDB` directly
- **New code imports from `core.*` / `analysis.*`** — not from legacy shim paths
- **Logging**: `logger = logging.getLogger(__name__)` — not bare `print()` in production
- **Token handling**: 401 = expired token (stop); 403 = no permission (not retryable)
- **Thread safety**: `threading.Lock()` for shared state; fresh `connect()` per thread
- **No raw SQL with user input** — parameterised `con.execute("WHERE id = ?", [val])`
- **Do not edit auto-generated packages** — `core/esi/generated/`, `core/esi/personal/`, `core/esi/corp/`, `core/esi/public/`
- **Table DDL belongs to analysis workers** — never add domain table DDL to `core/db/publicDB.py`
- **Access control via `@require_role`** — prefer `@require_role("role")` over `@require_login` for any route gated on a named role; use `@require_admin` only for admin-only routes; never use bare `@require_login` for new application routes
- **Do not set `access_level` or `required_role` in `ToolManifest` directly** — define them in `auth.json` and let `BaseTool._load_auth_config()` read them on instantiation

---

## Security Notes

- `_publicData/key` — Fernet symmetric key. **Never commit.**
- `_publicData/client_cred` — encrypted OAuth credentials. **Never commit.**
- `_privateData/` — per-user SQLite databases. **Never commit.**
- All three paths are in `.gitignore`.
- CSRF: SSO callback validates `state` via time-limited `OAuthStateCache`.
- No user-supplied strings interpolated into SQL — use parameterised queries.