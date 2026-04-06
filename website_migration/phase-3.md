# Phase 3 — `/esi` — Queue & API Explorer Unification

> **Depends on:** Phase 1 (core refactor), Phase 2 (esi_viewer shell created)
> **Blocks:** Nothing (parallel with Phases 4–6)
> **Scope:** `applications/esi_viewer/` — filling out stubs from Phase 2

---

## Goal

Implement the full `/esi` surface as defined in `website layout.md`: personal queue with task management, admin global queue, and ESI API explorer. All three tiers share a single application package with WebSocket-backed live updates via the bus system.

---

## Target Route Table

### Personal Tier — `/esi`

| Method | Route | Auth | Source | Implementation |
|--------|-------|------|--------|---------------|
| GET | `/esi/` | `[role:queue]` | queue_viewer index | **Port + rebuild** — rate cards (hidden when idle) + task list (active/completed) |
| GET | `/esi/<task_id>` | `[role:queue]` + ownership | queue_viewer task detail | **Port** — name, status badge, rate mini-bar, live log |
| POST | `/esi/<task_id>/cancel` | `[role:queue]` + ownership | queue_viewer cancel | **Port** — signal pending task |
| POST | `/esi/clear` | `[role:queue]` | queue_viewer clear | **Port** — remove completed/failed tasks |
| WS | `/esi/ws` | `[role:queue]` | queue_viewer SSE → bus | **Convert** — subscribe to `esi/rate` + `queue/tasks`, owner-filtered |
| WS | `/esi/<task_id>/ws` | `[role:queue]` + ownership | queue_viewer log SSE → bus | **Convert** — subscribe to `task/<task_id>/log` |

### Admin Tier — `/esi/admin`

| Method | Route | Auth | Source | Implementation |
|--------|-------|------|--------|---------------|
| GET | `/esi/admin/` | `[admin]` | *(new)* | **New** — global rate cards + per-owner task groups |
| WS | `/esi/admin/ws` | `[admin]` | *(new)* | **New** — subscribe to `esi/rate` + `queue/tasks`, unfiltered |

### Explorer Tier — `/esi/explore`

| Method | Route | Auth | Source | Implementation |
|--------|-------|------|--------|---------------|
| GET | `/esi/explore/` | `[admin]` | esi_browser index | **Port** — grouped by tag, searchable |
| GET | `/esi/explore/<operation_id>` | `[admin]` | esi_browser detail | **Port** — params, schema, scopes, example |
| POST | `/esi/explore/<operation_id>/run` | `[admin]` | esi_browser execute | **Port** — execute with user's token |

---

## Implementation Details

### Personal Queue Index (`GET /esi/`)

**Data sources:**
- `queue_info.get_tasks_for_owner(owner_id)` → list of Task dicts (active + completed)
- `queue_info.get_esi_rate_stats()` → rate limiter bucket state per character

**Template:**
- Rate-limit cards (one per character with active ESI traffic). Cards hidden when bucket usage is zero — use `data-*` attributes to pass rate values to JS.
- Task table: name, status (pending/running/complete/failed), started_at, duration, action buttons (cancel, view logs)
- "Clear completed" button → `POST /esi/clear`

**Port from:** `queue_viewer/routes.py` index route + `queue_viewer/templates/queue.html`

### Task Detail (`GET /esi/<task_id>`)

**Data sources:**
- `queue_info.get_task(task_id)` → single Task dict
- Ownership check: `task.owner_id == session["owner_id"]` or user is admin

**Template:**
- Task name + status badge
- ESI rate mini-bar (from bus `esi/rate` topic)
- Live scrolling log console (from bus `task/<task_id>/log` topic via WebSocket)

**Port from:** `queue_viewer/routes.py` task_detail + `queue_viewer/templates/task.html`

### SSE to WebSocket Conversion

The current `queue_viewer` uses SSE (Server-Sent Events) via `rate_stream()` and `log_stream()` from `core/tasks/output.py`. The target architecture uses the bus WebSocket system instead.

**Current flow:**
```
Browser → GET /queue/stream/rate → SSE → rate_stream() generator
Browser → GET /queue/stream/<task_id> → SSE → log_stream() generator
```

**New flow:**
```
Browser → WS /esi/ws → subscribe to esi/rate, queue/tasks
Browser → WS /esi/<task_id>/ws → subscribe to task/<task_id>/log
```

**Implementation:**
- The bus already publishes `esi/rate` events (from `core/esi/rate.py` via `_esi_rate_hook`)
- The bus already publishes `task/<task_id>/log` events (from `core/tasks/output.py` `_TaskLogHandler`)
- Per-application WebSocket routes connect to `WS /bus` with topic filtering
- Alternatively, create thin WS endpoints that internally subscribe to the bus:

```python
from applications._api import bus_handler

@sock.route("/esi/ws")
@require_role("queue")
def esi_ws(ws):
    owner_id = session["owner_id"]
    topics = [f"esi/rate/{owner_id}", "queue/tasks"]
    # Subscribe to bus, filter by owner, forward to ws
    ...
```

Or — simpler — the client connects to `WS /bus` directly and subscribes to the relevant topics. The per-app WS routes in `website layout.md` may be convenience aliases that the client-side JS handles by connecting to `/bus` with the right topic subscriptions.

**Decision for this phase:** Use the centralized `WS /bus` endpoint with client-side topic subscriptions. The per-app WS routes (`/esi/ws`, `/esi/<task_id>/ws`, `/esi/admin/ws`) are thin wrappers that auto-subscribe to the correct topics based on auth context.

### Admin Queue (`GET /esi/admin/`)

**Data sources:**
- `queue_info.get_all_tasks()` → all tasks across all owners
- `queue_info.get_esi_rate_stats()` → global rate stats (all characters)

**Template:**
- Global rate cards (all characters, all owners)
- Per-owner grouped task table
- No cancel/clear actions (admin observes but does not interfere with other users' tasks)

### ESI Explorer (`GET /esi/explore/`)

**Data sources:**
- `esi_manifest.get_operations()` → sorted list of all ESI operations
- `esi_manifest.get_meta()` → compatibility date, counts

**Template:**
- Operations grouped by ESI tag (Markets, Characters, Corporations, ...)
- Search input filtering by path, description, scope
- Each row links to `/esi/explore/<operation_id>`

**Port from:** `esi_browser/routes.py` index + `esi_browser/templates/admin_esi.html`

### Operation Detail (`GET /esi/explore/<operation_id>`)

**Data sources:**
- `esi_manifest.get_operation(operation_id)` → single operation dict

**Template:**
- HTTP method badge + full path
- Description
- Path parameters with types
- Query parameters with types + defaults
- Response schema (expandable tree)
- Required ESI scopes
- "Execute" form with parameter inputs → `POST /esi/explore/<operation_id>/run`

### Execute Operation (`POST /esi/explore/<operation_id>/run`)

**Implementation:**
```python
@esi_bp.route("/explore/<operation_id>/run", methods=["POST"])
@require_admin
def explore_run(operation_id):
    op = esi_manifest.get_operation(operation_id)
    if not op:
        abort(404)

    # Build params from form
    path_params = {k: request.form[k] for k in op.get("path_params", {}) if k in request.form}
    query_params = {k: request.form[k] for k in op.get("query_params", {}) if k in request.form}

    # Get user's token if scopes are needed
    token = None
    if op.get("security"):
        owner_id = session["owner_id"]
        char_id, token_data = token_resolution.pick_token(owner_id)
        _, fresh_data = token_resolution.fresh_token(owner_id, char_id, token_data)
        token = f"Bearer {fresh_data['access_token']}"

    result = esi.execute(operation_id, path_params=path_params, query_params=query_params, token=token)
    return jsonify(result)
```

---

## JavaScript Architecture

### `esi_viewer.js` — Shared Utilities

```javascript
// WebSocket connection to /bus
class BusClient {
    constructor(topics) {
        this.ws = new WebSocket(`ws://${location.host}/bus`);
        this.ws.onopen = () => {
            this.ws.send(JSON.stringify({action: "subscribe", topics}));
        };
    }
    onMessage(handler) {
        this.ws.onmessage = (e) => handler(JSON.parse(e.data));
    }
}
```

### `esi_personal.js` — Personal Queue

- Subscribe to `esi/rate` (owner-filtered) + `queue/tasks` (owner-filtered)
- Update rate cards on rate events
- Update task table on task lifecycle events
- Auto-scroll log console on `task/<id>/log` events

### `esi_explorer.js` — Operation Browser

- Client-side search filtering
- Execute form submission + response display
- JSON syntax highlighting for responses

---

## Templates

| Template | Extends | Blocks Used |
|----------|---------|------------|
| `esi_index.html` | `base.html` | `title`, `content`, `scripts` |
| `esi_task.html` | `base.html` | `title`, `content`, `scripts` |
| `esi_admin.html` | `base.html` | `title`, `content`, `scripts` |
| `esi_explore.html` | `base.html` | `title`, `content`, `scripts` |
| `esi_operation.html` | `base.html` | `title`, `content`, `scripts` |

All templates follow the `pg-hd` / `pg-body` pattern from existing templates.

---

## Bus Topic Declarations

Ensure these topics are registered in `core/bus/topics.py` or dynamically via `register_topic()`:

| Topic | Publisher | Access | Description |
|-------|----------|--------|-------------|
| `esi/rate` | `core/esi/rate.py` | `role:queue` | Rate limiter bucket snapshots |
| `queue/tasks` | `core/tasks/queue.py` | `role:queue` | Task lifecycle events (created, started, completed, failed) |
| `task/<task_id>/log` | `core/tasks/output.py` | `role:queue` + ownership | Per-task log lines |

---

## Verification Checklist

- [ ] `GET /esi/` shows rate cards + task list with real data
- [ ] `GET /esi/<task_id>` shows task detail with live log streaming via WebSocket
- [ ] `POST /esi/<task_id>/cancel` cancels a pending task
- [ ] `POST /esi/clear` clears completed tasks
- [ ] `GET /esi/admin/` shows global queue across all owners (admin only)
- [ ] `GET /esi/explore/` lists all ESI operations grouped by tag
- [ ] `GET /esi/explore/<op_id>` shows operation detail with parameters
- [ ] `POST /esi/explore/<op_id>/run` executes an operation and returns JSON
- [ ] WebSocket connections to `/bus` with ESI topics work
- [ ] Non-admin users cannot access `/esi/admin/` or `/esi/explore/`
- [ ] Rate cards hide when no ESI traffic is active

---

## File Operation Summary

| Operation | Count | Details |
|-----------|-------|---------|
| **Modified** | ~5 | `routes.py` (fill stubs), templates (5), static JS/CSS |
| **Created** | ~3 | Additional JS files if split |
| **Deleted** | 0 | (old apps already deleted in Phase 2) |
