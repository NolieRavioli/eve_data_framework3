# Phase 1 — Core Infrastructure Refactor

> **Depends on:** Nothing (first phase)
> **Blocks:** All subsequent phases
> **Scope:** `core/` only — no application or analysis changes

---

## Goal

Establish 7 clean core systems with no naming collisions, no dead code, and sharp separation of responsibility. After this phase, every core module has a single clear purpose and there is exactly one canonical import path for every function.

**The 7 core systems after this phase:**

| Package | Responsibility | One-sentence rule |
|---------|---------------|-------------------|
| `core/config` | Runtime configuration | Loads config.yaml, exposes `RuntimeSettings` |
| `core/auth` | Authentication & authorization framework | SSO, tokens, credentials, roles, levels, decorators |
| `core/bus` | Event bus & WebSocket | Pub/sub, topic registry, WebSocket handler |
| `core/db` | Data persistence | DuckDB + SQLite: connections, reads, writes, SDE caches |
| `core/esi` | ESI API access | HTTP requests, rate limiting, response caching, spec registry |
| `core/tasks` | Task execution & scheduling | Task queue, scheduler engine, output capture |
| `core/web` | Flask application | App factory, template context, home page, setup wizard |

---

## Operation A — Dissolve `core/queue/`

### Problem

`core/queue/` currently holds 6 unrelated concerns:

| File | Lines | What it actually does | Real home |
|------|-------|-----------------------|-----------|
| `scheduler.py` | ~330 | Task dataclass, `enqueue()`, ThreadPoolExecutors, task lifecycle | `core/tasks/` |
| `esi_req.py` | ~1000 | ESI rate limiter, HTTP functions, L1 cache, fair alternation | `core/esi/` |
| `db.py` | ~260 | Gateway wrapping writer/reader/db_access — adds indirection with no value | **DELETE** |
| `db_access.py` | ~250 | Per-owner private SQLite write queue (dead — never used) | `core/db/` (absorb) |
| `streams.py` | ~200 | stdout/stderr capture, SSE generators, ESI rate hooks | `core/tasks/` |
| `_context.py` | ~10 | Thread-local `task_id` | `core/tasks/` |

Additionally, `__init__.py` re-exports 32 symbols from 4 different submodules, creating the illusion that these belong together.

### File-by-File Migration

#### 1. `core/queue/scheduler.py` → `core/tasks/queue.py`

**Move entire file.** Update internal imports:

```python
# OLD (core/queue/scheduler.py)
from core.queue._context import _thread_task
from core.queue.esi_req import set_request_lane

# NEW (core/tasks/queue.py)
from core.tasks.context import _thread_task
from core.esi.request import set_request_lane
```

Public symbols that move: `Task`, `enqueue`, `get_task`, `get_tasks_for_owner`, `get_all_tasks`, `cancel_task`, `clear_tasks`

Any import of `core.bus.handler` or `core.bus.registry` inside this file stays as-is (bus is stable).

#### 2. `core/queue/streams.py` → `core/tasks/output.py`

**Move entire file.** Update internal imports:

```python
# OLD
from core.queue._context import _thread_task
from core.queue.scheduler import _registry  # task registry dict

# NEW
from core.tasks.context import _thread_task
from core.tasks.queue import _registry
```

Public symbols that move: `rate_stream`, `log_stream`, `_ThreadRoutedWriter`, `_TaskLogHandler`

#### 3. `core/queue/_context.py` → `core/tasks/context.py`

**Move as-is.** No internal imports to update (it's self-contained — just `threading.local()`).

Public symbol: `_thread_task`

#### 4. `core/queue/esi_req.py` → Split into `core/esi/request.py` + `core/esi/rate.py`

This is the most complex move. The ~1000 LOC file has three layers:

**`core/esi/rate.py`** — Internal rate engine (not re-exported from `core/esi/`):
- `EsiRateLimiter` class (token bucket algorithm)
- `FairAlternatingLock` class
- `_esi_rate_limiter` module-level singleton
- `get_esi_rate_limiter()` accessor
- `get_esi_rate_stats()` stats getter
- `set_request_lane(lane)` lane setter
- All `X-Ratelimit-*` header parsing logic
- `_RATE_DEFS` config
- The 429/420 backoff state

Internal imports:
```python
from core.tasks.context import _thread_task  # for per-task rate attribution
from core.bus import publish                  # rate event publishing
```

**`core/esi/request.py`** — Public API (re-exported from `core/esi/__init__.py`):
- `esi_get(url, *, params, headers)` → `requests.Response`
- `esi_post(url, *, json, headers)` → `requests.Response`
- `esi_request(method, url, **kwargs)` → `requests.Response`
- L1 in-memory cache dict (`_CACHE`)
- ETag handling (`If-None-Match` header injection)
- Cache check → rate acquire → HTTP → cache store → rate release flow

Internal imports:
```python
from core.esi.rate import (
    EsiRateLimiter,
    get_esi_rate_limiter,
    _esi_rate_limiter,
)
from core.esi.cache import check, store, refresh_ttl, get_ttl_for_url, make_cache_key
from core.tasks.context import _thread_task
```

**Split heuristic:** If a function is called by application code or analysis code → `request.py`. If it's only called by `request.py` internals → `rate.py`.

#### 5. `core/queue/db.py` → **DELETE**

This file is a gateway that wraps `core.db.writer`, `core.db.reader`, and `core.queue.db_access` with renamed functions. It adds indirection without adding value.

**Current callers and their migrations:**

| Caller | Current Import | New Import |
|--------|---------------|-----------|
| `applications/_api.py` | `from core.queue.db import read_public, read_public_one, read_public_scalar` | `from core.db.reader import query_rows, query_one, query_scalar` |
| `applications/_api.py` | `from core.queue.db import read_private` | `from core.db.private import read_private` |
| `applications/_api.py` | `from core.queue.db import get_db_gateway_stats` | `from core.db.stats import get_db_gateway_stats` |
| `core/queue/__init__.py` | All 15 re-exports from `core.queue.db` | N/A — `core/queue/` deleted |
| `core/web/__init__.py` | `from core.queue.db import start_db_stats_publisher` | `from core.db.stats import start_db_stats_publisher` |
| `core/esi/cache.py` | `from core.queue.db import write_public_nowait, write_public` | `from core.db.writer import db_write_nowait, db_write` |

The `start_db_stats_publisher()` function (currently in `core/queue/db.py`) moves to `core/db/stats.py` since it publishes DB metrics.

**Dead code removed:**
- `write_private()` — defined in `core/queue/db.py`, never called by any module
- `write_private_many()` — defined in `core/queue/db.py`, never called by any module
- Their re-exports in `core/queue/__init__.py`

#### 6. `core/queue/db_access.py` → Absorb into `core/db/private.py`

The per-owner `_OwnerState` queue and drain thread pattern from `db_access.py` gets absorbed into the renamed `private.py` (was `privateDB.py`). The logic stays the same but lives alongside the session factory it depends on.

Key function: `submit_private_write(owner_id, fn)` — enqueues a callable that receives a SQLAlchemy session.

Even though this is currently dead code (no callers), it's a sound pattern that Phase 7 will need when enforcing collector write discipline. Preserve the implementation but mark it clearly.

#### 7. Delete `core/queue/` directory

After all files are moved and imports updated, delete:
- `core/queue/__init__.py`
- `core/queue/scheduler.py`
- `core/queue/streams.py`
- `core/queue/_context.py`
- `core/queue/esi_req.py`
- `core/queue/db.py`
- `core/queue/db_access.py`

---

## Operation B — Redesign `core/esi/`

### Before

```
core/esi/
  __init__.py       # empty
  auth.py           # CredentialManager + TokenDBManager + pick_token + fresh_token
  registry.py       # ESI spec fetch + DuckDB storage
  cache.py          # L2 DuckDB response cache
  generated/        # auto-generated client
  personal/         # auto-generated domain wrappers
  corp/             # auto-generated domain wrappers
  public/           # auto-generated domain wrappers
```

### After

```
core/esi/
  __init__.py       # re-exports: esi_get, esi_post, esi_request
  request.py        # NEW — public ESI HTTP API + L1 cache (from esi_req.py)
  rate.py           # NEW — internal rate engine (from esi_req.py)
  cache.py          # UNCHANGED — L2 DuckDB cache
  registry.py       # UNCHANGED — ESI spec management
  generated/        # auto-generated — UNCHANGED
  personal/         # auto-generated — UNCHANGED
  corp/             # auto-generated — UNCHANGED
  public/           # auto-generated — UNCHANGED
```

**`auth.py` is DELETED** — content moves to `core/auth/` (Operation C).

### `core/esi/__init__.py` — New content

```python
"""ESI access — the only way to make ESI HTTP requests.

All outbound ESI communication goes through esi_get / esi_post / esi_request.
These functions handle rate limiting, caching, ETag revalidation, and error
classification automatically.

Internal modules (rate.py, cache.py) are not re-exported — they are
implementation details of the request pipeline.
"""

from core.esi.request import esi_get, esi_post, esi_request

__all__ = ["esi_get", "esi_post", "esi_request"]
```

### What callers change

| Caller | Old Import | New Import |
|--------|-----------|-----------|
| `analysis/market/regions.py` | `from core.queue.esi_req import esi_get` | `from core.esi import esi_get` |
| `analysis/market/structures.py` | `from core.queue.esi_req import esi_get` | `from core.esi import esi_get` |
| `analysis/structures/discover.py` | `from core.queue.esi_req import esi_get` | `from core.esi import esi_get` |
| `applications/_api.py` | `from core.queue.esi_req import esi_get, esi_post, esi_request` | `from core.esi import esi_get, esi_post, esi_request` |
| `applications/_api.py` | `from core.queue.esi_req import get_esi_rate_limiter` | `from core.esi.rate import get_esi_rate_limiter` |
| `core/tasks/output.py` (was streams.py) | `from core.queue.esi_req import ...` | `from core.esi.rate import ...` |

### Auto-generated packages

`core/esi/generated/`, `core/esi/personal/`, `core/esi/corp/`, `core/esi/public/` are **untouched**. They import from `core.esi.generated.client` which calls `esi_request` internally — that internal import path must be updated in the codegen templates (`utils/build/esi_codegen.py` and `utils/build/domain_codegen.py`).

**Check:** Run `python build.py --gen-only` after Phase 1 to verify generated code uses the new import paths. If the codegen templates hardcode `core.queue.esi_req`, update them.

---

## Operation C — Extract `core/auth/`

### Problem

Auth logic is scattered across three packages:

| Concern | Current Location | Lines |
|---------|-----------------|-------|
| OAuth2 SSO flow (login/callback/logout/add_toon/switch_character) | `core/web/auth.py` | ~200 |
| CSRF state tokens (OAuthStateCache) | `core/web/auth.py` | ~50 |
| Access decorators (require_login/admin/role) | `core/web/auth.py` | ~80 |
| Client credential storage (CredentialManager) | `core/esi/auth.py` | ~80 |
| Per-character token storage + refresh (TokenDBManager) | `core/esi/auth.py` | ~150 |
| Token resolution (pick_token, fresh_token, get_token) | `core/esi/auth.py` | ~60 |
| Role CRUD (get_user_roles, grant_user_roles, revoke_user_role) | `core/db/publicDB.py` | ~60 |
| Admin CRUD (get_site_admin, upsert_site_admin, delete_site_admin) | `core/db/publicDB.py` | ~50 |
| User registration (link_public_user, list_public_users) | `core/db/publicDB.py` | ~40 |
| Owner check (is_site_owner_configured) | `core/db/publicDB.py` | ~10 |

### Target Structure

```
core/auth/
  __init__.py       # re-exports: decorators, token helpers, identity queries
  sso.py            # OAuth2 SSO flow — auth_bp blueprint, OAuthStateCache
  credentials.py    # CredentialManager — Fernet encryption of client_id/secret
  tokens.py         # TokenDBManager — per-char token CRUD, pick_token, fresh_token
  identity.py       # User/admin/role CRUD — extracted from publicDB.py
  decorators.py     # require_login, require_admin, require_role
```

### File-by-File Details

#### `core/auth/sso.py` — from `core/web/auth.py`

Move the Flask blueprint (`auth_bp`) and `OAuthStateCache`. This file retains Flask dependency (it defines routes).

```python
# core/auth/sso.py
from flask import Blueprint, session, redirect, request, url_for
from core.auth.credentials import CredentialManager
from core.auth.tokens import TokenDBManager
from core.auth.identity import link_user, grant_default_roles, is_site_owner_configured
from core.auth.decorators import require_login

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
# ... routes: /login, /callback, /logout, /add_toon, /switch_character
```

#### `core/auth/credentials.py` — from `core/esi/auth.py`

Move `CredentialManager` class. No Flask dependency — pure crypto + file I/O.

```python
# core/auth/credentials.py
from cryptography.fernet import Fernet
# CredentialManager: load_credentials(), save_credentials(), has_credentials()
```

#### `core/auth/tokens.py` — from `core/esi/auth.py`

Move `TokenDBManager` and the convenience functions `pick_token()`, `fresh_token()`, `get_token()`, `resolve_default_owner_id()`.

```python
# core/auth/tokens.py
from core.db.private import get_private_session
from core.auth.credentials import CredentialManager
# TokenDBManager: save_tokens(), load_tokens(), refresh_token()
# pick_token(owner_id) → (char_id, token_data)
# fresh_token(owner_id, char_id, token_data) → (char_id, fresh_data)
```

#### `core/auth/identity.py` — from `core/db/publicDB.py`

Extract all user/admin/role functions. These currently live in `publicDB.py` alongside connection management — they are identity concerns, not database concerns.

Functions to extract:
- `link_user(owner_id, character_id, character_name)`
- `list_users()` → `list[dict]`
- `get_user_roles(owner_id)` → `list[str]`
- `grant_user_roles(owner_id, roles, granted_by)`
- `revoke_user_role(owner_id, role)`
- `get_site_admin(owner_id)` → `dict | None`
- `upsert_site_admin(owner_id, role="admin")`
- `delete_site_admin(owner_id)`
- `is_site_owner_configured()` → `bool`

These functions still call `core.db.public.connect()` internally — they use the DB, they just don't *belong* in the DB package.

```python
# core/auth/identity.py
from core.db.public import connect
# ... all identity CRUD functions
```

#### `core/auth/decorators.py` — from `core/web/auth.py`

Move `require_login`, `require_admin`, `require_role`. These are pure Flask decorators checking `session` state.

```python
# core/auth/decorators.py
from functools import wraps
from flask import session, redirect, url_for, abort
# require_login(f), require_admin(f), require_role(role_name)(f)
```

#### `core/auth/__init__.py`

```python
"""Authentication & authorization framework.

Handles: OAuth2 SSO, encrypted token storage, role-based access control,
client credential management, and access decorators.
"""

from core.auth.decorators import require_login, require_admin, require_role
from core.auth.tokens import pick_token, fresh_token, get_token, resolve_default_owner_id
from core.auth.identity import (
    link_user, list_users, get_user_roles, grant_user_roles, revoke_user_role,
    get_site_admin, upsert_site_admin, delete_site_admin, is_site_owner_configured,
)
from core.auth.credentials import CredentialManager

__all__ = [
    "require_login", "require_admin", "require_role",
    "pick_token", "fresh_token", "get_token", "resolve_default_owner_id",
    "link_user", "list_users", "get_user_roles", "grant_user_roles", "revoke_user_role",
    "get_site_admin", "upsert_site_admin", "delete_site_admin", "is_site_owner_configured",
    "CredentialManager",
]
```

### What callers change

| Caller | Old Import | New Import |
|--------|-----------|-----------|
| `applications/_api.py` | `from core.web.auth import require_login, require_admin, require_role` | `from core.auth import require_login, require_admin, require_role` |
| `applications/_api.py` | `from core.esi.auth import get_token, fresh_token, pick_token, resolve_default_owner_id` | `from core.auth import get_token, fresh_token, pick_token, resolve_default_owner_id` |
| `applications/_api.py` | `_pub.get_site_admin`, `_pub.upsert_site_admin`, etc. (via `db_admin` namespace) | `from core.auth.identity import get_site_admin, upsert_site_admin, ...` |
| `core/web/__init__.py` | `from core.web.auth import auth_bp` | `from core.auth.sso import auth_bp` |
| `core/web/context.py` | `from core.web.auth import ...` (if any) | `from core.auth import ...` |
| `analysis/market/structures.py` | `from core.esi.auth import pick_token, fresh_token, resolve_default_owner_id` | `from core.auth import pick_token, fresh_token, resolve_default_owner_id` |
| `analysis/structures/discover.py` | `from core.esi.auth import pick_token, fresh_token, resolve_default_owner_id` | `from core.auth import pick_token, fresh_token, resolve_default_owner_id` |
| `analysis/character/populate.py` | `from core.esi.auth import pick_token, fresh_token` | `from core.auth import pick_token, fresh_token` |

### Files DELETED after extraction

- `core/web/auth.py` — content split between `core/auth/sso.py` and `core/auth/decorators.py`
- `core/esi/auth.py` — content split between `core/auth/tokens.py` and `core/auth/credentials.py`

---

## Operation D — Rename & Slim `core/db/`

### Renames

| Old | New | Reason |
|-----|-----|--------|
| `core/db/publicDB.py` | `core/db/public.py` | Naming standardization |
| `core/db/privateDB.py` | `core/db/private.py` | Naming standardization |

### `core/db/public.py` — Slimmed

After extracting identity functions to `core/auth/identity.py`, `public.py` retains:
- `connect()` — DuckDB connection factory
- `ensure_public_database(con)` — schema DDL for `users`, `site_admins`, `user_roles` tables
- `get_database_path()` — file path helper
- Browser helpers: `list_browser_tables()`, `query_browser_sql()`, `public_table_counts()`, `get_warehouse_status()`
- Private browser helpers (if they query the private DB path): `list_private_browser_tables()`, `query_private_browser_sql()`

The identity CRUD functions (`link_public_user`, `get_user_roles`, etc.) **move out** to `core/auth/identity.py` but the DDL for the tables they write to stays in `public.py` (table schema is a DB concern; CRUD operations on identity data are an auth concern).

### `core/db/private.py` — Absorbs write queue

Currently `privateDB.py` has:
- `initialize_private_database(owner_id)` — creates SQLite file + runs schema
- `get_private_session(owner_id)` — returns SQLAlchemy session
- `_private_engines` dict — engine cache

After absorbing `db_access.py`, it also has:
- `_OwnerState` class — per-owner write queue + drain thread
- `submit_private_write(owner_id, fn)` — enqueue a write callable
- `read_private(owner_id, sql, params)` — read helper

### `core/db/stats.py` — Absorbs stats publisher

Currently `stats.py` has: `get_table_stats()`, `optimization_hints()`

Absorbed from `core/queue/db.py`:
- `start_db_stats_publisher()` — daemon thread publishing `db/stats` to bus every 5s
- `get_db_gateway_stats()` — aggregate stats from writer + reader + market_buffer

### `core/db/__init__.py` — Update re-exports

```python
from core.db.public import connect, ensure_public_database, get_database_path
from core.db.private import initialize_private_database, get_private_session
# ... existing ensure_schema, warm_caches, initialize_all
```

All internal references updated: `publicDB` → `public`, `privateDB` → `private`.

---

## Operation E — Merge into `core/tasks/`

### Before

```
core/tasks/
  __init__.py          # re-exports: get_engine, SchedulerEngine, register_all_jobs
  scheduler.py         # SchedulerEngine daemon
  scheduler_db.py      # scheduler_jobs DDL + CRUD
  scheduler_jobs.py    # job catalog
  sde_loader.py        # SDE pipeline
```

### After

```
core/tasks/
  __init__.py          # re-exports: Task, enqueue, get_task, streams, engine, register_all_jobs
  queue.py             # Task dataclass, enqueue(), executors, lifecycle — from core/queue/scheduler.py
  engine.py            # SchedulerEngine daemon — renamed from scheduler.py
  persist.py           # scheduler_jobs DDL + CRUD — renamed from scheduler_db.py
  jobs.py              # job catalog — renamed from scheduler_jobs.py
  output.py            # log/rate SSE + stdout capture — from core/queue/streams.py
  context.py           # thread-local task_id — from core/queue/_context.py
  sde_loader.py        # SDE pipeline — unchanged
```

### `core/tasks/__init__.py` — New content

```python
"""Task execution and scheduling.

Task queue:   enqueue() → Task runs in ThreadPoolExecutor → logs stream via bus
Scheduler:    SchedulerEngine ticks every 30s, fires due jobs via enqueue()
Output:       stdout/stderr capture + SSE generators for live task logs
"""

from core.tasks.queue import (
    Task,
    enqueue,
    get_task,
    get_tasks_for_owner,
    get_all_tasks,
    cancel_task,
    clear_tasks,
)
from core.tasks.output import rate_stream, log_stream
from core.tasks.engine import get_engine, SchedulerEngine
from core.tasks.jobs import register_all_jobs

# Writer thread start/stop stays in core.db.writer — it's a DB concern
from core.db.writer import start_writer, stop_writer

__all__ = [
    "Task", "enqueue", "get_task", "get_tasks_for_owner", "get_all_tasks",
    "cancel_task", "clear_tasks",
    "rate_stream", "log_stream",
    "get_engine", "SchedulerEngine", "register_all_jobs",
    "start_writer", "stop_writer",
]
```

### Internal cross-references within `core/tasks/`

| From | To | Import |
|------|----|--------|
| `queue.py` | `context.py` | `from core.tasks.context import _thread_task` |
| `queue.py` | `output.py` | `from core.tasks.output import _TaskLogHandler, _ThreadRoutedWriter` |
| `queue.py` | `core.esi.request` | `from core.esi.request import set_request_lane` |
| `queue.py` | `core.bus` | `from core.bus.registry import register_topic` |
| `engine.py` | `queue.py` | `from core.tasks.queue import enqueue` |
| `engine.py` | `persist.py` | `from core.tasks.persist import ensure_tables, upsert_job_registration, ...` |
| `jobs.py` | `engine.py` | `from core.tasks.engine import SchedulerEngine` |
| `output.py` | `context.py` | `from core.tasks.context import _thread_task` |
| `output.py` | `queue.py` | `from core.tasks.queue import _registry` |

---

## Operation F — Update `applications/_api.py`

This is the highest-impact file outside core/. Every import changes.

### Import Migration Table

| Section | Old Import | New Import |
|---------|-----------|-----------|
| Auth decorators | `from core.web.auth import require_login, require_admin, require_role` | `from core.auth import require_login, require_admin, require_role` |
| Context | `from core.web.context import base_ctx` | `from core.web.context import base_ctx` *(unchanged)* |
| Config | `from core.config import get_runtime_settings` | *(unchanged)* |
| SDE | `import core.db.sde as sde` | *(unchanged)* |
| DB connection | `from core.db import publicDB as _pub` | `from core.db import public as _pub` |
| Private session | `from core.db.privateDB import get_private_session as _get_private_session` | `from core.db.private import get_private_session as _get_private_session` |
| DB reads | `from core.queue.db import (read_public, ...)` | `from core.db.reader import query_rows, query_one, query_scalar` |
| DB gateway stats | `from core.queue.db import get_db_gateway_stats` | `from core.db.stats import get_db_gateway_stats` |
| DB file stats | `from core.db.reader import get_db_file_stats` | *(unchanged)* |
| Private reads | `from core.queue.db import read_private` | `from core.db.private import read_private` |
| ESI HTTP | `from core.queue.esi_req import esi_get, esi_post, esi_request` | `from core.esi import esi_get, esi_post, esi_request` |
| ESI rate stats | `from core.queue.esi_req import get_esi_rate_limiter` | `from core.esi.rate import get_esi_rate_limiter` |
| Tokens | `from core.esi.auth import get_token, fresh_token, pick_token, resolve_default_owner_id` | `from core.auth import get_token, fresh_token, pick_token, resolve_default_owner_id` |
| ESI client | `from core.esi.generated.client import execute_operation, fetch_all_pages` | *(unchanged)* |
| Task queue | `from core.queue import enqueue, get_task, get_all_tasks, ...` | `from core.tasks import enqueue, get_task, get_all_tasks, ...` |
| Scheduler | `from core.tasks.scheduler import get_engine` | `from core.tasks.engine import get_engine` |
| ESI registry | `from core.esi.registry import get_registry_status` | *(unchanged)* |
| Bus | `from core.bus.handler import bus_handler` | *(unchanged)* |
| Bus helpers | `from core.bus import get_bus_log, get_all_topics, get_recent, publish` | *(unchanged)* |

### `db_admin` namespace update

Currently `db_admin` references `_pub.get_site_admin`, `_pub.upsert_site_admin`, etc. — these move to `core.auth.identity`:

```python
from core.auth.identity import (
    get_site_admin as _get_site_admin,
    list_users as _list_users,
    upsert_site_admin as _upsert_site_admin,
    delete_site_admin as _delete_site_admin,
)

db_admin = types.SimpleNamespace(
    list_tables=_pub.list_browser_tables,
    list_private_tables=_pub.list_private_browser_tables,
    query_sql=_pub.query_browser_sql,
    query_private_sql=_pub.query_private_browser_sql,
    table_counts=_pub.public_table_counts,
    get_warehouse_status=_pub.get_warehouse_status,
    get_site_admin=_get_site_admin,        # was _pub.get_site_admin
    list_users=_list_users,                # was _pub.list_public_users
    upsert_site_admin=_upsert_site_admin,  # was _pub.upsert_site_admin
    delete_site_admin=_delete_site_admin,   # was _pub.delete_site_admin
)
```

---

## Operation G — Update `main.py` and `core/web/__init__.py`

### `main.py`

```python
# OLD
from core.queue import start_writer, stop_writer

# NEW
from core.db.writer import start_writer, stop_writer
```

No other main.py imports reference `core.queue`.

### `core/web/__init__.py`

```python
# OLD
from core.web.auth import auth_bp
from core.queue.db import start_db_stats_publisher

# NEW
from core.auth.sso import auth_bp
from core.db.stats import start_db_stats_publisher
```

Scheduler imports:
```python
# OLD
from core.tasks.scheduler import get_engine
from core.tasks.scheduler_jobs import register_all_jobs

# NEW
from core.tasks.engine import get_engine
from core.tasks.jobs import register_all_jobs
```

---

## Operation H — Update `analysis/*` imports

These are mechanical import path updates. No logic changes.

### `analysis/character/populate.py`

```python
# OLD
from core.esi.auth import pick_token, fresh_token

# NEW
from core.auth import pick_token, fresh_token
```

### `analysis/market/regions.py`

```python
# OLD
from core.queue.esi_req import esi_get
from core.db.publicDB import connect as public_connect

# NEW
from core.esi import esi_get
from core.db.public import connect as public_connect
```

### `analysis/market/structures.py`

```python
# OLD
from core.queue.esi_req import esi_get
from core.db.publicDB import connect as public_connect
from core.esi.auth import pick_token, fresh_token, resolve_default_owner_id

# NEW
from core.esi import esi_get
from core.db.public import connect as public_connect
from core.auth import pick_token, fresh_token, resolve_default_owner_id
```

### `analysis/structures/discover.py`

```python
# OLD
from core.queue.esi_req import esi_get
from core.db.publicDB import connect as public_connect
from core.esi.auth import resolve_default_owner_id, pick_token, fresh_token

# NEW
from core.esi import esi_get
from core.db.public import connect as public_connect
from core.auth import resolve_default_owner_id, pick_token, fresh_token
```

> **Note:** These collectors still use `public_connect()` directly for writes, bypassing the writer thread. This is a known violation that Phase 7 addresses. Phase 1 only fixes import paths.

---

## Operation I — Update `utils/build/` codegen templates

Check `utils/build/esi_codegen.py` and `utils/build/domain_codegen.py` for hardcoded references to:
- `core.queue.esi_req` → should become `core.esi.request` or `core.esi`
- `core.esi.auth` → should become `core.auth.tokens` or `core.auth`

If found, update the template strings so regenerated code uses correct import paths. Then run `python build.py --gen-only` to verify.

---

## Verification Checklist

After all operations are complete:

- [ ] `grep -r "core\.queue" . --include="*.py"` returns zero matches (excluding `__pycache__`)
- [ ] `grep -r "core\.esi\.auth" . --include="*.py"` returns zero matches
- [ ] `grep -r "core\.web\.auth" . --include="*.py"` returns zero matches
- [ ] `grep -r "publicDB" . --include="*.py"` returns zero matches (excluding `__pycache__`)
- [ ] `grep -r "privateDB" . --include="*.py"` returns zero matches (excluding `__pycache__`)
- [ ] `python main.py` starts without import errors
- [ ] SSO login → callback → session creation works
- [ ] Role grant/revoke from admin panel works
- [ ] Scheduler fires a job → task completes → logs stream
- [ ] Market refresh completes via scheduler
- [ ] `python build.py --gen-only` regenerates without errors
- [ ] All application routes render (spot-check each /dashboard, /queue, /admin, /market, etc.)

---

## File Operation Summary

| Operation | Count | Details |
|-----------|-------|---------|
| **Created** | 8 | `core/auth/__init__.py`, `sso.py`, `credentials.py`, `tokens.py`, `identity.py`, `decorators.py`, `core/tasks/queue.py`, `core/tasks/output.py`, `core/tasks/context.py`, `core/esi/request.py`, `core/esi/rate.py` |
| **Renamed** | 4 | `publicDB.py` → `public.py`, `privateDB.py` → `private.py`, `scheduler.py` → `engine.py`, `scheduler_db.py` → `persist.py`, `scheduler_jobs.py` → `jobs.py` |
| **Modified** | ~15 | `applications/_api.py`, `main.py`, `core/web/__init__.py`, `core/web/context.py`, `core/web/setup.py`, `core/db/__init__.py`, `core/db/public.py`, `core/db/private.py`, `core/db/stats.py`, `core/esi/__init__.py`, `core/esi/cache.py`, `core/tasks/__init__.py`, `analysis/character/populate.py`, `analysis/market/regions.py`, `analysis/market/structures.py`, `analysis/structures/discover.py`, `utils/build/esi_codegen.py`, `utils/build/domain_codegen.py` |
| **Deleted** | 8 | `core/queue/__init__.py`, `core/queue/scheduler.py`, `core/queue/streams.py`, `core/queue/_context.py`, `core/queue/esi_req.py`, `core/queue/db.py`, `core/queue/db_access.py`, `core/web/auth.py`, `core/esi/auth.py` |

**Net change:** +3 files (8 created + 4 renamed − 9 deleted = +3, but code volume is lower due to dead code removal and gateway elimination)
