# EVE Data Framework — Agent Guide

This document is the primary reference for AI agents (and humans) working inside this repository.
Read this before modifying any file.

---

## Repository Overview

**EVE Data Framework** is a self-hosted Flask web application that interfaces with the EVE Online ESI REST API. It provides a web dashboard, EVE SSO authentication, a DuckDB public warehouse (SDE + market/structure data), per-character private SQLite databases, and a background task queue with live SSE log streaming. The data **collection layer** (corp/personal ESI collectors and analysis modules) is not yet implemented; the current codebase is the infrastructure foundation on which collectors will be built.

| Layer | Purpose |
|---|---|
| `main.py` | Entry point — initialises SDE, starts Flask server |
| `config.py` | Runtime settings, config loading, dependency checks |
| `config.yaml` | Environment variables + SDE toggle flags |
| `esi/` | Rate limiter, auth, spec registry, auto-generated client package |
| `db/` | SQLAlchemy models, session factories, SDE store, SDE facade |
| `tasks/` | Background task queue with live SSE log streaming |
| `build/` | SDE bootstrap, warehouse loader, ESI codegen, collector codegen |
| `webUI/` | Flask blueprints, SSE streaming, Jinja2 templates |
| `workers/` | Background ESI data collection workers |
| `_sde/` | Local copy of the EVE Static Data Export (YAML) |
| `_publicData/` | DuckDB public database (`public.duckdb`), OAuth credentials, ESI spec cache |
| `_privateData/<owner_id>/` | Per-owner SQLite databases |

### Tech Stack

- **Python 3.12+** — all async-free; threading via `ThreadPoolExecutor`
- **Flask** — web server, thread-safe, `threaded=True`
- **SQLAlchemy** — ORM; SQLite per character; `PublicBase` models exist but DuckDB writes bypass the ORM
- **DuckDB** — the single shared public store (SDE types/groups/universe, market orders, structures, ESI spec metadata)
- **requests** — all HTTP; wrapped by `esi/rate_limiter.py`
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

esi/
  rate_limiter.py        # ALL HTTP to ESI goes through esi_request()/esi_get()/esi_post()
  auth.py                # OAuth token storage (Fernet-encrypted), refresh helpers
  spec_registry.py       # fetch_openapi_spec() / refresh_esi_spec_registry() / get_registry_status()
  client/                # AUTO-GENERATED — do not edit by hand
    __init__.py          # package marker + version/compatibility check
    manifest.py          # OPERATIONS dict (208 ops), ALL_SCOPES, COMPATIBILITY_DATE
    client.py            # execute_operation() + batch helpers
    operations.py        # per-operation typed wrappers
    schemas.py           # TypedDict stubs from OpenAPI schemas

db/
  models.py              # SQLAlchemy ORM: PublicBase (User, SiteAdmin, Structure, MarketOrder,
                         #   MarketStructure) + PrivateBase (Character)
  database.py            # initialize_private_database(owner_id), get_private_session(owner_id)
                         # NOTE: get_public_session() raises RuntimeError — public SQLite retired
  sde_store.py           # connect() + ensure_public_database() + all DuckDB DDL/DML
  sde.py                 # startup_load_sde() + DuckDB-backed lookup facade (get_type_name, etc.)

tasks/
  task_queue.py          # background Task runner — enqueue() / get_task() / cancel_task()

build/
  sde_bootstrap.py       # download_sde() / extract_sde() / run_full_bootstrap() — SDE pipeline
  sde_loader.py          # build-time SDE YAML → DuckDB warehouse loader
  esi_codegen.py         # generate() — reads spec snapshot, writes esi/client/ package
  collector_codegen.py   # generate_collectors() — writes esi/personal/, esi/corp/, esi/public/

webUI/
  __init__.py            # Flask app factory (create_app) — registers blueprints
  app.py                 # start_webUI(settings)
  dashboard.py           # / — character info, ESI spec status, granted scopes
  sso.py                 # /login /callback /logout — EVE SSO OAuth2 flow
  admin.py               # /admin/* — live log console (SSE), DB browser, user management
  tasks.py               # /tasks/* + /stream/<task_id> SSE endpoint
  context.py             # Jinja2 context processors (base_ctx helper)
  templates/
    base.html
    dashboard.html
    admin.html
    admin_esi.html
    db_browser.html
    task_list.html
    task_progress.html

tests/
  test_generated.py      # smoke tests for esi/client/ package

_publicData/
  public.duckdb          # DuckDB warehouse (SDE + public operational tables + ESI spec metadata)
  client_cred            # Fernet-encrypted OAuth client_id/client_secret  [NEVER COMMIT]
  key                    # Fernet symmetric key                              [NEVER COMMIT]
  esi_specs/             # cached ESI OpenAPI spec JSON per compatibility date
    latest.json
    <date>/

_privateData/<owner_id>/
  <owner_id>.db          # per-character SQLite database                    [NEVER COMMIT]
```

> **Not yet implemented:** `esi/corp_*.py`, `esi/personal_*.py`, `esi/data_collector.py`, `analysis/` module, and the corresponding web routes (`/corp/*`, `/personal/*`, `/update_public/*`). These are the next layer to build on top of the existing infrastructure.

---

## Making ESI Requests

**Never use `requests` directly.** All ESI HTTP must go through the wrappers in `esi/rate_limiter.py`. These enforce the floating-window rate limit, apply per-group token buckets, handle caching, and fire SSE events for the live rate card in the UI.

```python
from esi.rate_limiter import esi_request, esi_get, esi_post

# Unauthenticated GET
resp = esi_get(url, params={"datasource": "tranquility"})

# Authenticated GET
resp = esi_request("GET", url, headers={"Authorization": f"Bearer {token}"}, params=...)

# POST
resp = esi_post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
```

Alternatively, use the auto-generated client from `esi/generated/client.py` which wraps `esi_request` with typed parameters derived from the OpenAPI spec:

```python
from esi.client.client import execute_operation
result = execute_operation("GetCharactersCharacterId", character_id=12345, token=access_token)
```

### Response Handling Pattern

```python
resp = esi_request("GET", url, headers=headers, params=params)
if resp.status_code == 401:
    # token expired — stop using this token
    raise _TokenExpired(...)
if resp.status_code in (403, 404):
    return None          # no access or not found — not an error
if not resp.ok:
    logger.warning("HTTP %s for %s", resp.status_code, url)
    return None
return resp.json()
```

### Pagination (X-Pages)

ESI returns a `X-Pages` header. Fetch page 1, then fan-out:

```python
resp = esi_get(url, params={**base_params, "page": 1})
total_pages = int(resp.headers.get("X-Pages", 1))
results = resp.json()
for page in range(2, total_pages + 1):
    r = esi_get(url, params={**base_params, "page": page})
    results.extend(r.json())
```

---

## ESI Services Reference

### ESI API

- **Base URL**: `https://esi.evetech.net/latest/`
- **Datasource param**: always pass `{"datasource": "tranquility"}` (or use the `DATASOURCE` constant where defined)
- **Versioning**: send `X-Compatibility-Date: YYYY-MM-DD` header (or `compatibility_date` query param) to pin API behaviour. Date rolls at 11:00 UTC. The generated client is pinned to the date in `manifest.COMPATIBILITY_DATE`.
- **Explorer / spec**: `https://esi.evetech.net/ui/`

#### Rate Limiting — Floating Window

ESI uses a **floating window token bucket** per `(rate_limit_group, applicationID:characterID)` pair.

| Response class | Token cost |
|---|---|
| 2XX | 2 tokens |
| 3XX | 1 token |
| 4XX | 5 tokens |
| 5XX | 0 tokens (server fault) |

Rate-limit response headers:

| Header | Meaning |
|---|---|
| `X-Ratelimit-Group` | Endpoint group name |
| `X-Ratelimit-Limit` | Bucket size (e.g. `150/15m`) |
| `X-Ratelimit-Remaining` | Tokens left right now |
| `X-Ratelimit-Used` | Tokens consumed by this request |
| `Retry-After` | Seconds to wait (only on 429) |

**Error rate limit** (separate, older system): at most 100 non-2XX/3XX responses per minute. On breach, ESI returns 420 on all routes until the minute resets. Headers: `X-ESI-Error-Limit-Remain`, `X-ESI-Error-Limit-Reset`.

**Task queue lane assignment**: `enqueue(..., queue="public")` requests use the public lane; `queue="private"` (default) requests use the private lane. An alternating gate in the rate limiter (`_ALTERNATING_GATE`) ensures one-for-one HTTP interleaving when both lanes are active simultaneously.

**Best practices:**
- Do not operate at the limit; back off when `X-Ratelimit-Remaining` approaches zero.
- Spread periodic requests; avoid `*/5`-minute cron patterns — stagger 5 minutes after the previous job finished.
- Respect `Expires` cache headers; refetching before expiry wastes tokens and can trigger a ban.
- Use `If-None-Match` / `ETag` — ESI returns 304 (1 token) when data is unchanged.

#### Caching

- `Expires` — do **not** re-request before this time.
- `Last-Modified` — when paginating, all pages should share the same value; mismatch means a cache refresh occurred mid-fetch.
- `ETag` — send back as `If-None-Match` on subsequent requests; 304 response = no new data, 1 token cost.

#### Endpoints without `X-Ratelimit-Group`

Some routes (e.g. `/universe/structures/{id}/`) do not return the group header. These requests fall into the **default bucket** (`limit=1800`, `window=900s`) tracked internally as `"(ungrouped)"` in `get_stats()`.

### SSO (Single Sign-On)

EVE uses OAuth 2.0 Authorization Code flow.

1. App redirects user to EVE SSO authorize endpoint with `client_id`, `redirect_uri`, `scope`, `state`.
2. User logs in, selects character, approves scopes → SSO redirects to `redirect_uri?code=…&state=…`.
3. App exchanges code for `access_token` + `refresh_token` via POST to token endpoint.
4. Use `access_token` as `Bearer` token in ESI `Authorization` header.
5. `access_token` expires (typically ~20 min); use `refresh_token` to get a new one.

Well-known endpoint for current URLs: `https://login.eveonline.com/.well-known/oauth-authorization-server`

**Security rules:**
- Always verify the `state` parameter on callback (CSRF protection). `webUI/sso.py` uses a time-limited `OAuthStateCache` to consume each state token exactly once.
- Never log or expose `refresh_token` — it grants indefinite re-auth.
- `client_secret` stays server-side only.

Token handling lives in `util/auth.py`. Tokens are Fernet-encrypted at rest (`_publicData/key`) and stored per-character in `_privateData/<owner_id>/`.

### Static Data Export (SDE)

The SDE contains static game data (types, groups, blueprints, universe geometry). It only changes on game patches.

- Local copy: `_sde/` (YAML format; multilingual fields pruned to `SUPPORTED_LANGUAGES` by `sde_bootstrap.py`)
- In-memory store: `util/sde_store.py` — lookup helpers (`get_type_name`, `get_system_region`, etc.) backed by DuckDB
- DuckDB tables bootstrapped from SDE at startup via `sde_store.ensure_public_database()`
- Full re-download pipeline: `util/sde_bootstrap.py` — `run_full_bootstrap()` downloads the SDE ZIP, extracts, prunes, then rebuilds the warehouse
- Startup toggles under `SDE:` in `config.yaml` — set `false` to skip expensive datasets; they lazy-load on first use

SDE YAML integer-keyed maps use plain integer keys. Large files should be read as JSON Lines when possible.

Celestial name derivation (no `name` field in SDE for most celestials):
- Stars → `<solarSystemName>`
- Planets → `<orbitName> <celestialIndex>` (Roman numerals)
- Moons → `<orbitName> - Moon <orbitIndex>`
- Stargates → `Stargate (<destinationSystemName>)`

### ESI Spec Registry & Codegen

`esi/spec_registry.py` maintains a local cache of the ESI OpenAPI spec:

```python
from esi.spec_registry import refresh_esi_spec_registry, get_registry_status

# Fetch and store the latest compatibility date's spec
refresh_esi_spec_registry()

# Get current status (date, route/schema/scope counts, last update, etc.)
status = get_registry_status()
```

Spec snapshots are stored under `_publicData/esi_specs/<date>/` as `routes.json`, `schemas.json`, `scopes.json`. `latest.json` records the most recently fetched date and counts.

`build/esi_codegen.py` reads the spec snapshot and regenerates the `esi/client/` package:

```powershell
python -m build.esi_codegen                   # regenerate from latest snapshot
python -m build.esi_codegen --date 2025-12-16 # pin to a specific date
python -m build.esi_codegen --force           # overwrite even if date matches
```

**Do not hand-edit `esi/client/`** — all changes will be overwritten on the next codegen run.

---

## Database Architecture

### Public — DuckDB (`_publicData/public.duckdb`)

Used for: SDE type/group/universe data, market orders, structures, site admin records, ESI spec metadata.

Access: `db/sde_store.py` — `connect()` returns a fresh `duckdb.DuckDBPyConnection`. Get a new connection per thread; DuckDB connections are not thread-safe.

```python
from db import sde_store

con = sde_store.connect()
try:
    rows = con.execute("SELECT type_id, name FROM dim_types WHERE type_id = ?", [34]).fetchall()
finally:
    con.close()
```

> **Note:** `get_public_session()` in `db/database.py` raises `RuntimeError`. The `PublicBase` SQLAlchemy models (`User`, `SiteAdmin`, `Structure`, etc.) exist as ORM definitions but DuckDB writes go through `sde_store` helpers, not SQLAlchemy sessions.

### Private — SQLite (per owner, `_privateData/<owner_id>/<owner_id>.db`)

Used for: character identity, OAuth tokens, and all future per-character data (assets, wallet, jobs, etc.).

Access: `db/database.py` — `get_private_session(owner_id)` returns a SQLAlchemy session. Call `session.close()` when done (or use as a context manager if wrapped).

```python
from db.database import get_private_session
session = get_private_session(owner_id)
try:
    char = session.query(Character).filter_by(character_id=owner_id).first()
finally:
    session.close()
```

SQLite WAL mode, `synchronous=NORMAL`, `busy_timeout=30000`, and `foreign_keys=ON` are set automatically on each connection.

### Models (`db/models.py`)

| Base | Model | Storage |
|---|---|---|
| `PublicBase` | `User`, `SiteAdmin`, `Structure`, `MarketOrder`, `MarketStructure` | DuckDB (via `sde_store`) |
| `PrivateBase` | `Character` | SQLite per owner |

New private models: add to `PrivateBase` in `db/models.py`. `PrivateBase.metadata.create_all(engine)` is called inside `initialize_private_database` — no migration tool needed.

New public tables: add DDL directly inside `sde_store.ensure_public_database()`.

---

## Background Tasks & SSE

Long-running work runs in `tasks/task_queue.py` via two single-threaded `ThreadPoolExecutor` queues (public + private). Each queue is strictly FIFO; public and private tasks run concurrently with each other.

```python
from tasks.task_queue import enqueue

# queue="private" (default) — character/corp tasks
task_id = enqueue("My Task Name", my_worker_function, arg1, arg2, owner_id=owner_id)

# queue="public" — market/SDE/structure tasks
task_id = enqueue("Refresh Market", market_worker, owner_id=0, queue="public")
```

- `logging` calls and `print()` inside worker threads are automatically captured and streamed to the browser via SSE (`/stream/<task_id>`).
- The live task view is rendered by `webUI/templates/task_progress.html`.
- After each ESI request, `esi/rate_limiter.py` fires an `esi_rate` SSE event so the rate card in the task view updates in real time.
- `get_stats()` returns the most-depleted bucket as the summary, plus a `groups` dict (includes `"(ungrouped)"` when the default bucket has activity).
- Additional helpers: `get_task(task_id)`, `get_tasks_for_owner(owner_id)`, `get_all_tasks()`, `cancel_task(task_id)`, `clear_tasks(owner_id)`.

---

## Admin Panel (`webUI/admin.py`)

The admin blueprint (`/admin/*`) provides:

- **Live log console** (`/admin/stream`) — SSE stream of all `logging` output captured by `_AdminLogHandler` (last 500 lines, ring buffer).
- **DB browser** (`/admin/db_browser`) — read-only DuckDB workspace browser + private SQLite browser. Renders `db_browser.html`.
- **User management** (`/admin/promote`, `/admin/demote`) — promote/demote site admins stored in the `site_admins` DuckDB table.
- **ESI registry status** — exposed via `get_registry_status()` from `esi/spec_registry.py`.

Only users with `session["is_admin"] == True` can access these routes (enforced by the `require_admin` decorator).

---

## Common Agent Tasks

### Add a new ESI endpoint collector

1. Create `esi/corp_<name>.py` or `esi/personal_<name>.py`.
2. Implement a `collect_<name>(owner_id, access_token)` function.
3. Use `esi_get` / `esi_request` / `execute_operation` for all HTTP — never raw `requests`.
4. Handle pagination with `X-Pages` (see pattern above).
5. Upsert results to the owner's private DB via `get_private_session(owner_id)`.
6. Submit as a background task via `enqueue("Collect …", collect_fn, owner_id=owner_id)`.
7. Expose a trigger route in a new blueprint and register it in `webUI/__init__.py`.

### Add a new DB model

1. Add a class to `db/models.py` inheriting `PrivateBase`.
2. `PrivateBase.metadata.create_all(engine)` runs automatically in `initialize_private_database` — no migration needed.
3. For new DuckDB/public tables, add DDL in `sde_store.ensure_public_database()`.

### Add a new web route

1. Add the route to an existing blueprint or create a new one.
2. Register new blueprints in `webUI/__init__.py` (`create_app`).
3. Add Jinja2 template under `webUI/templates/`, extending `base.html`.

### Regenerate the ESI client

```powershell
# 1. Refresh the spec snapshot from ESI
python -c "from esi.spec_registry import refresh_esi_spec_registry; refresh_esi_spec_registry()"

# 2. Regenerate esi/client/
python -m build.esi_codegen --force
```

### Run the application

```powershell
python main.py
```

Default: `http://127.0.0.1:5000`. Debug mode and port are controlled by `RuntimeSettings` (see `config.py`). Override without editing config by setting env vars: `EVE_DEBUG=1`, `EVE_WEB_PORT=8080`, etc.

### Check for errors

```powershell
python -c "import main"          # quick import-time check
python -m py_compile esi/rate_limiter.py
```

### Install / update dependencies

```powershell
pip install -r requirements.txt
```

---

## Code Conventions

- **All ESI HTTP → `esi_request` / `esi_get` / `esi_post`** (never raw `requests`).
- **Never call `requests` directly** anywhere outside `esi/rate_limiter.py` and `esi/spec_registry.py` / `build/sde_bootstrap.py` (which make non-ESI HTTP calls for spec/SDE download).
- **Logging**: use module-level `logger = logging.getLogger(__name__)`; `logger.warning`, `logger.info`, `logger.debug` — not bare `print()` in production code (though `print()` is captured by the task queue in workers).
- **Token handling**: always check for 401 separately from 403/404. A 401 means the access token is expired; stop using it. A 403 means no permission — not an error to retry.
- **Thread safety**: all shared mutable state must use `threading.Lock()`. Get a fresh `sde_store.connect()` connection per thread — do not share DuckDB connections across threads.
- **No raw SQL with user input** — always use parameterised DuckDB queries (`con.execute("… WHERE id = ?", [val])`) or SQLAlchemy ORM.
- **Config values**: read from `config.yaml` via `load_config(CONFIG_PATH)` at startup; don't re-read config files inside request handlers.
- **Do not edit `esi/client/`** — regenerate via `build/esi_codegen.py` instead.

---

## Security Notes

- `_publicData/key` — Fernet symmetric key for encrypting refresh tokens at rest. **Never commit this file.**
- `_publicData/client_cred` — encrypted OAuth `client_id`/`client_secret`. **Never commit.**
- `_privateData/` — per-user SQLite databases. **Never commit.**
- All three paths are in `.gitignore`.
- CSRF: the SSO callback (`webUI/sso.py`) validates the `state` parameter on every callback using a time-limited `OAuthStateCache` that consumes each token exactly once.
- No user-supplied strings should be interpolated into SQL; use ORM or DuckDB parameterised queries.
