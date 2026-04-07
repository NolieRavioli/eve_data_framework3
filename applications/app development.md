# Application Development Guide

All services are imported from `applications._api`. Never import from `core.*` directly.

---

## Defining a tool

```python
from applications._api import BaseTool, ToolManifest, base_ctx, require_role
from applications.my_tool import routes

class MyTool(BaseTool):
    manifest = ToolManifest(
        id="my_tool",
        name="My Tool",
        icon="★",
        description="One-line description.",
        url_prefix="/tools/my_tool",
        nav_section="apps",   # "overview"|"tools"|"apps"|"admin"|"" (hidden)
        access_level="user",  # "public"|"user"|"admin"|"site_owner"
        required_role="my_tool",  # None = level-check only
        nav_weight=50,
    )
    def create_blueprint(self):
        return routes.my_bp

Tool = MyTool()
```

Routes use `@require_role("my_tool")` (admins bypass automatically). Prefer it over bare `@require_login`.

---

## SDE lookups — `sde.*`

In-memory cache, always fast, no DB round-trip.

| Function | Returns |
|---|---|
| `sde.name_from_type_id(type_id)` | `str` — English name, or `"Unknown [id]"` |
| `sde.type_id_from_name(name)` | `int \| None` |
| `sde.suggest_type_names(prefix, limit=10)` | `list[str]` — autocomplete |
| `sde.group_id_from_type_id(type_id)` | `int \| None` |
| `sde.group_name(group_id)` | `str` |
| `sde.category_id_from_type(type_id)` | `int \| None` |
| `sde.category_name(category_id)` | `str` |
| `sde.market_group_from_type_id(type_id)` | `int \| None` |
| `sde.load_market_tree()` | Nested market group tree |
| `sde.get_flat_market_map()` | `dict[group_id, name]` |
| `sde.get_types_in_group(group_id)` | `list[int]` |
| `sde.resolve_type_ids(raw_query)` | `set[int]` — parse a name or ID string |
| `sde.region_id_from_system_id(system_id)` | `int \| None` |
| `sde.system_name_from_id(system_id)` | `str` |
| `sde.region_name_from_id(region_id)` | `str` |
| `sde.security_from_system_id(system_id)` | `float \| None` |
| `sde.blueprint_for_type(blueprint_type_id)` | `dict \| None` — blueprint data |
| `sde.reprocess_materials(type_id)` | `list[dict]` — reprocessing outputs |
| `sde.dogma_attributes(type_id)` | `dict[attr_name, float]` |
| `sde.dogma_effects(type_id)` | `list[int]` — effect IDs |

---

## Database reads — `db.*`

All `db` methods read from the shared DuckDB warehouse. They are thread-safe.

```python
from applications._api import db

# Returns list[dict]
rows = db.query("SELECT type_id, name_en FROM dim_types WHERE group_id = ?", [group_id])

# Returns dict | None
row = db.query_one("SELECT * FROM market_orders WHERE order_id = ?", [order_id])

# Returns a single scalar value
count = db.scalar("SELECT COUNT(*) FROM market_orders WHERE region_id = ?", [10000002])

# Best market price (checks live buffer first, then DB)
best_sell = db.market_price(type_id=34, region_id=10000002, buy=False)
best_buy  = db.market_price(type_id=34, region_id=10000002, buy=True)
```

Key public tables:

| Table | Contents |
|---|---|
| `market_orders` | Live orders: `type_id`, `price`, `is_buy_order`, `region_id`, `location_id`, `volume_remain` |
| `dim_types` | `type_id`, `name_en`, `group_id`, `market_group_id`, `volume`, `mass` |
| `dim_stations` | `station_id`, `station_name`, `region_id`, `system_id` |
| `dim_regions` | `region_id`, `region_name` |
| `dim_groups` | `group_id`, `group_name`, `category_id` |
| `dim_categories` | `category_id`, `category_name` |
| `structures` | Player structures: `structure_id`, `name`, `region_id`, `type_id` |

### Per-character private SQLite

```python
rows = db.private_query(owner_id, "SELECT * FROM character_skills WHERE character_id = ?", {"character_id": char_id})
```

Private tables: `character_skills`, `character_wallet`, `character_assets`.

---

## Character data — `char_data.*`

```python
from applications._api import char_data

# Returns dict with: character_id, name, scopes, token_expires
char = char_data.get_character(owner_id, character_id)

# All characters for an owner
chars = char_data.get_characters(owner_id)

# List of granted ESI scope strings
scopes = char_data.get_scopes(owner_id, character_id)
```

---

## Convenience helpers

```python
from applications._api import get_regions, DEFAULT_REGION

regions = get_regions()      # list[{"id": int, "name": str}] sorted by name
forge   = DEFAULT_REGION     # 10000002 — The Forge (Jita)
```

---

## Triggering background work — `tasks.enqueue`

Long-running work (ESI fetches, calculations) must run in a background worker, not in a route.

```python
from applications._api import tasks
from collectors.market.regions import fetch_all_market_data

task_id = tasks.enqueue(
    "Market refresh",       # display name shown in queue viewer
    fetch_all_market_data,  # callable — must be a top-level importable function
    owner_id=0,             # 0 = public/system task; user's owner_id for private work
    queue="public",         # "public" for shared data; omit (default "private") for per-user
)
# Redirect to live progress:
return redirect(url_for("queue_viewer.task_progress", task_id=task_id))
```

Workers run in a thread. Use Python `logging` — output is captured and streamed live to the browser.

**The worker callable must**:
- Be a top-level function (importable by path), not a lambda or closure
- Live in `analysis/<domain>/worker.py`, not inside applications
- Never call routes or import from `applications.*`

---

## Scheduled jobs — `scheduler.*`

```python
from applications._api import scheduler

scheduler.list_jobs()                        # list[dict] — all registered jobs
scheduler.set_enabled("market_refresh", True)
task_id = scheduler.run_now("market_refresh")  # enqueues immediately, returns task_id
```

To add a new scheduled job, see scheduler_jobs.py.

---

## Monitoring — `queue_info.*`

```python
from applications._api import queue_info

all_tasks  = queue_info.get_all_tasks()           # list[Task]
task       = queue_info.get_task(task_id)         # Task | None
owner_tasks = queue_info.get_tasks_for_owner(owner_id)

queue_info.cancel_task(task_id)

# SSE generators (for streaming endpoints)
yield from queue_info.rate_stream()
yield from queue_info.log_stream(task_id)
```

---

## Auth tokens — `token_resolution.*`

Only needed if a route needs to make a live ESI call on behalf of a character (rare — prefer analysis workers).

```python
from applications._api import token_resolution

owner_id = token_resolution.resolve_default_owner_id()
char_id, token_data = token_resolution.pick_token(owner_id)
char_id, fresh = token_resolution.fresh_token(owner_id, char_id, token_data)
access_token = fresh["access_token"]
```

---

## Template patterns

Extend `base.html`. Pass context via `base_ctx("tool_id")`:

```html
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

Pass data to JavaScript via `data-*` attributes — never inline JSON in `<script>` tags:

```html
<div id="app-data" data-task-id="{{ task_id }}" data-owner="{{ owner_id }}"></div>
```

```javascript
const el = document.getElementById("app-data");
const taskId = el.dataset.taskId;
```

---

## Rules

- **Never** import from `core.*` in a route, `__init__.py`, or template
- **Never** write to DuckDB from a route — enqueue an analysis worker instead
- **Never** call `requests` directly — use `tasks.enqueue` to trigger analysis workers
- **Never** put business logic in a route — routes render; workers compute
- Worker files inside `applications/<name>/worker.py` are allowed only for lightweight in-process computation (no ESI, no DB writes)