# Phase 4 — `/admin` + `/db` — Administration Suite

> **Depends on:** Phase 1 (core refactor), Phase 2 (admin_panel + db_viewer shells created)
> **Blocks:** Nothing (parallel with Phases 3, 5, 6)
> **Scope:** `applications/admin_panel/`, `applications/db_viewer/`

---

## Goal

Refactor the admin panel to the target URL surface from `website layout.md`. Split the current monolithic `admin_panel` into a focused user-management tool and create a dedicated `db_viewer` application for database browsing. Both gain WebSocket-backed live stats via the bus.

---

## Target Route Table

### Admin Panel — `/admin`

| Method | Route | Auth | Source | Implementation |
|--------|-------|------|--------|---------------|
| GET | `/admin/` | `[admin]` | admin_panel index | **Rebuild** — dashboard with user count, admin count, role summary |
| GET | `/admin/users` | `[admin]` | admin_panel users | **Port** — paginated user list with role chips |
| GET | `/admin/users/<owner_id>` | `[admin]` | admin_panel user detail | **Port + expand** — character list, roles, admin status, last login |
| POST | `/admin/users/<owner_id>/roles` | `[admin]` | admin_panel grant/revoke | **Port** — add/remove named roles |
| POST | `/admin/users/<owner_id>/admin` | `[site_owner]` | admin_panel toggle admin | **Port** — promote/demote site admin |
| POST | `/admin/users/<owner_id>/delete` | `[site_owner]` | *(new)* | **New** — remove user and their data |
| WS | `/admin/ws` | `[admin]` | *(new)* | **New** — subscribe to `admin/events` (user login/logout, role changes) |

### DB Viewer — `/db`

| Method | Route | Auth | Source | Implementation |
|--------|-------|------|--------|---------------|
| GET | `/db/` | `[role:db]` | db_browser index | **Port + split** — personal: own SQLite tables; admin: public DuckDB tables |
| GET | `/db/public` | `[admin]` | db_browser public | **Port** — DuckDB table list with row counts |
| GET | `/db/public/<table>` | `[admin]` | db_browser table detail | **Port** — schema + paginated data + filter |
| GET | `/db/private` | `[role:db]` | db_browser private | **Port** — user's own SQLite tables |
| GET | `/db/private/<table>` | `[role:db]` | db_browser private table | **Port** — schema + data for user's SQLite |
| POST | `/db/query` | `[admin]` | db_browser query | **Port** — execute read-only SQL on DuckDB |
| GET | `/db/stats` | `[role:db]` | *(new)* | **New** — table sizes, row counts, last-modified times |
| WS | `/db/ws` | `[role:db]` | *(new)* | **New** — subscribe to `db/stats` for live table metrics |

---

## Implementation Details — Admin Panel

### Admin Dashboard (`GET /admin/`)

**Data sources:**
- `db_admin.list_users()` → user list (count for dashboard card)
- `db_admin.list_site_admins()` → admin list (count for dashboard card)
- Role distribution: `SELECT role, COUNT(*) FROM user_roles GROUP BY role`

**Template: `admin_index.html`**
- Summary cards: total users, total admins, total roles granted
- Recent logins (if event bus captures login events — new `auth/login` topic)
- Quick links to user management

### User List (`GET /admin/users`)

**Data sources:**
- `db_admin.list_users()` → `[{owner_id, character_name, ...}]`
- For each user, `core.auth.identity.get_user_roles(owner_id)` → role list

**Template: `admin_users.html`**
- Sortable table: owner_id, character name, roles (as chips/badges), admin badge, actions
- Search/filter input (client-side)
- Link each row to `/admin/users/<owner_id>`

**Port from:** `admin_panel/routes.py` user management routes

### User Detail (`GET /admin/users/<owner_id>`)

**Data sources:**
- `db_admin.get_user(owner_id)` or direct `core.auth.identity` query
- `core.auth.identity.get_user_roles(owner_id)` → role list
- `core.auth.identity.is_site_admin(owner_id)` → bool
- Character list from private DB: `char_data.get_character(owner_id)`

**Template: `admin_user_detail.html`**
- Character portrait + name
- Linked characters table
- Role management: current roles with remove buttons, add-role form
- Admin status toggle (site_owner only)
- Delete user button (site_owner only, with confirmation modal)

### Role Management (`POST /admin/users/<owner_id>/roles`)

```python
@admin_bp.route("/users/<int:owner_id>/roles", methods=["POST"])
@require_admin
def manage_roles(owner_id):
    action = request.form["action"]  # "grant" or "revoke"
    role = request.form["role"]

    if action == "grant":
        core.auth.identity.grant_user_roles(owner_id, [role], granted_by=session["owner_id"])
    elif action == "revoke":
        core.auth.identity.revoke_user_role(owner_id, role)

    # Publish event to bus
    bus.publish("admin/events", {
        "type": "role_change",
        "owner_id": owner_id,
        "action": action,
        "role": role,
        "by": session["owner_id"],
    })

    return redirect(url_for("admin_panel.user_detail", owner_id=owner_id))
```

### Admin Toggle (`POST /admin/users/<owner_id>/admin`)

```python
@admin_bp.route("/users/<int:owner_id>/admin", methods=["POST"])
@require_role("site_owner")  # Only site_owner can promote/demote admins
def toggle_admin(owner_id):
    action = request.form["action"]  # "promote" or "demote"
    if action == "promote":
        db_admin.upsert_site_admin(owner_id)
    elif action == "demote":
        db_admin.remove_site_admin(owner_id)
    return redirect(url_for("admin_panel.user_detail", owner_id=owner_id))
```

### User Deletion (`POST /admin/users/<owner_id>/delete`)

**New endpoint.** Only `site_owner` can delete users.

```python
@admin_bp.route("/users/<int:owner_id>/delete", methods=["POST"])
@require_role("site_owner")
def delete_user(owner_id):
    if owner_id == session["owner_id"]:
        flash("Cannot delete yourself", "error")
        return redirect(url_for("admin_panel.user_detail", owner_id=owner_id))

    # Remove from DuckDB: users, user_roles, site_admins
    core.auth.identity.delete_user(owner_id)

    # Optionally: remove private DB file
    # This is destructive — confirm with dialog before reaching this endpoint

    return redirect(url_for("admin_panel.users"))
```

> **Note:** `core.auth.identity.delete_user()` is a new function that needs to be added in Phase 1 or at the start of this phase.

---

## Implementation Details — DB Viewer

### Personal View (`GET /db/private`)

**Data source:**
- `db.private_query(owner_id, "SELECT name FROM sqlite_master WHERE type='table'")` → table list

The personal tier shows only the current user's private SQLite tables. No cross-owner queries.

### Admin View (`GET /db/public`)

**Data source:**
- `db_admin.list_tables()` → DuckDB table list with row counts

### Table Detail (`GET /db/public/<table>` or `/db/private/<table>`)

**Data source (public):**
- `db_admin.query_sql(f"DESCRIBE {table}")` → schema  *(table name validated against list_tables)*
- `db_admin.query_sql(f"SELECT * FROM {table} LIMIT ? OFFSET ?", [limit, offset])` → paginated data

**Data source (private):**
- Same via `db.private_query(owner_id, ...)` *(table name validated against sqlite_master)*

**Security:** Table names are validated against the known table list. They are never interpolated from raw user input. Use an allowlist check:

```python
known_tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
if table not in known_tables:
    abort(404)
```

### SQL Console (`POST /db/query`)

Admin-only. Execute arbitrary read-only SQL on DuckDB.

```python
@db_bp.route("/query", methods=["POST"])
@require_admin
def run_query():
    sql = request.form["sql"]
    # Safety: DuckDB read-only connection or BEGIN READ ONLY
    try:
        result = db_admin.query_sql(sql)
        return jsonify({"columns": result["columns"], "rows": result["rows"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
```

**Port from:** `db_browser/routes.py` query endpoint

### DB Stats (`GET /db/stats`)

**New endpoint** returning JSON with table metrics:

```python
@db_bp.route("/stats")
@require_role("db")
def stats():
    tables = db_admin.list_tables()  # admin sees all
    if not is_admin():
        # Non-admin: only show private table stats
        tables = get_private_tables(session["owner_id"])
    return jsonify(tables)
```

### Live Stats WebSocket (`WS /db/ws`)

Subscribe to `db/stats` bus topic. Stats are published periodically (e.g. every 60s) or on significant write events.

**Bus topic:** `db/stats`
- Publisher: `core/db/writer.py` — emit after each batch write completes
- Payload: `{"table": "market_orders", "action": "insert", "rows_affected": 15000, "ts": "..."}`

---

## Bus Topic Declarations

| Topic | Publisher | Access | Description |
|-------|----------|--------|-------------|
| `admin/events` | `admin_panel/routes.py` | `[admin]` | User management events (role changes, admin promotions) |
| `auth/login` | `core/auth/sso.py` | `[admin]` | Login events (new session for user) |
| `db/stats` | `core/db/writer.py` | `role:db` | Write activity notifications |

---

## JavaScript Architecture

### `admin_panel.js`

- WebSocket to `/bus` subscribing to `admin/events`
- Live notification badges when user roles change
- Confirmation modals for destructive actions (delete user, demote admin)

### `db_viewer.js`

- Client-side table search/filter
- Paginated data loading (fetch next page via AJAX)
- SQL console with submit + response table rendering
- WebSocket to `/bus` subscribing to `db/stats` for live row-count updates
- JSON syntax highlighting for cell values containing structured data

---

## Templates

### Admin Panel

| Template | Extends | Purpose |
|----------|---------|---------|
| `admin_index.html` | `base.html` | Dashboard with summary cards |
| `admin_users.html` | `base.html` | Paginated user list with role chips |
| `admin_user_detail.html` | `base.html` | Single user: characters, roles, admin toggle |

### DB Viewer

| Template | Extends | Purpose |
|----------|---------|---------|
| `db_index.html` | `base.html` | Landing: links to public/private |
| `db_public.html` | `base.html` | DuckDB table list |
| `db_private.html` | `base.html` | User's SQLite table list |
| `db_table.html` | `base.html` | Schema + paginated data (shared for both DBs) |
| `db_query.html` | `base.html` | SQL console (admin only) |

---

## Migration from Current Apps

### admin_panel → admin_panel (in-place refactor)

The current `admin_panel` has:
- User management (keep and expand)
- Log viewer (move to `/system` in Phase 6)
- Stats (split: DB stats → `/db`, system stats → `/system`)

**What stays:** User list, user detail, role management
**What moves:** Log viewer → Phase 6 (`/system`), DB stats → `/db`
**What's new:** User deletion, admin dashboard, bus event publishing

### db_browser → db_viewer (new package)

The current `db_browser` has:
- Public DuckDB browsing
- Private SQLite browsing
- SQL console

**All three port to `db_viewer`** with cleaner URL structure and personal/admin tier split.

---

## New Core Functions Needed

If not added in Phase 1, these must be added at the start of this phase:

| Function | Location | Purpose |
|----------|----------|---------|
| `delete_user(owner_id)` | `core/auth/identity.py` | Remove user from users, user_roles, site_admins |
| `is_admin(owner_id)` | `core/auth/identity.py` | Check if user is site_admin (may already exist) |

---

## Verification Checklist

- [ ] `GET /admin/` shows dashboard with user/admin/role counts
- [ ] `GET /admin/users` shows paginated user list with role badges
- [ ] `GET /admin/users/<id>` shows user detail with character list and role management
- [ ] `POST /admin/users/<id>/roles` grants/revokes roles correctly
- [ ] `POST /admin/users/<id>/admin` promotes/demotes admins (site_owner only)
- [ ] `POST /admin/users/<id>/delete` deletes user (site_owner only, not self)
- [ ] `GET /db/` shows landing page with personal/admin links
- [ ] `GET /db/public` lists DuckDB tables (admin only)
- [ ] `GET /db/public/<table>` shows schema + paginated data
- [ ] `GET /db/private` shows user's SQLite tables
- [ ] `GET /db/private/<table>` shows schema + data for user's SQLite
- [ ] `POST /db/query` executes read-only SQL (admin only)
- [ ] WebSocket connections to `/bus` with admin/db topics work
- [ ] Non-admin users cannot access `/admin/` or `/db/public`
- [ ] SQL injection is impossible — table names validated against allowlist

---

## File Operation Summary

| Operation | Count | Details |
|-----------|-------|---------|
| **Modified** | ~6 | admin_panel routes.py, __init__.py, templates (3+); db_viewer routes.py |
| **Created** | ~8 | db_viewer package (routes.py, __init__.py, templates, static), new admin templates |
| **Deleted** | 0 | (old db_browser already deleted in Phase 2) |
