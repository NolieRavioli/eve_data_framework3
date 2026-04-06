# Phase 6 — `/scheduler` + `/sde` + `/system` — Operational Tools

> **Depends on:** Phase 1 (core refactor), Phase 2 (application shells created)
> **Blocks:** Nothing (parallel with Phases 3–5)
> **Scope:** `applications/scheduler/`, `applications/sde_browser/` (new), `applications/system/` (renamed from `sys_status/`)

---

## Goal

Expand the three operational/admin tools to their full `website layout.md` surface:

1. **Scheduler** — add job detail pages, run history, interval editing
2. **SDE Browser** — new application for SDE status, ID↔name lookup, and entity detail pages
3. **System** — renamed from sys_status; process metrics, git version check, system update, live bus log console

---

## Part A — `/scheduler` — Background Job Management

### Target Route Table

| Method | Route | Auth | Source | Implementation |
|--------|-------|------|--------|---------------|
| GET | `/scheduler/` | `[admin]` | existing | **Expand** — add last-run status, next-run countdown |
| GET | `/scheduler/<job_id>` | `[admin]` | `[TBD]` | **New** — job detail: description, fn_path, full run history |
| POST | `/scheduler/<job_id>/toggle` | `[admin]` | existing | **Port** — enable/disable toggle |
| POST | `/scheduler/<job_id>/run-now` | `[admin]` | existing | **Port** — enqueue immediate run |
| POST | `/scheduler/<job_id>/interval` | `[admin]` | `[TBD]` | **New** — change job interval |

### Implementation Details

#### Job List Expansion (`GET /scheduler/`)

**Current state:** Shows job_id, label, enabled, interval, next_run.
**Add:** Last run timestamp, last run status (success/failure/running), next-run countdown timer (JS).

**Data source:** `scheduler.list_jobs()` — need to extend the return dict to include `last_run_at`, `last_run_status`, `last_task_id`.

**Required core change:** `core/tasks/persist.py` (formerly `scheduler_db.py`) needs columns:

```sql
ALTER TABLE scheduler_jobs ADD COLUMN IF NOT EXISTS last_run_at TIMESTAMP;
ALTER TABLE scheduler_jobs ADD COLUMN IF NOT EXISTS last_run_status TEXT;
ALTER TABLE scheduler_jobs ADD COLUMN IF NOT EXISTS last_task_id TEXT;
```

Update `core/tasks/engine.py` (formerly `scheduler.py`) to write these columns after each job run.

#### Job Detail (`GET /scheduler/<job_id>`)

**Data sources:**
- `scheduler.get_job(job_id)` → job metadata (need to add this method)
- Run history: stored in a new `scheduler_run_history` table or derived from task queue history

**Template: `scheduler_detail.html`**
- Job metadata: ID, label, function path, interval, enabled status
- Run history table: timestamp, duration, status (success/failed/cancelled), task_id link to `/esi/<task_id>`
- Interval change form
- Run-now button

#### Run History Storage

**Option A — New table in DuckDB:**
```sql
CREATE TABLE IF NOT EXISTS scheduler_run_history (
    run_id      TEXT PRIMARY KEY,
    job_id      TEXT NOT NULL,
    task_id     TEXT,
    started_at  TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    status      TEXT,  -- 'success' | 'failed' | 'cancelled'
    error       TEXT
)
```

**Option B — Derive from task queue:** Task objects already capture start/end/status. Add `job_id` to the Task dataclass and query completed tasks filtered by job_id.

**Recommendation:** Option A. A dedicated table survives task queue clearing and provides persistent audit history.

#### Interval Change (`POST /scheduler/<job_id>/interval`)

```python
@scheduler_bp.route("/<job_id>/interval", methods=["POST"])
@require_admin
def change_interval(job_id):
    new_interval = int(request.form["interval_s"])
    if new_interval < 60:  # minimum 1 minute
        flash("Interval must be at least 60 seconds", "error")
        return redirect(url_for("scheduler.detail", job_id=job_id))
    scheduler.set_interval(job_id, new_interval)
    return redirect(url_for("scheduler.detail", job_id=job_id))
```

**Required core change:** Add `set_interval(job_id, interval_s)` to `core/tasks/engine.py` → updates `scheduler_jobs.interval_s` and recalculates `next_run`.

---

## Part B — `/sde` — Static Data Edition Browser

### Target Route Table

| Method | Route | Auth | Source | Implementation |
|--------|-------|------|--------|---------------|
| GET | `/sde/` | `[admin]` | *(new)* | **New** — SDE status card + per-table row counts + lookup tool |
| POST | `/sde/update` | `[admin]` | *(new)* | **New** — enqueue SDE loader pipeline |
| GET | `/sde/lookup` | `[admin]` | *(new)* | **New** — search by name or ID across types/systems/regions |
| GET | `/sde/lookup/type/<int:type_id>` | `[admin]` | *(new)* | **New** — type detail page |
| GET | `/sde/lookup/system/<int:system_id>` | `[admin]` | *(new)* | **New** — solar system detail page |
| GET | `/sde/lookup/region/<int:region_id>` | `[admin]` | *(new)* | **New** — region detail page |

### Application Scaffold

```
applications/sde_browser/
  __init__.py
  routes.py
  templates/
    sde_index.html
    sde_lookup.html
    sde_type.html
    sde_system.html
    sde_region.html
  static/
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
        description="Static Data Edition status and lookup tools.",
        url_prefix="/sde",
        required_scopes=[],
        nav_weight=75,
        nav_section="admin",
        access_level="admin",
        required_role=None,
    )

    def create_blueprint(self):
        return routes.sde_bp


Tool = SDEBrowser()
```

### Implementation Details

#### SDE Status (`GET /sde/`)

**Data sources:**
- Row counts per SDE table: `SELECT COUNT(*) FROM dim_types`, `dim_groups`, `dim_categories`, `dim_regions`, `dim_constellations`, `dim_systems`, `dim_stations`
- SDE version/date: from `_publicData/esi_specs/` or a metadata row
- Last loaded timestamp: store as a metadata row or derive from file modification time of `_sde/`

**Template: `sde_index.html`**
- Status card: SDE version, last loaded timestamp
- Table row-count cards: one card per dim_* table
- "Update SDE" button → `POST /sde/update`
- Quick lookup form: text input + search button → `GET /sde/lookup?q=...`

#### SDE Update (`POST /sde/update`)

```python
@sde_bp.route("/update", methods=["POST"])
@require_admin
def update_sde():
    from core.tasks.sde_loader import run_sde_pipeline
    task_id = tasks.enqueue("SDE Update", run_sde_pipeline, queue="public")
    return redirect(url_for("esi_viewer.task_detail", task_id=task_id))
```

#### Lookup (`GET /sde/lookup`)

**Query param:** `?q=<search_term>`

Search across multiple SDE tables:
```python
@sde_bp.route("/lookup")
@require_admin
def lookup():
    q = request.args.get("q", "").strip()
    if not q:
        return render_template("sde_lookup.html", **base_ctx("sde_browser"), results=None)

    results = {"types": [], "systems": [], "regions": []}

    con = db.connect()
    try:
        # Try numeric ID first
        if q.isdigit():
            type_id = int(q)
            row = con.execute("SELECT type_id, name_en FROM dim_types WHERE type_id = ?", [type_id]).fetchone()
            if row:
                results["types"].append({"type_id": row[0], "name": row[1]})

            sys_row = con.execute("SELECT system_id, system_name FROM dim_systems WHERE system_id = ?", [type_id]).fetchone()
            if sys_row:
                results["systems"].append({"system_id": sys_row[0], "name": sys_row[1]})

        # Name search (case-insensitive LIKE)
        name_param = f"%{q}%"
        results["types"] = [
            {"type_id": r[0], "name": r[1]}
            for r in con.execute(
                "SELECT type_id, name_en FROM dim_types WHERE name_en ILIKE ? LIMIT 50", [name_param]
            ).fetchall()
        ]
        results["systems"] = [
            {"system_id": r[0], "name": r[1]}
            for r in con.execute(
                "SELECT system_id, system_name FROM dim_systems WHERE system_name ILIKE ? LIMIT 50", [name_param]
            ).fetchall()
        ]
        results["regions"] = [
            {"region_id": r[0], "name": r[1]}
            for r in con.execute(
                "SELECT region_id, region_name FROM dim_regions WHERE region_name ILIKE ? LIMIT 50", [name_param]
            ).fetchall()
        ]
    finally:
        con.close()

    return render_template("sde_lookup.html", **base_ctx("sde_browser"), results=results, query=q)
```

#### Type Detail (`GET /sde/lookup/type/<int:type_id>`)

**Data source:** `dim_types` + `dim_groups` + `dim_categories` (JOINed)

**Template: `sde_type.html`**
- Type name, type ID
- Group name → Category name
- Base price, packaged volume, mass
- Description (if available)
- Market group breadcrumb (if applicable)

#### System Detail (`GET /sde/lookup/system/<int:system_id>`)

**Data source:** `dim_systems` + `dim_constellations` + `dim_regions` (JOINed)

**Template: `sde_system.html`**
- System name, system ID
- Region → Constellation
- Security status (colored: green > 0.5, yellow > 0.0, red ≤ 0.0)
- Star type (if in SDE)
- Stations in system (from `dim_stations`)

#### Region Detail (`GET /sde/lookup/region/<int:region_id>`)

**Data source:** `dim_regions` + `dim_constellations` + `dim_systems`

**Template: `sde_region.html`**
- Region name, region ID
- Constellation list (expandable → systems per constellation)
- Station count

---

## Part C — `/system` — Python Runtime

### Target Route Table

| Method | Route | Auth | Source | Implementation |
|--------|-------|------|--------|---------------|
| GET | `/system/` | `[admin]` | sys_status (partial) | **Rebuild** — process metrics + git version + bus log console |
| POST | `/system/update` | `[site_owner]` | *(new)* | **New** — git pull + deps + restart |
| WS | `/system/ws/process` | `[admin]` | *(new)* | **New** — CPU/RAM/thread metrics every 10s |

### Application Rename

`sys_status/` → `system/`

```python
# applications/system/__init__.py
from applications._api import BaseTool, ToolManifest
from applications.system import routes


class SystemTool(BaseTool):
    manifest = ToolManifest(
        id="system",
        name="System",
        icon="⚙",
        description="Runtime process metrics, version management, and bus log console.",
        url_prefix="/system",
        required_scopes=[],
        nav_weight=90,
        nav_section="admin",
        access_level="admin",
        required_role=None,
    )

    def create_blueprint(self):
        return routes.system_bp


Tool = SystemTool()
```

### Implementation Details

#### Runtime Overview (`GET /system/`)

**Data sources:**
- `psutil.Process()` → CPU usage %, RSS memory, VMS memory, thread count
- `subprocess.check_output(["git", "describe", "--tags", "--always"])` → current version
- GitHub API → latest release (cached, refreshed every 10 min)

**Template: `system_index.html`**
- Process metrics cards: CPU %, RAM (RSS/VMS in MB), thread count
- Per-thread identity table (if available via threading.enumerate())
- Git version card: current commit/tag vs latest GitHub release
- "Update System" button (site_owner only, with confirmation modal)
- Live bus log console: `<div id="bus-log">` with topic filter checkboxes

**Dependencies:** Add `psutil` to `requirements.txt` (if not already present).

#### Process Metrics Publisher

A background daemon thread that publishes system metrics to the bus:

```python
# core/tasks/process_monitor.py (new)
import psutil
import threading
import time
import logging

logger = logging.getLogger(__name__)

def start_process_monitor(bus, interval=10):
    """Start a daemon thread that publishes process metrics every `interval` seconds."""
    proc = psutil.Process()

    def _monitor():
        while True:
            try:
                cpu = proc.cpu_percent(interval=1)
                mem = proc.memory_info()
                threads = threading.active_count()
                bus.publish("system/process", {
                    "cpu_percent": cpu,
                    "rss_mb": round(mem.rss / 1048576, 1),
                    "vms_mb": round(mem.vms / 1048576, 1),
                    "threads": threads,
                })
            except Exception:
                logger.exception("Process monitor error")
            time.sleep(interval - 1)  # cpu_percent already sleeps 1s

    t = threading.Thread(target=_monitor, daemon=True, name="ProcessMonitor")
    t.start()
    return t
```

Start from `create_app()` in `core/web/__init__.py`.

#### System Update (`POST /system/update`)

**Site owner only.** Requires a CSRF-like confirmation token (random string generated per page load, embedded in hidden form field, validated on POST).

```python
@system_bp.route("/update", methods=["POST"])
@require_role("site_owner")
def update_system():
    confirm_token = request.form.get("confirm_token")
    expected = session.pop("system_update_token", None)
    if not confirm_token or confirm_token != expected:
        flash("Invalid confirmation token", "error")
        return redirect(url_for("system.index"))

    def _do_update():
        import subprocess
        subprocess.check_call(["git", "pull", "origin", "main"])
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        logger.info("System updated. Manual restart required.")
        # Note: hot restart is complex — log a message telling admin to restart

    task_id = tasks.enqueue("System Update", _do_update, queue="public")
    return redirect(url_for("esi_viewer.task_detail", task_id=task_id))
```

#### Bus Log Console

The `/system/` page includes a live log console that connects to `WS /bus` (the centralized bus WebSocket) and displays messages from all topics the admin is authorized to see.

**Client-side:**
```javascript
// system.js
const bus = new BusClient(["*"]);  // Subscribe to all (server filters by access)

const logContainer = document.getElementById("bus-log");
const activeTopics = new Set();  // User's topic filter checkboxes

bus.onMessage((msg) => {
    if (activeTopics.size === 0 || activeTopics.has(msg.topic)) {
        appendLogLine(logContainer, msg);
    }
});
```

**Topic filter checkboxes:** Dynamically generated from the bus topic registry. Admin sees all registered topics.

### WebSocket Route

```python
from flask_sock import Sock

sock = Sock()

@sock.route("/system/ws/process")
@require_admin
def process_ws(ws):
    # Subscribe to system/process topic on bus, forward to ws
    ...
```

Or the client connects to `WS /bus` and subscribes to `system/process`.

---

## Bus Topic Declarations

| Topic | Publisher | Access | Description |
|-------|----------|--------|-------------|
| `system/process` | `core/tasks/process_monitor.py` | `[admin]` | CPU/RAM/thread metrics every 10s |
| `system/update` | `applications/system/routes.py` | `[admin]` | System update progress events |

---

## Templates

### Scheduler

| Template | Purpose |
|----------|---------|
| `scheduler_index.html` | Job list with status + countdown (existing, expanded) |
| `scheduler_detail.html` | Job detail: metadata + run history + interval form |

### SDE Browser

| Template | Purpose |
|----------|---------|
| `sde_index.html` | Status card + row counts + lookup form |
| `sde_lookup.html` | Search results grouped by type/system/region |
| `sde_type.html` | Type detail page |
| `sde_system.html` | Solar system detail page |
| `sde_region.html` | Region detail page |

### System

| Template | Purpose |
|----------|---------|
| `system_index.html` | Process metrics + git version + bus log console |

---

## New Core Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `process_monitor.py` | `core/tasks/` | Daemon thread publishing system metrics |
| `scheduler.set_interval()` | `core/tasks/engine.py` | Change job interval at runtime |
| `scheduler.get_job()` | `core/tasks/engine.py` | Get single job metadata |
| `scheduler_run_history` | `core/tasks/persist.py` | Run history table DDL + CRUD |

---

## Verification Checklist

### Scheduler
- [ ] `GET /scheduler/` shows all jobs with last-run status and next-run countdown
- [ ] `GET /scheduler/<job_id>` shows job detail with run history
- [ ] `POST /scheduler/<job_id>/toggle` enables/disables jobs
- [ ] `POST /scheduler/<job_id>/run-now` enqueues immediate run and redirects to task view
- [ ] `POST /scheduler/<job_id>/interval` changes interval (min 60s)

### SDE Browser
- [ ] `GET /sde/` shows SDE status with per-table row counts
- [ ] `POST /sde/update` enqueues SDE pipeline and redirects to task view
- [ ] `GET /sde/lookup?q=Tritanium` finds the type
- [ ] `GET /sde/lookup?q=30000142` finds Jita by system ID
- [ ] `GET /sde/lookup/type/34` shows Tritanium detail
- [ ] `GET /sde/lookup/system/30000142` shows Jita detail with stations
- [ ] `GET /sde/lookup/region/10000002` shows The Forge with constellations

### System
- [ ] `GET /system/` shows CPU, RAM, thread count
- [ ] `GET /system/` shows git version vs latest GitHub release
- [ ] `POST /system/update` requires site_owner + confirmation token
- [ ] `WS /system/ws/process` streams metrics every 10s
- [ ] Bus log console displays live events with topic filtering
- [ ] Non-admin users cannot access any `/system/` routes

---

## File Operation Summary

| Operation | Count | Details |
|-----------|-------|---------|
| **Created** | ~15 | sde_browser package (6 files), system templates, scheduler_detail.html, process_monitor.py, scheduler run history |
| **Modified** | ~6 | scheduler routes.py, engine.py, persist.py, system routes.py, requirements.txt |
| **Renamed** | 1 | sys_status/ → system/ |
| **Deleted** | 1 | sys_status/ (after rename) |
