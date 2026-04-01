# EVE Data Framework 3

EVE Data Framework 3 is a self-hosted operations hub for EVE Online. It provisions a shared DuckDB warehouse and per-owner private SQLite databases, manages EVE SSO authentication, schedules background work through a live-streaming task queue, and renders a Flask web dashboard.

The codebase is layered into **core infrastructure** (`core/`), **data collectors** (`collectors/`), **user-facing applications** (`applications/`), and a **web layer** (`webUI/`). Legacy import paths (`db/`, `esi/`, `sde.py`, `tasks/`, `workers/`) are thin forwarding shims — new code should import from `core.*` or `collectors.*`.

---

## 1. High-Level Workflow

1. **Runtime bootstrap (`main.py`)**
   - Loads `config.yaml`, configures logging, and surfaces runtime toggles via `config.initialize_runtime_environment`.
   - Optionally auto-installs missing packages if `Runtime.auto_install` is set.
   - Ensures the shared DuckDB warehouse is ready via `core.db.ensure_public_database()`.
   - Loads SDE lookup caches into memory via `core.sde.startup_load_sde()`.
   - Launches the Flask application created in `webUI.create_app`.

2. **Web UI (`webUI/`)**
   - Four blueprints are registered: `auth_bp` (SSO), `dashboard_bp` (main view), `admin_bp` (admin panel), `tasks_bp` (background task viewer + SSE streams).
   - Application blueprints are auto-discovered via `pkgutil` from `applications/` and registered automatically.

3. **Background tasks (`core/queue/manager.py`)**
   - Long-running work is submitted via `enqueue()` into two single-threaded executor queues (`queue="public"` and `queue="private"`).
   - Both `logging` output and `print()` from worker threads are captured and streamed live to the browser via SSE (`/stream/<task_id>`).

4. **ESI access**
   - All HTTP to ESI goes through `core/queue/esi_req.py`, which enforces the floating-window token-bucket rate limit, handles caching, and fires SSE events that update the live rate card in the task view.
   - `esi/client/` is an auto-generated typed client for all 208 ESI operations derived from the OpenAPI spec.

5. **Storage**
   - Shared public and SDE data live in `_publicData/public.duckdb`.
   - Each account owner gets a dedicated SQLite database in `_privateData/<owner_id>/<owner_id>.db`.

---

## 2. Configuration

All runtime knobs live in `config.yaml`. The file has these sections:

- **Environment Variables** — copied into `os.environ` on startup. Contains `LANGUAGE`, `SUPPORTED_LANGUAGES`, `PUBLIC_DATA_FOLDER`, `EVE_PRIVATE_DATABASE_FOLDER`, and `SDE_PATH`. Absent variables also accept env-var overrides.
- **Runtime** — optional block that maps to `config.RuntimeSettings`. Keys include `debug`, `auto_install`, `host`, `port`, `log_level`, `trace_esi`, and `secret_key`. All fall back to sane defaults or the environment variables `EVE_DEBUG`, `EVE_WEB_PORT`, `EVE_LOG_LEVEL`, etc.
- **SDE** — toggles for each SDE dataset loaded at startup. Set a flag to `false` to skip loading that dataset (it will lazy-load on first use). The `database_file` key sets the DuckDB path.
- **Structures** — cooldown-day settings that control how long inaccessible structures are skipped during enrichment and market collection.

---

## 3. Dependency Management

`requirements.txt` lists the supported dependency set. On startup, `ensure_dependencies` checks that required modules are importable. If `auto_install` is true, a missing module triggers `pip install -r requirements.txt` in place.

---

## 4. Database Architecture

### 4.1 Shared Warehouse (`_publicData/public.duckdb`)

This DuckDB file holds all public and SDE data:

- **SDE marts**: `dim_types`, `dim_groups`, `dim_categories`, `dim_market_groups`, `dim_systems`, `dim_stargates`, `fact_blueprints`, dogma/material tables, and SDE manifest tables.
- **Identity tables**: `users`, `site_admins` — owned by `core/db/publicDB.py`.
- **Domain tables**: `structures`, `market_orders`, `market_structures`, `market_region_cooldowns`, `isk_per_hour_results` — owned by their respective collectors/applications.
- **ESI spec metadata**: `esi_routes`, `esi_schemas`, `esi_scopes` — populated by `core/esi/registry.py`.

Access: `core.db.publicDB.connect()` returns a fresh `duckdb.DuckDBPyConnection`. Always get a new connection per thread; DuckDB connections are not thread-safe.

#### Decentralised Table Ownership

Each collector (or application) owns the DDL for its tables via an `ensure_tables(con)` function called before any writes. Core infrastructure only creates identity tables and views. See [AGENTS.md](AGENTS.md) for the full ownership table and enrichment pattern.

### 4.2 Private Databases (`_privateData/<owner_id>/<owner_id>.db`)

When a character first authenticates, `core.db.privateDB.initialize_private_database(owner_id)` provisions a dedicated SQLite database for that owner. It currently stores:

- Character identity and OAuth tokens (`characters` table via `PrivateBase`).

Future per-character data (assets, wallet, industry jobs, skills, etc.) will be added here as new `PrivateBase` models. Sessions are obtained via `core.db.privateDB.get_private_session(owner_id)`. SQLite is configured with WAL mode, `synchronous=NORMAL`, a 30 s busy timeout, and `foreign_keys=ON`.

---

## 5. Authentication and Token Flow

1. Characters authenticate through EVE SSO (OAuth 2.0 Authorization Code flow) via the routes in `webUI/sso.py`.
2. A time-limited `OAuthStateCache` issues and consumes each CSRF `state` token exactly once.
3. OAuth tokens are Fernet-encrypted at rest (`_publicData/key`) and stored in the owner's private SQLite database via `core/esi/auth.py`.
4. On each request that needs an access token, token helpers in `core.esi.auth` load the character's stored token and refresh it if expired.
5. Multiple characters can be attached to a single owner (add-toon flow); each character gets its own token row.

---

## 6. ESI Access, Caching, and Rate Limiting

`core/queue/esi_req.py` centralises all outbound ESI HTTP. Key behaviours:

- **Floating-window token bucket** — tracks per `(rate_limit_group, applicationID:characterID)` pair. 2XX = 2 tokens, 4XX = 5 tokens; 3XX = 1; 5XX = 0 (server fault).
- **Error-rate tracking** — monitors `X-ESI-Error-Limit-Remain` separately from the main bucket.
- **ETag / `If-None-Match`** — responses are cached and re-requested with the ETag; unchanged data returns 304 (1 token) instead of a full response.
- **Alternating gate** — when both `public` and `private` task queues are active, the gate interleaves their HTTP requests one-for-one to avoid one queue monopolising the rate budget.
- **Post-request hook** — after each real HTTP call, a hook fires an `esi_rate` SSE event.
- **Tracing** — when `RuntimeSettings.trace_esi` is true, each outbound call is printed.

---

## 7. ESI Spec Registry & Auto-Generated Client

### Spec Registry (`core/esi/registry.py`)

Fetches the ESI OpenAPI spec for a given compatibility date and parses it into structured JSON files stored in `_publicData/esi_specs/<date>/`:

- `routes.json` — all operations with parameters, scopes, pagination info, cache hints.
- `schemas.json` — TypedDict-compatible schema definitions.
- `scopes.json` — all unique OAuth scopes.
- `latest.json` — records the most recently fetched date and counts.

Spec metadata is also inserted into the DuckDB tables `esi_routes`, `esi_schemas`, `esi_scopes`.

### Code Generator (`codegen/`)

Reads the spec snapshot and regenerates packages:

```powershell
python build.py              # fetch spec + regenerate esi/client/ + collectors
python build.py --force      # force regenerate
python build.py --spec-only  # only fetch spec
python build.py --collectors # only regenerate collector packages
```

The generated `esi/client/` package provides 208 typed operations. Auto-generated domain collectors live in `collectors/personal_generatedESI/`, `collectors/corp_generatedESI/`, and `collectors/public_generatedESI/`. **Do not hand-edit generated packages.**

---

## 8. Static Data Export (SDE) Pipeline

The SDE provides static game data (type names, market groups, universe geometry, blueprints, dogma). It is rebuilt whenever CCP patches the game.

Pipeline (`collectors/sde_loader.py`):

1. Download the SDE ZIP from CCP's S3 bucket.
2. Extract YAML files into `_sde/`.
3. Language-prune multilingual fields to only the languages in `SUPPORTED_LANGUAGES`.
4. Rebuild the DuckDB warehouse.
5. Refresh the ESI spec registry.
6. Reload in-memory SDE caches.

At normal startup, `startup_load_sde()` loads the SDE datasets that are toggled `true` in `config.yaml` (no download). The download pipeline is triggered manually or from a future admin route.

---

## 9. Data Collectors

Collectors live in `collectors/` and own their table DDL via `ensure_tables(con)`:

| Collector | Tables Owned | Entry Point |
|---|---|---|
| `collectors/sde_loader.py` | SDE dimension/fact tables | `update_sde()`, `build_sde_warehouse()` |
| `collectors/structures/publicDiscovery.py` | `structures` | `discover_structures()` |
| `collectors/market/publicRegions.py` | `market_orders`, `market_region_cooldowns` | `fetch_all_market_data()` |
| `collectors/market/privateStructures.py` | `market_structures` + structures enrichment | `update_structure_market_orders()` |
| `collectors/*_generatedESI/` | (varies) | Auto-generated per-endpoint wrappers |

---

## 10. Applications (Auto-Discovery)

User-facing tools live in `applications/` and are auto-discovered via `pkgutil`. Each sub-package exposes a `Tool` attribute (an instance of `BaseTool`) and a Flask `Blueprint`.

| Application | Description |
|---|---|
| `market_browser` | Browse live market orders by region and item type |
| `industry_calculator` | Calculate manufacturing costs and margins |
| `isk_per_hour` | Rank blueprints by ISK earned per hour |

To add a new application:
1. Create `applications/<name>/` with `__init__.py`, `routes.py`, optional `worker.py`.
2. Define a class inheriting `BaseTool` with a `ToolManifest` and `create_blueprint()`.
3. Set `Tool = YourTool()` as a module-level attribute in `__init__.py`.
4. The application will be auto-registered on import.

---

## 11. Background Task Queue

```python
from core.queue.manager import enqueue

task_id = enqueue("My Task Name", worker_fn, arg1, arg2, owner_id=owner_id)
# queue="public" for market/SDE tasks (default is "private")
```

- Two single-threaded `ThreadPoolExecutor` queues (`tq-pub`, `tq-prv`) run concurrently with each other but each queue is strictly serial (FIFO).
- `logging` calls and `print()` inside worker threads are captured and streamed to the browser via SSE.
- The `/stream/<task_id>` SSE endpoint and `task_progress.html` render the live view.

---

## 12. Web UI Overview

The Flask app (`webUI/`) registers four core blueprints plus any application blueprints:

| Blueprint | Prefix | Purpose |
|---|---|---|
| `auth_bp` | `/` | EVE SSO login / callback / logout |
| `dashboard_bp` | `/` | Main landing page |
| `admin_bp` | `/admin` | Admin panel (log console, DB browser, user management) |
| `tasks_bp` | `/tasks` | Task list, task detail, SSE stream |

---

## 13. Development Tips

- **Running the app**: `python main.py` — default `http://127.0.0.1:5000`. Override host/port with `EVE_WEB_HOST` / `EVE_WEB_PORT`.
- **Quick syntax check**: `python -c "import main"` or `python -m py_compile <file>`.
- **Adding a collector**: create `collectors/<domain>/` — see AGENTS.md for the full pattern.
- **Adding an application**: create `applications/<name>/` — see AGENTS.md for the full pattern.
- **Adding a private DB model**: subclass `PrivateBase` in `core/db/models/identity.py`.
- **Regenerating the ESI client**: `python build.py --force`.
- **Never call `requests` directly** — use `core.queue.esi_req`.
- **New code imports from `core.*` / `collectors.*`** — not from legacy shim paths.

---

## 14. Security Notes

- `_publicData/key` — Fernet symmetric key. **Never commit.**
- `_publicData/client_cred` — encrypted OAuth `client_id`/`client_secret`. **Never commit.**
- `_privateData/` — per-user SQLite databases. **Never commit.**
- CSRF is mitigated by the `OAuthStateCache` in `webUI/sso.py`, which consumes each state token exactly once within a 5-minute window.
- All SQL uses parameterised DuckDB queries or the SQLAlchemy ORM — no string interpolation with user input.

---

## 15. Licensing

This project is released under the MIT License. See `LICENCE.md` for the full text.