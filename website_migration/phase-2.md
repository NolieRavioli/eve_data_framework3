# Phase 2 — Application Framework & URL Surface

> **Depends on:** Phase 1 (core refactor complete)
> **Blocks:** Phases 3–7 (all application-layer work)
> **Scope:** `applications/` only — core is stable after Phase 1

---

## Goal

Restructure all application packages to match the URL surface defined in `website layout.md`. Create shells for new applications, merge overlapping applications, and establish the URL prefix each app will own for all subsequent phases.

After this phase, every target URL prefix has a corresponding application package, even if the routes within are stubs. Subsequent phases fill out the implementations.

---

## Current Application Inventory

| Package | Manifest ID | Current Prefix | nav_section | access_level | required_role |
|---------|-------------|---------------|-------------|-------------|--------------|
| `dashboard/` | `dashboard` | `/dashboard` | `overview` | `user` | `dashboard` |
| `queue_viewer/` | `queue_viewer` | `/queue` | `tools` | `user` | `queue` |
| `admin_panel/` | `admin_panel` | `/admin` | `admin` | `admin` | None |
| `db_browser/` | `db_browser` | `/admin/db_browser` | `admin` | `admin` | None |
| `esi_browser/` | `esi_browser` | `/admin/esi` | `admin` | `admin` | None |
| `market_browser/` | `market_browser` | `/market` | `apps` | `public` | None |
| `scheduler/` | `scheduler` | `/admin/scheduler` | `admin` | `admin` | `scheduler` |
| `sys_status/` | `sys_status` | `/admin/sys_status` | `admin` | `admin` | None |

---

## Target Application Surface

| Package | Manifest ID | Target Prefix | nav_section | access_level | required_role | Action |
|---------|-------------|--------------|-------------|-------------|--------------|--------|
| `dashboard/` | `dashboard` | `/dashboard` | `overview` | `user` | `dashboard` | **Keep** (expand in Phase 5) |
| `esi_viewer/` | `esi_viewer` | `/esi` | `tools` | `user` | `queue` | **NEW** — merge queue_viewer + esi_browser |
| `admin_panel/` | `admin_panel` | `/admin` | `admin` | `admin` | None | **Keep** (expand in Phase 4) |
| `db_viewer/` | `db_viewer` | `/db` | `admin` | `user` | None | **NEW** — restructure from db_browser |
| `market_browser/` | `market_browser` | `/market` | `apps` | `public` | None | **Keep** (expand in Phase 7) |
| `scheduler/` | `scheduler` | `/scheduler` | `admin` | `admin` | `scheduler` | **Move prefix** |
| `system/` | `system` | `/system` | `admin` | `admin` | None | **NEW** — rename from sys_status |
| `sde_browser/` | `sde_browser` | `/sde` | `admin` | `admin` | None | **NEW** — create from scratch |

### Deleted Applications

| Package | Reason |
|---------|--------|
| `queue_viewer/` | Merged into `esi_viewer/` |
| `esi_browser/` | Merged into `esi_viewer/` |
| `sys_status/` | Renamed to `system/` |
| `db_browser/` | Replaced by `db_viewer/` |

---

## Step 1 — Create `applications/esi_viewer/`

Merge `queue_viewer/` (task management, log streaming, rate cards) with `esi_browser/` (ESI operation catalog, execute endpoint) into a single unified application.

### Package Structure

```
applications/esi_viewer/
  __init__.py              # ToolManifest + ESIViewer tool class
  routes.py                # All routes — personal, admin, explorer
  templates/
    esi_index.html         # Personal queue view
    esi_task.html          # Single task detail
    esi_admin.html         # Admin global queue view
    esi_explore.html       # ESI operation browser
    esi_operation.html     # Single operation detail
  static/
    esi_viewer.css
    esi_viewer.js
```

### `__init__.py`

```python
from applications._api import BaseTool, ToolManifest
from applications.esi_viewer import routes


class ESIViewer(BaseTool):
    manifest = ToolManifest(
        id="esi_viewer",
        name="ESI Queue",
        icon="⚡",
        description="ESI request queue, rate monitoring, and API explorer.",
        url_prefix="/esi",
        required_scopes=[],
        nav_weight=-50,
        nav_section="tools",
        access_level="user",
        required_role="queue",
    )

    def create_blueprint(self):
        return routes.esi_bp


Tool = ESIViewer()
```

### `routes.py` — Stub Routes

For Phase 2, routes are stubs that render placeholder templates. Phase 3 fills in the real implementations.

```python
from flask import Blueprint, render_template
from applications._api import base_ctx, require_role, require_admin

esi_bp = Blueprint("esi_viewer", __name__,
                   template_folder="templates",
                   static_folder="static")


# ── Personal tier ─────────────────────────────────────
@esi_bp.route("/")
@require_role("queue")
def index():
    return render_template("esi_index.html", **base_ctx("esi_viewer"))


@esi_bp.route("/<task_id>")
@require_role("queue")
def task_detail(task_id):
    return render_template("esi_task.html", task_id=task_id, **base_ctx("esi_viewer"))


@esi_bp.route("/<task_id>/cancel", methods=["POST"])
@require_role("queue")
def cancel_task(task_id):
    pass  # Phase 3


@esi_bp.route("/clear", methods=["POST"])
@require_role("queue")
def clear_tasks():
    pass  # Phase 3


# ── Admin tier ────────────────────────────────────────
@esi_bp.route("/admin/")
@require_admin
def admin_index():
    return render_template("esi_admin.html", **base_ctx("esi_viewer"))


# ── Explorer ──────────────────────────────────────────
@esi_bp.route("/explore/")
@require_admin
def explore_index():
    return render_template("esi_explore.html", **base_ctx("esi_viewer"))


@esi_bp.route("/explore/<operation_id>")
@require_admin
def explore_operation(operation_id):
    return render_template("esi_operation.html", operation_id=operation_id, **base_ctx("esi_viewer"))


@esi_bp.route("/explore/<operation_id>/run", methods=["POST"])
@require_admin
def explore_run(operation_id):
    pass  # Phase 3
```

### Port Code From

| Source File | What to Port | Target |
|-------------|-------------|--------|
| `queue_viewer/routes.py` | Task list, cancel, clear, log stream | `esi_viewer/routes.py` personal tier |
| `queue_viewer/templates/` | Task list template, task detail template | `esi_viewer/templates/` |
| `queue_viewer/static/` | CSS, JS for task view, rate cards | `esi_viewer/static/` |
| `esi_browser/routes.py` | Operation list, detail, execute | `esi_viewer/routes.py` explorer tier |
| `esi_browser/templates/` | Operation list, detail templates | `esi_viewer/templates/` |
| `esi_browser/static/` | CSS, JS for operation browser | `esi_viewer/static/` |

WebSocket routes are declared but not wired until Phase 3.

---

## Step 2 — Create `applications/db_viewer/`

Restructure `db_browser/` into a dual-tier application: personal view (any user sees own DB stats) and admin view (global stats + schema browser).

### Package Structure

```
applications/db_viewer/
  __init__.py
  routes.py
  templates/
    db_personal.html       # Personal DB stats
    db_admin.html          # Global DB stats
    db_public_browser.html # DuckDB schema browser
    db_private_browser.html # SQLite schema browser
  static/
    db_viewer.css
    db_viewer.js
```

### `__init__.py`

```python
from applications._api import BaseTool, ToolManifest
from applications.db_viewer import routes


class DBViewer(BaseTool):
    manifest = ToolManifest(
        id="db_viewer",
        name="Database",
        icon="⛁",
        description="Database statistics, schema browser, and SQL query tool.",
        url_prefix="/db",
        required_scopes=[],
        nav_weight=5,
        nav_section="admin",
        access_level="user",      # personal tier is user-accessible
        required_role=None,
    )

    def create_blueprint(self):
        return routes.db_bp


Tool = DBViewer()
```

### Key Routes

```python
# Personal tier — any authenticated user
@db_bp.route("/")
@require_login
def personal_stats(): ...

# Admin tier — stats
@db_bp.route("/admin/")
@require_admin
def admin_stats(): ...

# Admin tier — browsers
@db_bp.route("/public/")
@require_admin
def public_browser(): ...

@db_bp.route("/public/query", methods=["POST"])
@require_admin
def public_query(): ...

@db_bp.route("/<int:owner_id>/")
@require_admin
def private_browser(owner_id): ...

@db_bp.route("/<int:owner_id>/query", methods=["POST"])
@require_admin
def private_query(owner_id): ...
```

### Port Code From

| Source | What | Target |
|--------|------|--------|
| `db_browser/routes.py` | Schema browser, SQL query execution | `db_viewer/routes.py` browser routes |
| `db_browser/templates/` | Browser template | `db_viewer/templates/` |
| `db_browser/static/` | CSS, JS | `db_viewer/static/` |

New: personal stats page and admin stats page are created fresh — no existing code to port.

---

## Step 3 — Rename `applications/sys_status/` → `applications/system/`

### Changes

1. Rename the directory: `sys_status/` → `system/`
2. Update `__init__.py`:

```python
class SystemStatus(BaseTool):
    manifest = ToolManifest(
        id="system",              # was "sys_status"
        name="System",            # was "System Status"
        icon="⊞",
        description="Python runtime overview, process metrics, and system updates.",
        url_prefix="/system",     # was "/admin/sys_status"
        required_scopes=[],
        nav_weight=90,
        nav_section="admin",
        access_level="admin",
        required_role=None,
    )
```

3. Update blueprint name in `routes.py`: `Blueprint("system", ...)` (was `"sys_status"`)
4. Update template references: `url_for('system.static', ...)`, `url_for('system.index', ...)`
5. Add stub routes for Phase 6 targets:
   - `POST /system/update` (site_owner only)
   - `WS /system/ws/process`

---

## Step 4 — Move `applications/scheduler/` Prefix

### Changes

1. Update `__init__.py`:

```python
manifest = ToolManifest(
    id="scheduler",
    name="Scheduler",
    icon="⏱",
    description="Background job management.",
    url_prefix="/scheduler",      # was "/admin/scheduler"
    required_scopes=[],
    nav_weight=5,
    nav_section="admin",
    access_level="admin",
    required_role="scheduler",
)
```

2. No route changes needed (relative paths within the blueprint stay the same).
3. Add stub routes for Phase 6 targets:
   - `GET /scheduler/<job_id>` (job detail)
   - `POST /scheduler/<job_id>/interval` (change interval)

---

## Step 5 — Create `applications/sde_browser/`

Brand new application. SDE status dashboard and lookup tool.

### Package Structure

```
applications/sde_browser/
  __init__.py
  routes.py
  templates/
    sde_index.html         # SDE status + table counts + lookup form
    sde_type.html          # Type detail
    sde_system.html        # System detail
    sde_region.html        # Region detail
  static/
    sde_browser.css
    sde_browser.js
```

### `__init__.py`

```python
from applications._api import BaseTool, ToolManifest
from applications.sde_browser import routes


class SDEBrowser(BaseTool):
    manifest = ToolManifest(
        id="sde_browser",
        name="SDE Browser",
        icon="📚",
        description="Static Data Edition browser and lookup tool.",
        url_prefix="/sde",
        required_scopes=[],
        nav_weight=10,
        nav_section="admin",
        access_level="admin",
        required_role=None,
    )

    def create_blueprint(self):
        return routes.sde_bp


Tool = SDEBrowser()
```

### Stub Routes

```python
@sde_bp.route("/")
@require_admin
def index(): ...            # SDE status cards + table counts

@sde_bp.route("/update", methods=["POST"])
@require_admin
def update(): ...           # Enqueue SDE loader

@sde_bp.route("/lookup")
@require_admin
def lookup(): ...           # Cross-table search

@sde_bp.route("/lookup/type/<int:type_id>")
@require_admin
def type_detail(type_id): ...

@sde_bp.route("/lookup/system/<int:system_id>")
@require_admin
def system_detail(system_id): ...

@sde_bp.route("/lookup/region/<int:region_id>")
@require_admin
def region_detail(region_id): ...
```

---

## Step 6 — Delete Merged/Replaced Applications

After creating the new packages and verifying they load:

1. **Delete `applications/queue_viewer/`** — absorbed into `esi_viewer/`
2. **Delete `applications/esi_browser/`** — absorbed into `esi_viewer/`
3. **Delete `applications/db_browser/`** — replaced by `db_viewer/`
4. **Delete `applications/sys_status/`** — renamed to `system/`

---

## Step 7 — Update `applications/_api.py` (if needed)

Phase 1 already redirected all core imports. Phase 2 should not require `_api.py` changes unless:
- New adapter functions are needed for SDE browser (e.g., SDE table stats)
- DB viewer personal stats need a new stats query helper

If so, add minimal imports as needed following the established pattern:
```python
from core.db.stats import get_table_stats
# add to __all__
```

---

## Step 8 — Update `example.config.yaml`

Document new role names if any. The `queue` role now grants access to `/esi` instead of `/queue`. Add a comment noting this change.

---

## Verification Checklist

- [ ] `python main.py` starts without errors
- [ ] Sidebar nav shows correct applications in correct sections:
  - overview: Dashboard
  - tools: ESI Queue
  - apps: Market Browser
  - admin: Admin, Database, Scheduler, SDE Browser, System
- [ ] `GET /esi/` renders (stub OK)
- [ ] `GET /db/` renders (stub OK)
- [ ] `GET /sde/` renders (stub OK)
- [ ] `GET /system/` renders (stub OK)
- [ ] `GET /scheduler/` renders (no `/admin` prefix)
- [ ] Old URLs return 404:
  - `/queue` → 404
  - `/admin/esi` → 404
  - `/admin/db_browser` → 404
  - `/admin/sys_status` → 404
  - `/admin/scheduler` → 404
- [ ] `GET /market/` still works (unchanged)
- [ ] `GET /dashboard/` still works (unchanged)
- [ ] `GET /admin/` still works (unchanged)

---

## File Operation Summary

| Operation | Count | Details |
|-----------|-------|---------|
| **Created** | ~12 | `esi_viewer/` (5 files), `db_viewer/` (5 files), `sde_browser/` (5 files) |
| **Modified** | ~4 | `scheduler/__init__.py`, `system/__init__.py`, `system/routes.py`, possibly `_api.py` |
| **Renamed** | 1 | `sys_status/` → `system/` |
| **Deleted** | ~12 | `queue_viewer/` (~6 files), `esi_browser/` (~5 files), `db_browser/` (~5 files) |
