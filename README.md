# EVE Data Framework 3

EVE Data Framework 3 is a self-hosted operations hub for EVE Online. It provisions a shared DuckDB warehouse and per-owner private SQLite databases, manages EVE SSO authentication, schedules background work through a live-streaming task queue, and renders a Flask web dashboard. The codebase is the **infrastructure layer** — authentication, database access, ESI rate limiting, SDE pipeline, and the auto-generated ESI client are all complete. The data-collection workers (corp/personal ESI collectors and analysis modules) are the next layer to be built on top.

---

## 1. High-Level Workflow

1. **Runtime bootstrap (`main.py`)**
   - Loads `config.yaml`, configures logging, and surfaces runtime toggles via `util.utils.initialize_runtime_environment`.
   - Optionally auto-installs missing packages if `Runtime.auto_install` is set.
   - Ensures the shared DuckDB warehouse is ready via `sde_store.ensure_public_database()`.
   - Loads SDE lookup caches into memory via `util.sde.startup_load_sde()`.
   - Launches the Flask application created in `webUI.create_app`.

2. **Web UI (`webUI/`)**
   - Four blueprints are registered: `auth_bp` (SSO), `dashboard_bp` (main view), `admin_bp` (admin panel), `tasks_bp` (background task viewer + SSE streams).
   - The dashboard (`webUI/dashboard.py`) shows character & session info, the current ESI spec compatibility date and route count, and the OAuth scopes granted for the session token.

3. **Background tasks (`util/task_queue.py`)**
   - Long-running work is submitted via `enqueue()` into two single-threaded executor queues (`queue="public"` and `queue="private"`).
   - Both `logging` output and `print()` from worker threads are captured and streamed live to the browser via SSE (`/stream/<task_id>`).

4. **ESI access**
   - All HTTP to ESI goes through `util/esi_rate_limiter.py`, which enforces the floating-window token-bucket rate limit, handles caching, and fires SSE events that update the live rate card in the task view.
   - `esi/generated/` is an auto-generated typed client for all 208 ESI operations derived from the OpenAPI spec (`esi/generated/client.py` -> `execute_operation()`).

5. **Storage**
   - Shared public and SDE data live in `_publicData/public.duckdb`.
   - Each account owner gets a dedicated SQLite database in `_privateData/<owner_id>/<owner_id>.db`.

---

## 2. Configuration

All runtime knobs live in `config.yaml`. The file has these sections:

- **Environment Variables** -- copied into `os.environ` on startup. Contains `LANGUAGE`, `SUPPORTED_LANGUAGES`, `PUBLIC_DATA_FOLDER`, `EVE_PRIVATE_DATABASE_FOLDER`, `AUTH_DATA_FOLDER`, and `SDE_PATH`. Absent variables also accept env-var overrides.
- **Runtime** -- optional block that maps to `util.utils.RuntimeSettings`. Keys include `debug`, `auto_install`, `host`, `port`, `log_level`, `trace_esi`, and `secret_key`. All fall back to sane defaults or the environment variables `EVE_DEBUG`, `EVE_WEB_PORT`, `EVE_LOG_LEVEL`, etc.
- **SDE** -- toggles for each SDE dataset loaded at startup. Set a flag to `false` to skip loading that dataset (it will lazy-load on first use). The `database_file` key sets the DuckDB path.
- **Structures** -- cooldown-day settings that control how long inaccessible structures are skipped during enrichment and market collection.

---

## 3. Dependency Management

`requirements.txt` lists the supported dependency set. On startup, `ensure_dependencies` checks that required modules are importable. If `auto_install` is true, a missing module triggers `pip install -r requirements.txt` in place.

---

## 4. Database Architecture

### 4.1 Shared Warehouse (`_publicData/public.duckdb`)

This DuckDB file holds all public and SDE data:

- **SDE marts**: `dim_types`, `dim_groups`, `dim_categories`, `dim_market_groups`, `dim_systems`, `dim_stargates`, `fact_blueprints`, dogma/material tables, and SDE manifest tables.
- **Public operational tables**: `users`, `site_admins`, `structures`, `market_structures`, `market_orders`.
- **ESI spec metadata**: `esi_routes`, `esi_schemas`, `esi_scopes` -- populated by `util/esi_spec_registry.py`.

Access: `util/sde_store.connect()` returns a fresh `duckdb.DuckDBPyConnection`. Always get a new connection per thread; DuckDB connections are not thread-safe.

> `get_public_session()` in `db/database.py` raises `RuntimeError` -- public SQLite was retired. The `PublicBase` SQLAlchemy models (`User`, `SiteAdmin`, `Structure`, etc.) exist as ORM definitions but all DuckDB writes go through `sde_store` helpers directly.

### 4.2 Private Databases (`_privateData/<owner_id>/<owner_id>.db`)

When a character first authenticates, `initialize_private_database(owner_id)` provisions a dedicated SQLite database for that owner. It currently stores:

- Character identity and OAuth tokens (`characters` table via `PrivateBase`).

Future per-character data (assets, wallet, industry jobs, skills, etc.) will be added here as new `PrivateBase` models.

Sessions are obtained via `db.database.get_private_session(owner_id)`. SQLite is configured with WAL mode, `synchronous=NORMAL`, a 30 s busy timeout, and `foreign_keys=ON`.

---

## 5. Authentication and Token Flow

1. Characters authenticate through EVE SSO (OAuth 2.0 Authorization Code flow) via the routes in `webUI/sso.py`.
2. A time-limited `OAuthStateCache` issues and consumes each CSRF `state` token exactly once.
3. OAuth tokens are Fernet-encrypted at rest (`_publicData/key`) and stored in the owner's private SQLite database via `util/auth.py`.
4. On each request that needs an access token, `util.utils.get_token(owner_id)` loads the character's stored token and refreshes it if expired.
5. Multiple characters can be attached to a single owner (add-toon flow); each character gets its own token row.

---

## 6. ESI Access, Caching, and Rate Limiting

`util/esi_rate_limiter.py` centralises all outbound ESI HTTP. Key behaviours:

- **Floating-window token bucket** -- tracks per `(rate_limit_group, applicationID:characterID)` pair. 2XX = 2 tokens, 4XX = 5 tokens; 3XX = 1; 5XX = 0 (server fault).
- **Error-rate tracking** -- monitors `X-ESI-Error-Limit-Remain` separately from the main bucket.
- **ETag / `If-None-Match`** -- responses are cached and re-requested with the ETag; unchanged data returns 304 (1 token) instead of a full response.
- **Alternating gate** -- when both `public` and `private` task queues are active, the gate interleaves their HTTP requests one-for-one to avoid one queue monopolising the rate budget.
- **Post-request hook** -- after each real HTTP call, a hook fires an `esi_rate` SSE event so the live rate card in `task_progress.html` updates in the browser.
- **Tracing** -- when `RuntimeSettings.trace_esi` is true, each outbound call is printed (also visible in task log streams).

---

## 7. ESI Spec Registry & Auto-Generated Client

### Spec Registry (`util/esi_spec_registry.py`)

Fetches the ESI OpenAPI spec for a given compatibility date and parses it into structured JSON files stored in `_publicData/esi_specs/<date>/`:

- `routes.json` -- all operations with parameters, scopes, pagination info, cache hints.
- `schemas.json` -- TypedDict-compatible schema definitions.
- `scopes.json` -- all unique OAuth scopes.
- `latest.json` -- records the most recently fetched date and counts.

Spec metadata is also inserted into the DuckDB tables `esi_routes`, `esi_schemas`, `esi_scopes` for browsing via the admin DB browser.

```python
from esi.spec_registry import refresh_esi_spec_registry, get_registry_status
refresh_esi_spec_registry()       # fetch latest spec and store it
status = get_registry_status()    # dict with date, counts, last_updated, etc.
```

### Code Generator (`build/esi_codegen.py`)

Reads the spec snapshot and regenerates the `esi/client/` package:

```powershell
python -m build.esi_codegen                   # regenerate from latest snapshot
python -m build.esi_codegen --date 2025-12-16 # pin to a specific date
python -m build.esi_codegen --force           # overwrite even if date matches
```

The generated package (`esi/client/`) is pinned to compatibility date `2025-12-16` and provides 208 typed operations. **Do not hand-edit `esi/client/`.**

```python
from esi.client.client import execute_operation
result = execute_operation("GetCharactersCharacterId", character_id=12345, token=access_token)
```

---

## 8. Static Data Export (SDE) Pipeline

The SDE provides static game data (type names, market groups, universe geometry, blueprints, dogma). It is rebuilt whenever CCP patches the game.

Pipeline (`build/sde_bootstrap.py`):

1. Download the SDE ZIP from CCP's S3 bucket.
2. Extract YAML files into `_sde/`.
3. Language-prune multilingual fields to only the languages in `SUPPORTED_LANGUAGES`.
4. Rebuild the DuckDB warehouse (`sde_store.build_sde_warehouse()`).
5. Refresh the ESI spec registry (`esi_spec_registry.refresh_esi_spec_registry()`).
6. Reload in-memory SDE caches (`sde.refresh_all_caches()`).

At normal startup, `startup_load_sde()` loads the SDE datasets that are toggled `true` in `config.yaml` (no download). The download pipeline is triggered manually or from a future admin route.

---

## 9. Background Task Queue

`tasks/task_queue.py` provides a simple but complete background work system:

```python
from tasks.task_queue import enqueue

task_id = enqueue("My Task Name", worker_fn, arg1, arg2, owner_id=owner_id)
# queue="public" for market/SDE tasks (default is "private")
```

- Two single-threaded `ThreadPoolExecutor` queues (`tq-pub`, `tq-prv`) run concurrently with each other but each queue is strictly serial (FIFO).
- `logging` calls and `print()` inside worker threads are captured by thread-aware interceptors and streamed to the browser via SSE.
- ESI rate stats are pushed to the browser as `esi_rate` SSE events after each HTTP call.
- The `/stream/<task_id>` SSE endpoint and `task_progress.html` render the live view.
- Helpers: `get_task()`, `get_tasks_for_owner()`, `get_all_tasks()`, `cancel_task()`, `clear_tasks()`.

---

## 10. Admin Panel

`webUI/admin.py` provides the admin blueprint (`/admin/*`), accessible only to users with `session["is_admin"] == True`:

- **Live log console** (`/admin/stream`) -- SSE stream of all `logging` output, ring-buffered to the last 500 lines.
- **DB browser** (`/admin/db_browser`) -- read-only browser for the DuckDB warehouse and any owner's private SQLite database.
- **User management** (`/admin/promote`, `/admin/demote`) -- grant or revoke site-admin status, stored in the `site_admins` DuckDB table.
- **ESI registry status** -- current compatibility date, operation/schema/scope counts, and last-updated timestamp.

---

## 11. Web UI Overview

The Flask app (`webUI/`) registers four blueprints:

| Blueprint | Prefix | Purpose |
|---|---|---|
| `auth_bp` | `/` | EVE SSO login / callback / logout |
| `dashboard_bp` | `/` | Main landing page |
| `admin_bp` | `/admin` | Admin panel (log console, DB browser, user management) |
| `tasks_bp` | `/tasks` | Task list, task detail, SSE stream |

Templates under `webUI/templates/` all extend `base.html`:

| Template | Rendered by |
|---|---|
| `dashboard.html` | `dashboard_bp` -- character info, ESI spec status, granted scopes |
| `admin.html` | `admin_bp` -- live log console |
| `admin_esi.html` | `admin_bp` -- ESI registry details |
| `db_browser.html` | `admin_bp` -- DuckDB / SQLite browser |
| `task_list.html` | `tasks_bp` -- list of all tasks |
| `task_progress.html` | `tasks_bp` -- live task output + ESI rate card |

---

## 12. Logging

The framework uses the standard library `logging` module. Default level is INFO, configurable via `Runtime.log_level` or the `EVE_LOG_LEVEL` env var. Notable behaviours:

- Worker threads have their `logging` output and `print()` automatically captured and forwarded to the running `Task` object for SSE streaming.
- The admin panel's `_AdminLogHandler` buffers the last 500 log lines from all modules and streams them to the live log console page.
- A `StreamHandler` on the real `sys.stdout` emits all log records to the terminal without double-capturing from the task interceptors.

---

## 13. Development Tips

- **Running the app**: `python main.py` -- default `http://127.0.0.1:5000`. Override host/port with `EVE_WEB_HOST` / `EVE_WEB_PORT`.
- **Quick syntax check**: `python -c "import main"` or `python -m py_compile <file>`.
- **Adding a collector**: create `esi/corp_<name>.py` or `esi/personal_<name>.py`, use `esi_get`/`execute_operation` for HTTP, upsert to the private DB via `get_private_session(owner_id)`, submit as `enqueue(...)`, expose a trigger route in a new blueprint registered in `webUI/__init__.py`.
- **Adding a DB model**: subclass `PrivateBase` in `db/models.py` -- `create_all` runs automatically via `initialize_private_database`. For DuckDB/public tables add DDL in `sde_store.ensure_public_database()`.
- **Regenerating the ESI client**: `python -c "from esi.spec_registry import refresh_esi_spec_registry; refresh_esi_spec_registry()"` then `python -m build.esi_codegen --force`.
- **Never call `requests` directly** outside `esi/rate_limiter.py`, `esi/spec_registry.py`, and `build/sde_bootstrap.py`.

---

## 14. Security Notes

- `_publicData/key` -- Fernet symmetric key. **Never commit.**
- `_publicData/client_cred` -- encrypted OAuth `client_id`/`client_secret`. **Never commit.**
- `_privateData/` -- per-user SQLite databases. **Never commit.**
- CSRF is mitigated by the `OAuthStateCache` in `webUI/sso.py`, which consumes each state token exactly once within a 5-minute window.
- All SQL uses parameterised DuckDB queries or the SQLAlchemy ORM -- no string interpolation with user input.

---

## 15. Licensing

This project is released under the MIT License. See `LICENCE.md` for the full text.