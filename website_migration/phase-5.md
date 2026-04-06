# Phase 5 — `/dashboard` — Character Data Platform

> **Depends on:** Phase 1 (core refactor), Phase 2 (dashboard shell created)
> **Blocks:** Nothing (parallel with Phases 3, 4, 6)
> **Scope:** `applications/dashboard/`, `analysis/character/`
> **Sub-phases:** 5a (existing data), 5b (new collectors), 5c (sub-route views), 5d (WebSocket)

---

## Goal

Transform `/dashboard` from a minimal character overview into the full character-data platform described in `website layout.md`. This means 22 routes (including 15 new `[TBD]` routes), ~15 new ESI collectors in `analysis/character/`, and a WebSocket feed for live character events.

This is the largest single phase. It is subdivided into four sub-phases that can be committed independently.

---

## Target Route Table

| Method | Route | Auth | Source | Sub-phase |
|--------|-------|------|--------|-----------|
| GET | `/dashboard/` | `[role:dashboard]` | existing | **5a** — rebuild with aggregate stats |
| GET | `/dashboard/character/<id>` | `[role:dashboard]` | existing | **5a** — expand with more fields |
| GET | `/dashboard/character/<id>/skills` | `[role:dashboard]` | `[TBD]` | **5a** — data exists |
| GET | `/dashboard/character/<id>/wallet` | `[role:dashboard]` | `[TBD]` | **5a** — data exists |
| GET | `/dashboard/character/<id>/assets` | `[role:dashboard]` | `[TBD]` | **5a** — data exists |
| GET | `/dashboard/character/<id>/mail` | `[role:dashboard]` | `[TBD]` | **5b+5c** — new collector |
| GET | `/dashboard/character/<id>/contracts` | `[role:dashboard]` | `[TBD]` | **5b+5c** — new collector |
| GET | `/dashboard/character/<id>/calendar` | `[role:dashboard]` | `[TBD]` | **5b+5c** — new collector |
| GET | `/dashboard/character/<id>/contacts` | `[role:dashboard]` | `[TBD]` | **5b+5c** — new collector |
| GET | `/dashboard/character/<id>/notifications` | `[role:dashboard]` | `[TBD]` | **5b+5c** — new collector |
| GET | `/dashboard/character/<id>/industry` | `[role:dashboard]` | `[TBD]` | **5b+5c** — new collector |
| GET | `/dashboard/character/<id>/market` | `[role:dashboard]` | `[TBD]` | **5b+5c** — new collector |
| GET | `/dashboard/character/<id>/blueprints` | `[role:dashboard]` | `[TBD]` | **5b+5c** — new collector |
| GET | `/dashboard/character/<id>/pi` | `[role:dashboard]` | `[TBD]` | **5b+5c** — new collector |
| GET | `/dashboard/character/<id>/mining` | `[role:dashboard]` | `[TBD]` | **5b+5c** — new collector |
| GET | `/dashboard/character/<id>/loyalty` | `[role:dashboard]` | `[TBD]` | **5b+5c** — new collector |
| GET | `/dashboard/character/<id>/research` | `[role:dashboard]` | `[TBD]` | **5b+5c** — new collector |
| GET | `/dashboard/character/<id>/fittings` | `[role:dashboard]` | `[TBD]` | **5b+5c** — new collector |
| GET | `/dashboard/character/<id>/standings` | `[role:dashboard]` | `[TBD]` | **5b+5c** — new collector |
| GET | `/dashboard/character/<id>/killmails` | `[role:dashboard]` | `[TBD]` | **5b+5c** — new collector |
| WS | `/dashboard/ws` | `[role:dashboard]` | `[TBD]` | **5d** |

---

## Sub-phase 5a — Existing Data: Skills, Wallet, Assets

The current `analysis/character/populate.py` already fetches skills, wallet journal, wallet transactions, and assets into per-character SQLite. The dashboard currently shows a basic overview. This sub-phase adds dedicated sub-route views for these three data types.

### Dashboard Overview Rebuild (`GET /dashboard/`)

**Data sources:**
- All characters linked to `owner_id` (from private DB)
- For each character: name, portrait URL (from ESI image server), corp, alliance, total SP, active skill training, ISK balance
- Aggregate stats: total ISK across characters, total SP, active training count

**Template: `dashboard_index.html`**
- Character card grid: portrait, name, corp/alliance, ISK balance, current training skill + ETA
- Summary bar: total characters, total ISK, aggregate SP
- Each card links to `/dashboard/character/<id>`

### Character Sheet (`GET /dashboard/character/<id>`)

**Data sources:**
- Character row from private SQLite
- ESI public info: `GetCharactersCharacterId` → corp, alliance, security status, birthday
- ESI private info (scoped): clone, implants, fatigue, location

**Template: `dashboard_character.html`**
- Portrait + name + corp/alliance
- Stats: security status, total SP, birthday, last known location
- Active clone information
- Jump fatigue status
- Navigation sidebar: links to all sub-routes

### Skills View (`GET /dashboard/character/<id>/skills`)

**Data source:** `character_skills` table in private SQLite (populated by existing collector)

**Template: `dashboard_skills.html`**
- Skill queue at top: training skill name, level, ETA, progress bar
- Full skill tree grouped by category → group → skill
- Each skill: name, trained level (I–V), SP invested

### Wallet View (`GET /dashboard/character/<id>/wallet`)

**Data source:** `character_wallet` (journal + transactions) in private SQLite

**Template: `dashboard_wallet.html`**
- Balance card at top
- Tab toggle: Journal | Transactions
- Journal: date, type, amount, balance-after, description, parties
- Transactions: date, type, quantity, unit price, total, client, location

### Assets View (`GET /dashboard/character/<id>/assets`)

**Data source:** `character_assets` in private SQLite + SDE for type/group names

**Template: `dashboard_assets.html`**
- Grouped by location (station/structure name)
- Each item: type name (from SDE), quantity, estimated value (from market_price lookup)
- Location headers with total estimated ISK

### Ownership Check

All character sub-routes must verify `character_id` belongs to `session["owner_id"]`:

```python
@dashboard_bp.route("/character/<int:character_id>/skills")
@require_role("dashboard")
def skills(character_id):
    owner_id = session["owner_id"]
    char = char_data.get_character(owner_id, character_id)
    if not char:
        abort(404)
    # ... fetch skill data from private DB ...
```

---

## Sub-phase 5b — New Collectors

Each new dashboard sub-route requires a corresponding ESI collector. All new collectors follow the pattern from `analysis/character/populate.py` and write to the owner's private SQLite.

### Collector Inventory

| Collector | ESI Endpoint | Table | Scope | Priority |
|-----------|-------------|-------|-------|----------|
| Mail | `GetCharactersCharacterIdMail` | `character_mail` | `esi-mail.read_mail.v1` | Medium |
| Contracts | `GetCharactersCharacterIdContracts` | `character_contracts` | `esi-contracts.read_character_contracts.v1` | Medium |
| Calendar | `GetCharactersCharacterIdCalendar` | `character_calendar` | `esi-calendar.read_calendar_events.v1` | Low |
| Contacts | `GetCharactersCharacterIdContacts` | `character_contacts` | `esi-characters.read_contacts.v1` | Medium |
| Notifications | `GetCharactersCharacterIdNotifications` | `character_notifications` | `esi-characters.read_notifications.v1` | Medium |
| Industry | `GetCharactersCharacterIdIndustryJobs` | `character_industry` | `esi-industry.read_character_jobs.v1` | Medium |
| Personal Orders | `GetCharactersCharacterIdOrders` | `character_orders` | `esi-markets.read_character_orders.v1` | Medium |
| Blueprints | `GetCharactersCharacterIdBlueprints` | `character_blueprints` | `esi-characters.read_blueprints.v1` | Low |
| PI | `GetCharactersCharacterIdPlanets` | `character_planets` | `esi-planets.manage_planets.v1` | Low |
| Mining | `GetCharactersCharacterIdMining` | `character_mining` | `esi-industry.read_character_mining.v1` | Low |
| Loyalty | `GetCharactersCharacterIdLoyaltyPoints` | `character_loyalty` | `esi-characters.read_loyalty.v1` | Low |
| Research | `GetCharactersCharacterIdAgentsResearch` | `character_research` | `esi-characters.read_agents_research.v1` | Low |
| Fittings | `GetCharactersCharacterIdFittings` | `character_fittings` | `esi-fittings.read_fittings.v1` | Low |
| Standings | `GetCharactersCharacterIdStandings` | `character_standings` | `esi-characters.read_standings.v1` | Low |
| Killmails | `GetCharactersCharacterIdKillmailsRecent` | `character_killmails` | `esi-killmails.read_killmails.v1` | Low |

### Collector Pattern

Each collector is a function in `analysis/character/populate.py` (or in a new sub-module if the file gets too large). The pattern:

```python
def populate_mail(owner_id: int, character_id: int, access_token: str) -> None:
    """Fetch character mail headers and store in private SQLite."""
    session = get_private_session(owner_id)
    try:
        ensure_mail_table(session)
        resp = esi_get(
            f"https://esi.evetech.net/latest/characters/{character_id}/mail/",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if resp.status_code == 401:
            raise TokenExpiredError(character_id)
        if not resp.ok:
            return
        # ... insert into character_mail ...
    finally:
        session.close()
```

### ESI Scope Gathering

Before calling a collector, check whether the character's token has the required scope:

```python
scopes = char_data.get_scopes(owner_id, character_id)
if "esi-mail.read_mail.v1" in scopes:
    populate_mail(owner_id, character_id, access_token)
```

### Table DDL

Private SQLite tables use SQLAlchemy ORM or raw DDL — consistent with how `character_skills`, `character_wallet`, `character_assets` are created today.

### Scheduler Integration

Update `core/tasks/scheduler_jobs.py` to add a `character_full_refresh` job that calls `populate_all(owner_id)` for each registered owner. The `populate_all()` function should be extended to call all new collectors in addition to the existing three.

---

## Sub-phase 5c — Sub-Route Views & Templates

One new template per data type. Each follows the same pattern:

```python
# routes.py
@dashboard_bp.route("/character/<int:character_id>/mail")
@require_role("dashboard")
def mail(character_id):
    owner_id = session["owner_id"]
    char = char_data.get_character(owner_id, character_id)
    if not char:
        abort(404)
    mail_data = db.private_query(owner_id, "SELECT * FROM character_mail ORDER BY timestamp DESC LIMIT 50")
    return render_template("dashboard_mail.html",
                           **base_ctx("dashboard"),
                           character=char,
                           mail=mail_data)
```

### Template Inventory

| Template | Key Content |
|----------|------------|
| `dashboard_mail.html` | Inbox list: sender, subject, date. Click to expand body. |
| `dashboard_contracts.html` | Contract list: type, status, issuer, items, price. |
| `dashboard_calendar.html` | Calendar event list with response status. |
| `dashboard_contacts.html` | Contact list sorted by standing (colored bars). |
| `dashboard_notifications.html` | Notification feed with type-based icons/formatting. |
| `dashboard_industry.html` | Job list: activity, blueprint, status, start/end dates, output. |
| `dashboard_market.html` | Personal orders: type, price, volume, station, status (open/expired/fulfilled). |
| `dashboard_blueprints.html` | Blueprint library: name, type (BPO/BPC), ME, TE, runs, location. |
| `dashboard_pi.html` | Colony list per planet with extractor/factory status. |
| `dashboard_mining.html` | Mining ledger: date, ore type, quantity, estimated value. |
| `dashboard_loyalty.html` | LP balances by NPC corporation. |
| `dashboard_research.html` | Research agent slots: agent name, skill, points/day, total. |
| `dashboard_fittings.html` | Fitting list with EFT export button. |
| `dashboard_standings.html` | Standings by faction/corp/agent with colored bars. |
| `dashboard_killmails.html` | Kill/loss cards with ship type, system, date, value. |

### Character Sub-Navigation

Each character page includes a sidebar navigation with links to all sub-routes. Use a shared template fragment:

```html
{# _character_nav.html #}
<nav class="char-nav">
  <a href="{{ url_for('dashboard.character', character_id=character.id) }}" class="{{ 'active' if active_tab == 'overview' }}">Overview</a>
  <a href="{{ url_for('dashboard.skills', character_id=character.id) }}" class="{{ 'active' if active_tab == 'skills' }}">Skills</a>
  <a href="{{ url_for('dashboard.wallet', character_id=character.id) }}" class="{{ 'active' if active_tab == 'wallet' }}">Wallet</a>
  <!-- ... all sub-routes ... -->
</nav>
```

### SDE Enrichment

Many views need SDE lookups (type names, group names, system names). Use `sde.name_from_type_id()`, `sde.system_name_from_id()`, etc. from the `_api` adapter:

```python
from applications._api import sde

# In route handler or template context
type_name = sde.name_from_type_id(item["type_id"])
```

---

## Sub-phase 5d — WebSocket: Live Character Events

### Bus Topics

| Topic | Publisher | Access | Description |
|-------|----------|--------|-------------|
| `character/<owner_id>/training` | `analysis/character/populate.py` | `role:dashboard` + ownership | Skill training completion or queue change |
| `character/<owner_id>/wallet` | `analysis/character/populate.py` | `role:dashboard` + ownership | Wallet balance change notification |
| `character/<owner_id>/notifications` | `analysis/character/populate.py` | `role:dashboard` + ownership | New EVE notification count |

### WebSocket Route

```python
@sock.route("/dashboard/ws")
@require_role("dashboard")
def dashboard_ws(ws):
    owner_id = session["owner_id"]
    # Subscribe to all character topics for this owner
    topics = [
        f"character/{owner_id}/training",
        f"character/{owner_id}/wallet",
        f"character/{owner_id}/notifications",
    ]
    # ... bus subscription + forward to ws ...
```

### Client-Side

```javascript
// dashboard.js
const bus = new BusClient([
    `character/${ownerId}/training`,
    `character/${ownerId}/wallet`,
    `character/${ownerId}/notifications`,
]);

bus.onMessage((msg) => {
    if (msg.topic.endsWith("/training")) {
        updateSkillTrainingCard(msg.data);
    } else if (msg.topic.endsWith("/wallet")) {
        updateWalletBalance(msg.data);
    } else if (msg.topic.endsWith("/notifications")) {
        incrementNotificationBadge(msg.data.count);
    }
});
```

---

## Impact on `analysis/character/`

### Current Structure

```
analysis/character/
  __init__.py       # re-exports: populate_all
  populate.py       # populate_skills, populate_wallet, populate_assets, populate_all
```

### Target Structure (after 5b)

```
analysis/character/
  __init__.py       # re-exports: populate_all, populate_mail, populate_contracts, ...
  populate.py       # Core: populate_skills, populate_wallet, populate_assets
  collectors.py     # New: populate_mail, populate_contracts, populate_calendar, ...
  __all_collectors.py  # Optional: registry of all collectors with scope → function mapping
```

Or, if keeping a single file is cleaner:

```
analysis/character/
  __init__.py       # re-exports: populate_all
  populate.py       # All 18 collectors + populate_all orchestrator
```

The `populate_all(owner_id)` function should iterate over all collectors, checking scopes before calling each one:

```python
def populate_all(owner_id: int) -> None:
    """Refresh all character data for an owner."""
    for char_id, token_data in get_all_character_tokens(owner_id):
        _, fresh = fresh_token(owner_id, char_id, token_data)
        access_token = fresh["access_token"]
        scopes = get_scopes(owner_id, char_id)

        # Always-available (no scope needed)
        populate_public_info(owner_id, char_id)

        # Scope-gated collectors
        COLLECTORS = [
            ("esi-skills.read_skills.v1", populate_skills),
            ("esi-wallet.read_character_wallet.v1", populate_wallet),
            ("esi-assets.read_assets.v1", populate_assets),
            ("esi-mail.read_mail.v1", populate_mail),
            ("esi-contracts.read_character_contracts.v1", populate_contracts),
            # ... all 15 collectors ...
        ]
        for scope, fn in COLLECTORS:
            if scope in scopes:
                try:
                    fn(owner_id, char_id, access_token)
                except TokenExpiredError:
                    logger.warning("Token expired for %s, stopping", char_id)
                    break
```

---

## Verification Checklist

### 5a — Existing Data
- [ ] `GET /dashboard/` shows character card grid with aggregate stats
- [ ] `GET /dashboard/character/<id>` shows full character sheet
- [ ] `GET /dashboard/character/<id>/skills` shows skill queue + skill tree
- [ ] `GET /dashboard/character/<id>/wallet` shows balance + journal + transactions
- [ ] `GET /dashboard/character/<id>/assets` shows assets grouped by location with values
- [ ] Ownership check prevents viewing other users' characters

### 5b — New Collectors
- [ ] Each new collector writes to its private SQLite table
- [ ] Scope checking prevents calling collectors without the required ESI scope
- [ ] `populate_all()` calls all collectors
- [ ] Scheduler job `character_full_refresh` works end-to-end

### 5c — Sub-Route Views
- [ ] All 15 new sub-routes render correctly with real data
- [ ] Character sub-navigation highlights the active tab
- [ ] SDE lookups work for type names, system names, etc.
- [ ] Empty states handled gracefully (no data yet → "No data collected" message)

### 5d — WebSocket
- [ ] `WS /dashboard/ws` subscribes to character topics
- [ ] Skill training completion triggers live UI update
- [ ] Wallet balance change triggers live UI update
- [ ] New notifications increment badge

---

## File Operation Summary

| Operation | Count | Details |
|-----------|-------|---------|
| **Modified** | ~5 | dashboard routes.py, __init__.py, populate.py, scheduler_jobs.py |
| **Created** | ~20 | 15 new templates, 2-3 new JS files, collectors.py, template fragments |
| **Deleted** | 0 | |
