# Website Migration — Roadmap Overview

> **This is a planning document.** Each phase has its own detailed file.
> Reference target: `website layout.md`

---

## Executive Summary

Transform the EVE Data Framework from its current state into the architecture defined by `website layout.md`. The migration is structured as 7 sequential phases — a core infrastructure refactor first, then progressive application-layer work.

**Three structural problems this migration solves:**

1. **`core/queue/` is a dumping ground** — it holds task execution, ESI rate limiting, DB write gateway, SSE streams, per-owner private writes, and thread context. Six unrelated concerns in one namespace.
2. **Auth logic is scattered** — SSO lives in `core/web/auth.py`, token/credential management in `core/esi/auth.py`, role CRUD in `core/db/publicDB.py`, and decorators in `core/web/auth.py`. No unified auth framework.
3. **Application URLs don't match the target** — queue is at `/queue`, ESI browser at `/admin/esi`, DB browser at `/admin/db_browser`, scheduler at `/admin/scheduler`. The target surface is fundamentally different.

---

## Current vs Target State

### Core Framework Routes (Part 1 of target)

| Surface | Current State | Target State | Delta |
|---------|--------------|-------------|-------|
| `GET /` | Exists (`core/web/home.py`) | Same | None |
| `/setup` | Exists (GET + POST) | Add `GET /setup/owner` | Small |
| `/auth/*` | Exists (5 routes in `core/web/auth.py`) | Same, relocate to `core/auth/sso.py` | Internal move |
| `WS /bus` | Exists (`core/bus/websocket.py`) | Same | None |

### Application Routes (Part 2 of target)

| Surface | Current Prefix | Target Prefix | Action |
|---------|---------------|--------------|--------|
| Dashboard | `/dashboard` (1 route) | `/dashboard` (22 routes + WS) | **Massive expansion** |
| Admin | `/admin` (4 routes) | `/admin` (6 routes) | Medium expansion |
| DB Browser | `/admin/db_browser` (2 routes) | `/db` (8 routes + 2 WS) | **Major restructure** |
| ESI Queue | `/queue` (5 routes + 2 WS) | `/esi` (11 routes + 4 WS) | **Major merge** |
| ESI Browser | `/admin/esi` (3 routes) | *(merged into `/esi`)* | **Absorbed** |
| Scheduler | `/admin/scheduler` (3 routes) | `/scheduler` (5 routes) | Prefix change + expansion |
| System Status | `/admin/sys_status` (1 route + 1 WS) | `/system` (3 routes + 1 WS) | **Rename + expansion** |
| Market | `/market` (5 routes) | `/market` (6 routes) | Small expansion |
| SDE Browser | *(does not exist)* | `/sde` (6 routes) | **New application** |

### Route Counts

| | Current | Target | New |
|---|---|---|---|
| HTTP routes | ~28 | ~72 | +44 |
| WebSocket endpoints | 4 | 10 | +6 |
| Applications | 8 | 9 (+2 merged) | +1 net |

---

## Core/ Target Structure (after Phase 1)

```
core/
  __init__.py
  config.py              # Configuration — unchanged

  auth/                  # NEW — unified auth framework
    __init__.py          #   re-exports: decorators, token helpers, identity queries
    sso.py               #   OAuth2 flow (auth_bp), OAuthStateCache
    credentials.py       #   CredentialManager (Fernet client_id/secret)
    tokens.py            #   TokenDBManager, pick_token, fresh_token, get_token
    identity.py          #   User/admin/role CRUD (extracted from publicDB.py)
    decorators.py        #   require_login, require_admin, require_role

  bus/                   # Event bus — preserved, minor refinement
    __init__.py
    handler.py
    topics.py
    registry.py
    websocket.py
    process_pub.py

  db/                    # Data persistence — redesigned
    __init__.py          #   re-exports: ensure_schema, warm_caches, initialize_all
    public.py            #   was publicDB.py — DuckDB connection + schema DDL only
    private.py           #   was privateDB.py — SQLite sessions + absorbed write queue
    writer.py            #   serialized DuckDB write thread — unchanged
    reader.py            #   thread-safe DuckDB reads — unchanged
    sde.py               #   SDE caches — unchanged
    market_buffer.py     #   market order buffer — unchanged
    stats.py             #   DB metrics + stats publisher (absorbed from queue/db.py)
    models/
      __init__.py
      identity.py

  esi/                   # ESI access — redesigned
    __init__.py          #   re-exports: esi_get, esi_post, esi_request
    request.py           #   public API: esi_get/post/request + L1 cache orchestration
    rate.py              #   internal: EsiRateLimiter, FairAlternatingLock
    cache.py             #   L2 DuckDB cache + ETag — unchanged
    registry.py          #   ESI spec management — unchanged
    generated/           #   AUTO-GENERATED — never hand-edit
    personal/            #   AUTO-GENERATED
    corp/                #   AUTO-GENERATED
    public/              #   AUTO-GENERATED

  tasks/                 # Task execution + scheduling — merged
    __init__.py          #   re-exports: Task, enqueue, get_task, streams, engine
    queue.py             #   was core/queue/scheduler.py — Task, enqueue, executors
    engine.py            #   was core/tasks/scheduler.py — SchedulerEngine daemon
    persist.py           #   was core/tasks/scheduler_db.py — scheduler_jobs CRUD
    jobs.py              #   was core/tasks/scheduler_jobs.py — job catalog
    output.py            #   was core/queue/streams.py — log/rate SSE + stdout capture
    context.py           #   was core/queue/_context.py — thread-local task_id
    sde_loader.py        #   SDE pipeline — unchanged

  web/                   # Flask — slimmed (auth extracted)
    __init__.py          #   create_app() factory
    app.py               #   start_webUI()
    context.py           #   base_ctx() template helper
    home.py              #   public landing page
    setup.py             #   first-run credential wizard
    templates/

  queue/                 # ← DELETED ENTIRELY
```

### Import Hierarchy (verified cycle-free)

```
core/config   ← no deps
core/bus      ← no domain deps
core/db       ← config
core/auth     ← db, config
core/esi      ← db, auth, config, bus
core/tasks    ← db, esi, auth, bus, config
core/web      ← everything above
```

---

## Phase Dependency Graph

```
Phase 1  Core Infrastructure Refactor
  │
  ▼
Phase 2  Application Framework & URL Surface
  │
  ├──────────┬──────────┬──────────┐
  ▼          ▼          ▼          ▼
Phase 3    Phase 4    Phase 5    Phase 6
 /esi      /admin     /dashboard /scheduler
           + /db                 + /sde
                                 + /system
                 │
                 ▼
              Phase 7
              /market + Analysis Architecture
```

Phases 3–6 can proceed in **parallel** after Phase 2 completes.
Phase 7 depends on Phase 4 (reuses admin-tier UI patterns).

---

## Phase Summary

| Phase | File | Scope | Key Deliverables |
|-------|------|-------|-----------------|
| **1** | `phase-1.md` | Core infrastructure refactor | Dissolve `core/queue/`, extract `core/auth/`, redesign `core/esi/` and `core/db/`, standardize naming |
| **2** | `phase-2.md` | Application framework & URL surface | Merge queue_viewer + esi_browser → esi_viewer, restructure db_browser → db_viewer, create sde_browser shell, rename sys_status → system, move scheduler prefix |
| **3** | `phase-3.md` | `/esi` — unified queue + explorer | 11 routes + 4 WS: personal queue, admin queue, API explorer |
| **4** | `phase-4.md` | `/admin` + `/db` — admin suite | Full user management, dual-tier DB stats, schema browsers |
| **5** | `phase-5.md` | `/dashboard` — character platform | 22 routes + WS, 15 new collectors in `analysis/character/` |
| **6** | `phase-6.md` | `/scheduler` + `/sde` + `/system` | Operational tools: job management, SDE browser, system health |
| **7** | `phase-7.md` | `/market` + analysis architecture | Market type detail, collector write discipline, analysis vs collector split |

---

## Breaking Change Policy

Each phase can break things during execution but **must be self-consistent when complete**:
- All imports resolve
- `python main.py` starts without error
- All routes declared in the phase render correctly
- Scheduler, task queue, and auth flow work end-to-end

Phases are designed to be completed one at a time on a feature branch, then merged.

---

## Key Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | `core/queue/` dissolved entirely | 6 unrelated concerns; "queue" is not a meaningful namespace |
| 2 | `core/auth/` extracted as new framework | Auth was scattered across 3 packages; SSO, tokens, roles, levels, and decorators belong together |
| 3 | No "scheduler" naming collision | `engine.py` (daemon), `queue.py` (task execution), `jobs.py` (catalog), `persist.py` (DB CRUD) |
| 4 | `publicDB.py` → `public.py`, `privateDB.py` → `private.py` | Naming standardization |
| 5 | `esi_req.py` split into `request.py` + `rate.py` | Separate public API from internal engine |
| 6 | Bus system preserved and extended | Well-architected, user loves the pub/sub + WS pattern |
| 7 | WebSockets included with each phase | Not deferred — each application phase includes its WS endpoints |
| 8 | Collector write discipline deferred to Phase 7 | Core refactor focuses on framework; collector fixes are application-level |
| 9 | `write_private()` / `write_private_many()` are dead code | Audited — never called anywhere in the codebase. Deleted in Phase 1 |
| 10 | `core/queue/db.py` gateway eliminated | Callers import directly from source modules; gateway added indirection with no value |

---

## Audit Findings (from pre-planning research)

### Dead Code
- `write_private()` and `write_private_many()` in `core/queue/db.py` — defined but never called by any module
- Their re-exports in `core/queue/__init__.py` — also dead

### Naming Collisions
- "scheduler" appears as: `core/queue/scheduler.py` (task queue), `core/tasks/scheduler.py` (engine), `core/tasks/scheduler_db.py` (persistence)
- "writer" means different things: `core/db/writer.py` (DuckDB write thread), `core/queue/streams._ThreadRoutedWriter` (stdout capture)

### Bypass Violations
- `analysis/character/populate.py` uses `get_private_session()` + raw `session.execute()` / `session.commit()` — bypasses the non-existent private write queue entirely
- `analysis/market/regions.py`, `analysis/market/structures.py`, `analysis/structures/discover.py` all call `publicDB.connect()` directly and execute DDL + writes outside the writer thread
- `core/esi/cache.py` stores responses via `write_public_nowait()` (correct path) but reads via `publicDB.connect()` (direct)

### Re-export Confusion
- `db_write()` / `db_executemany()` are importable from: `core.db.writer`, `core.queue.__init__`, `core.queue.db` — three paths to the same function
- `enqueue()` is importable from: `core.queue.scheduler`, `core.queue.__init__`, `applications._api.tasks.enqueue` — three paths

---

*Each phase document contains: goals, file-by-file operations, specific function/import migrations, verification steps, and dependency declarations.*

# Phase Results

## Phase 1 — Core Infrastructure Refactor

**Status:** Complete

### Operations Completed

| Op | Scope | Summary |
|----|-------|---------|
| A | Dissolve `core/queue/` | Task queue → `core/tasks/queue.py`, streams → `core/tasks/output.py`, thread context → `core/tasks/context.py`. All 7 files + directory deleted. |
| B | Redesign `core/esi/` | `esi_req.py` split into `core/esi/rate.py` (engine) + `core/esi/request.py` (public API). `core/esi/__init__.py` re-exports `esi_get`, `esi_post`, `esi_request`. |
| C | Extract `core/auth/` | 6 new files: `decorators.py`, `credentials.py`, `tokens.py`, `identity.py`, `sso.py`, `__init__.py`. Auth scattered across 3 packages → unified framework. |
| D | Rename `core/db/` files | `publicDB.py` → `public.py`, `privateDB.py` → `private.py`. `stats.py` absorbed `get_db_gateway_stats`/`start_db_stats_publisher`. `private.py` absorbed `read_private`/`read_private_one`. |
| E | Merge `core/tasks/` | `scheduler.py` → `engine.py`, `scheduler_db.py` → `persist.py`, `scheduler_jobs.py` → `jobs.py`. `core/tasks/__init__.py` rewritten with unified re-exports. |
| F | Update `applications/_api.py` | All 8 import groups migrated to new paths. Identity functions moved to `core.auth.identity` namespace. |
| G | Update `core/web/` | `auth_bp` from `core.auth.sso`, stats from `core.db.stats`, scheduler from `core.tasks.engine`/`jobs`. `setup.py` → `core.auth.credentials`. `context.py` → `core.db.private`. |
| H | Update analysis imports | `regions.py`, `structures.py`, `discover.py`, `populate.py` — all updated to new `core.db.public`, `core.esi`, `core.auth` paths. |
| I | Update codegen templates | `esi_codegen.py` template + `generated/client.py` updated: `core.queue.esi_req` → `core.esi.request`. |

### Additional Updates
- `core/db/writer.py` — `publicDB` → `public`, `core.queue._context` → `core.tasks.context`
- `core/db/reader.py` — `publicDB` → `public`
- `core/db/market_buffer.py` — `publicDB` → `public`
- `core/db/sde.py` — `publicDB` → `public`
- `core/db/stats.py` — `publicDB` → `public`, removed dead `db_access` import
- `core/esi/cache.py` — `publicDB` → `public`, docstring updated
- `core/esi/registry.py` — `publicDB` → `public`, `esi_req` → `request`
- `core/bus/websocket.py` — `publicDB.get_user_roles` → `core.auth.identity`
- `core/bus/topics.py` — logger prefix map updated for new module paths
- `core/tasks/sde_loader.py` — `publicDB` → `public`
- `example.config.yaml` — logger names updated to new module paths
- Test files — all 3 updated to new paths

### Files Deleted (13)
`core/queue/__init__.py`, `core/queue/_context.py`, `core/queue/db.py`, `core/queue/db_access.py`, `core/queue/esi_req.py`, `core/queue/scheduler.py`, `core/queue/streams.py`, `core/web/auth.py`, `core/esi/auth.py`, `core/db/publicDB.py`, `core/db/privateDB.py`, `core/tasks/scheduler.py`, `core/tasks/scheduler_db.py`, `core/tasks/scheduler_jobs.py`

### Verification
- Zero `from core.db.publicDB` / `from core.db import publicDB` imports in codebase
- Zero `from core.db.privateDB` / `from core.db import privateDB` imports in codebase
- Zero `from core.queue` / `import core.queue` imports in codebase
- Zero `core.esi.auth` / `core.web.auth` imports in codebase
- Zero `core.tasks.scheduler_db` / `core.tasks.scheduler_jobs` imports in codebase
- Directory structure matches target specification in roadmap

## Phase 7 — `/market` + Analysis Architecture

- **Status:** Complete
- **Files created:** `applications/market_browser/templates/market_type.html`, `applications/market_browser/static/market_type.js`, `analysis/market/history.py`
- **Files deleted:** None
- **Files modified:** `applications/market_browser/routes.py` (added `type_detail` and `type_history` routes, added `abort`, `sde`, `raw_esi` imports), `applications/market_browser/templates/market_browser.html` (added "Detail →" link to type detail page), `applications/market_browser/static/market_browser.css` (added `.mt-order-grid` and `.tw-scroll` styles for type detail page), `analysis/market/__init__.py` (re-exports `fetch_market_history`, `cache_history_rows`), `analysis/__init__.py` (replaced brief docstring with full architecture documentation)
- **Key changes:** Added market type detail page (`GET /market/type/<type_id>`) with type metadata, full buy/sell order book, and Chart.js price history chart with 30d/90d/1y toggles. Added JSON history endpoint (`GET /market/type/<type_id>/history`) that checks DuckDB cache first then falls back to ESI. Created `analysis/market/history.py` collector with `market_history` table DDL and `cache_history_rows()` function using the writer's `db_executemany()`. Audited all analysis collectors for write discipline — DuckDB collectors already route data writes through `core/db/writer.py` via `core/db/public.py` helper functions. Updated `analysis/__init__.py` with formal architecture documentation.
- **Deviations from plan:** (1) DuckDB write discipline refactoring (Part B) was unnecessary — all collectors already use `core/db/public.py` functions which delegate to `db_write`/`db_executemany`/`db_write_dataframe`. The spec assumed direct `con.execute()` data writes existed; they don't. (2) SQLite write discipline: the spec's `write_private()` / `write_private_batch()` functions don't exist — they were explicitly identified as dead code in Phase 1 audit and deleted. Current SQLAlchemy engine pattern with WAL mode + busy_timeout is safe and idiomatic. No refactoring applied. (3) No Chart.js CDN bundling — using CDN link (`chart.js@4`) rather than vendoring the library.
- **Known issues:** None. All 7 phases are now complete.
