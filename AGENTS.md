# EVE Data Framework — Agent Guide

This document is the primary reference for AI agents (and humans) working inside this repository.
Read this before modifying any file.

---

## Repository Overview

**EVE Data Framework** is a self-hosted Flask web application that pulls EVE Online corporation and character data from the ESI REST API, stores it locally, and presents it through a live dashboard.

| Layer | Purpose |
|---|---|
| `main.py` | Entry point — loads SDE, starts Flask server |
| `config.yaml` | Environment variables + SDE toggle flags |
| `esi/` | One module per ESI endpoint group (corp_*, personal_*) |
| `analysis/` | Derived calculations on collected data (structures, job slots) |
| `db/` | SQLAlchemy models + session factories |
| `util/` | Shared infrastructure (rate limiter, auth, SDE, task queue) |
| `webUI/` | Flask blueprints, SSE streaming, Jinja2 templates |
| `_sde/` | Local copy of the EVE Static Data Export (YAML) |
| `_publicData/` | DuckDB public database (`public.duckdb`), OAuth credentials |
| `_privateData/<owner_id>/` | Per-owner SQLite databases |

### Tech Stack

- **Python 3.12+** — all async-free; threading via `ThreadPoolExecutor`
- **Flask** — web server, thread-safe, `threaded=True`
- **SQLAlchemy** — ORM; SQLite per character, DuckDB for public/SDE data
- **DuckDB** — public database (market orders, structures, SDE types, etc.)
- **requests** — all HTTP; wrapped by `util/esi_rate_limiter.py`
- **`config.yaml`** — runtime configuration; loaded once at startup

### Key Environment Variables (set via `config.yaml`)

| Variable | Default | Meaning |
|---|---|---|
| `PUBLIC_DATA_FOLDER` | `_publicData` | DuckDB + OAuth credential files |
| `EVE_PRIVATE_DATABASE_FOLDER` | `_privateData/` | Per-owner SQLite root |
| `SDE_PATH` | `_sde/` | Local SDE YAML files |

---

## Directory Map

```
main.py                  # startup
config.yaml              # configuration toggles
requirements.txt         # pip dependencies: flask, sqlalchemy, requests, duckdb, pyjwt, cryptography …

util/
  esi_rate_limiter.py    # ALL HTTP to ESI goes through esi_request() / esi_get() / esi_post()
  auth.py                # OAuth token storage, refresh, REQUIRED_SCOPES list
  task_queue.py          # background Task runner with SSE log streaming
  sde.py                 # SDE YAML loaders
  sde_store.py           # SDE in-memory store + DuckDB public schema bootstrap
  utils.py               # config loader, RuntimeSettings, dependency checks

db/
  models.py              # SQLAlchemy ORM: PublicBase (DuckDB) + PrivateBase (SQLite)
  database.py            # session factories: get_private_session(owner_id), DuckDB connection

esi/
  data_collector.py      # orchestrates full collection runs
  corp_*.py              # corporate endpoint collectors
  personal_*.py          # character endpoint collectors
  public/                # unauthenticated endpoint collectors

analysis/
  structures.py          # discovers + enriches player-owned structures
  job_slots.py           # industry job slot analysis

webUI/
  __init__.py            # Flask app factory (create_app)
  app.py                 # starts Flask (start_webUI)
  tasks.py               # SSE /stream/<task_id> endpoint, esi_rate hook
  corp_routes.py         # /corp/* blueprint
  personal_routes.py     # /personal/* blueprint
  public_routes.py       # /public/* blueprint
  dashboard.py           # / dashboard blueprint
  sso.py                 # SSO login/callback/logout
  context.py             # Jinja2 context processors
  templates/             # Jinja2 HTML templates
```

---

## Making ESI Requests

**Never use `requests` directly.** All ESI HTTP must go through the wrappers in `util/esi_rate_limiter.py`. These enforce the floating-window rate limit, apply per-group token buckets, handle caching, and fire SSE events for the live rate card in the UI.

```python
from util.esi_rate_limiter import esi_request, esi_get, esi_post

# Unauthenticated GET
resp = esi_get(url, params={"datasource": "tranquility"})

# Authenticated GET
resp = esi_request("GET", url, headers={"Authorization": f"Bearer {token}"}, params=...)

# POST
resp = esi_post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
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
- **Versioning**: send `X-Compatibility-Date: YYYY-MM-DD` header (or `compatibility_date` query param) to pin API behaviour. Date rolls at 11:00 UTC.
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
- Always verify the `state` parameter on callback (CSRF protection).
- Never log or expose `refresh_token` — it grants indefinite re-auth.
- `client_secret` stays server-side only.

Token handling in this repo lives in `util/auth.py`. Tokens are encrypted at rest using Fernet (`_publicData/key`) and stored per-character in `_privateData/<owner_id>/`.

### Static Data Export (SDE)

The SDE contains static game data (types, groups, blueprints, universe geometry). It only changes on game patches.

- Local copy: `_sde/` (YAML format)
- In-memory store: `util/sde_store.py` — access via `sde_store.get_type_name(type_id)`, etc.
- DuckDB tables are bootstrapped from SDE at startup via `sde_store.ensure_public_database()`
- Startup toggles in `config.yaml` under `SDE:` — set `false` to skip expensive datasets

SDE YAML integer-keyed maps use plain integer keys. Large files (`mapMoons`, etc.) should be read as JSON Lines when possible.

Celestial name derivation (no `name` field in SDE for most):
- Stars → `<solarSystemName>`
- Planets → `<orbitName> <celestialIndex>` (Roman numerals)
- Moons → `<orbitName> - Moon <orbitIndex>`
- Stargates → `Stargate (<destinationSystemName>)`

---

## Database Architecture

### Public — DuckDB (`_publicData/public.duckdb`)

Used for: SDE type/group/system data, market orders, public contracts, sovereignty, structures.

Access: `util/sde_store.py` — `get_duckdb_connection()` returns a `duckdb.DuckDBPyConnection`.

### Private — SQLite (per owner, `_privateData/<owner_id>/<owner_id>.db`)

Used for: character/corp assets, wallet, industry jobs, skills, bookmarks, etc.

Access: `db/database.py` — `get_private_session(owner_id)` returns a SQLAlchemy session.

```python
from db.database import get_private_session
with get_private_session(owner_id) as session:
    jobs = session.query(IndustryJob).filter_by(owner_id=owner_id).all()
```

### Models

Defined in `db/models.py`, split into two declarative bases:
- `PublicBase` — DuckDB-backed models
- `PrivateBase` — SQLite-backed models (per owner)

---

## Background Tasks & SSE

Long-running work (data collection, structure discovery) runs in `util/task_queue.py` via a `ThreadPoolExecutor`.

```python
from util.task_queue import submit_task

task_id = submit_task("My Task Name", my_worker_function, arg1, arg2)
```

- `logging` calls and `print()` inside worker threads are automatically captured and streamed to the browser via SSE (`/stream/<task_id>`).
- The live task view is rendered by `webUI/templates/task_progress.html`.
- After each ESI request, `util/esi_rate_limiter.py` fires an `esi_rate` SSE event so the rate card updates in real time.
- `get_stats()` returns the most-depleted bucket as the summary, plus a `groups` dict (includes `"(ungrouped)"` when the default bucket has activity).

---

## Common Agent Tasks

### Add a new ESI endpoint collector

1. Create `esi/corp_<name>_full.py` (or `personal_<name>_full.py`).
2. Implement a `collect_<name>(owner_id, access_token)` function.
3. Use `esi_get` / `esi_request` for all HTTP — never raw `requests`.
4. Handle pagination with `X-Pages` (see pattern above).
5. Upsert results to `_privateData` via `get_private_session(owner_id)`.
6. Register the collector in `esi/data_collector.py`.

### Add a new DB model

1. Add a class to `db/models.py` inheriting `PrivateBase` or `PublicBase`.
2. Call `PrivateBase.metadata.create_all(engine)` (happens in `initialize_private_database`) — no migration needed for new tables.
3. For DuckDB/public tables, add DDL in `util/sde_store.py`'s `ensure_public_database()`.

### Add a new web route

1. Add route function to the appropriate blueprint file (`corp_routes.py`, `personal_routes.py`, `public_routes.py`, or create a new blueprint).
2. Register new blueprints in `webUI/__init__.py` (`create_app`).
3. Add Jinja2 template under `webUI/templates/`.

### Run the application

```powershell
python main.py
```

Default: `http://127.0.0.1:5000`. Debug mode and port are controlled by `RuntimeSettings` (see `util/utils.py`).

### Check for errors

```powershell
python -c "import main"          # quick import-time check
python -m py_compile util/esi_rate_limiter.py
```

### Install / update dependencies

```powershell
pip install -r requirements.txt
```

---

## Code Conventions

- **All ESI HTTP → `esi_request` / `esi_get` / `esi_post`** (never raw `requests`).
- **Never call `requests` directly** anywhere outside `util/esi_rate_limiter.py`.
- **Logging**: use module-level `logger = logging.getLogger(__name__)`; `logger.warning`, `logger.info`, `logger.debug` — not `print()` in production code (though `print()` is captured by the task queue in workers).
- **Token handling**: always check for 401 separately from 403/404. A 401 means the access token is expired; remove it from rotation. A 403 means no permission — not an error to retry.
- **Thread safety**: all shared mutable state must use `threading.Lock()`. DuckDB connections are not thread-safe; get a fresh connection per thread or use the lock in `sde_store`.
- **No raw SQL strings with user input** — always use SQLAlchemy ORM or parameterised DuckDB queries.
- **Config values**: read from `config.yaml` via `load_config(CONFIG_PATH)` at startup; don't re-read config files inside request handlers.

---

## Security Notes

- `_publicData/key` — Fernet symmetric key for encrypting refresh tokens at rest. **Never commit this file.**
- `_publicData/client_cred` — encrypted OAuth `client_id`/`client_secret`. **Never commit.**
- `_privateData/` — per-user SQLite databases. **Never commit.**
- All three paths are in `.gitignore`.
- CSRF: the SSO callback (`webUI/sso.py`) validates the `state` parameter on every callback.
- No user-supplied strings should be interpolated into SQL; use ORM or DuckDB parameterised queries.
