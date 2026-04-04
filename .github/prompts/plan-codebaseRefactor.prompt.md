# Plan: Full Codebase Refactor & Dead Code Removal

Systematic cleanup across all layers — dead functions, copy-paste violations, config antipatterns, inline CSS extraction, hardcoded JS URLs, and inline event handlers. No behavioral changes in Phases 1–3; Phases 4–6 are pure frontend hygiene.

---

## Phase 1 — Dead Code Removal *(safe, ~30 min)*

1. **`core/db/publicDB.py`** — delete 4 functions with zero callers:
   - `reset_public_operational_tables()` — dev utility, never called
   - `retire_legacy_public_database()` — SQLite-era migration relic, never called
   - `upsert_public_contracts()` — infrastructure for a contracts collector that doesn't exist
   - `search_market_orders()` — incomplete feature, market_browser never imports it

2. **`core/db/privateDB.py`** — delete `get_public_session()` which does nothing but `raise RuntimeError`; the SQLite→DuckDB migration it guarded is long complete

3. **`core/queue/__init__.py`** — remove `writer_is_running` re-export; zero external imports

4. **`analysis/market/structures.py`** — remove dead `rate_limit_sleep: float = 10.0` parameter from `fetch_structure_orders()`; accepted, never read inside function body

5. **File header stale comments** — 7 files in `applications/` still say `# tools/` at the top instead of `# applications/`:
   - `applications/market_browser/routes.py`
   - `applications/market_browser/worker.py`
   - `applications/industry_calculator/routes.py`
   - `applications/industry_calculator/worker.py`
   - `applications/isk_per_hour/routes.py`
   - `applications/isk_per_hour/worker.py`
   - (verify any others)

---

## Phase 2 — Zombie Code & Config Antipatterns *(~1 hr)*

6. **`core/db/publicDB.py`** — remove `database_file` parameter from write-path functions only. These call `db_write_nowait()` / `db_executemany_nowait()` internally, making the parameter structurally impossible to honor. Read-path functions (`connect()`, `warehouse_exists()`, `ensure_public_database()`, `link_public_user()`, etc.) correctly use `database_file` via `connect(database_file or get_database_path())` and must keep it. Write-path targets:
   - `upsert_market_orders()`
   - `upsert_structures()`
   - `upsert_market_structures()`
   - `mark_region_market_refreshed()`
   - any others confirmed by grep (grep `database_file` across callers)

7. **`core/queue/scheduler.py`** — replace `_esi_log: list` with `collections.deque(maxlen=500)`; current code manually does `pop(0)` (O(n) shift) when capped

8. **`analysis/market/structures.py`** — 7 config helper functions each call `load_config()` independently on every invocation — reads config from disk 7× per structure processed. Load once at module level into a `_CFG` constant; replace all inner `cfg = load_config(CONFIG_PATH)` calls with references to `_CFG`.

9. **`analysis/structures/discover.py`** — same pattern, 3 separate `_cfg_*` functions each calling `load_config()` independently

10. **SimpleNamespace wrapper antipattern** — 3 files wrap already-imported functions in `SimpleNamespace` for no reason; call functions directly:
    - `analysis/market/structures.py` — `raw_esi = SimpleNamespace(get=_esi_get)` and `token_resolution = SimpleNamespace(...)`
    - `analysis/structures/discover.py` — `token_resolution = SimpleNamespace(...)`
    - `analysis/character/populate.py` — `token_resolution = SimpleNamespace(...)`

11. **`analysis/sde_loader.py`** — `_progress_print()` writes to `sys.stdout` directly, bypassing the logging system entirely (untestable, uncapturable by the task log handler). Replace with `logger.info()` / `logger.debug()`. Removes the `_LAST_PROGRESS_LENGTH = 0` global mutable state with it.

---

## Phase 3 — Shared Application Helpers (DRY) *(~30 min)*

12. **`_get_regions()` triplication** — identical function copy-pasted verbatim in 3 route files. Extract to `applications/_adapters.py` as a helper on the `db` namespace (or a standalone function). Update all 3 callers:
    - `applications/market_browser/routes.py` L25–29
    - `applications/industry_calculator/routes.py` L33–37
    - `applications/isk_per_hour/routes.py` L52–56

13. **`_DEFAULT_REGION = 10000002`** — duplicated constant in `industry_calculator/routes.py` (L15) and `isk_per_hour/routes.py` (L16). Centralize in `applications/_adapters.py` as `DEFAULT_REGION`.

14. **Late imports inside route handlers** — 4 route files import worker functions *inside* route functions, executing the import on every request. Move to module top-level:
    - `applications/market_browser/routes.py` L68: `from applications.market_browser.worker import refresh_region`
    - `applications/market_browser/routes.py` L87: `from analysis.market.regions import fetch_all_market_data`
    - `applications/industry_calculator/routes.py` L48: `from applications.industry_calculator.worker import calculate`
    - `applications/isk_per_hour/routes.py` L43: `from applications.isk_per_hour.worker import compute_rankings`

15. **`sde_store` alias** — `applications/market_browser/worker.py` imports `publicDB as sde_store`; misleading name (it is the full public warehouse, not SDE-specific). Rename to `public_db`.

---

## Phase 4 — CSS Extraction *(high effort, ~2 hrs)*

16. **`core/web/templates/base.html`** contains ~2300 lines of inline `<style>`. Extract entirely to `core/web/static/base.css`, update `base.html` to reference it via `<link rel="stylesheet" href="{{ url_for('static', filename='base.css') }}">`.

17. **Duplicate shared CSS classes** — `.console`, `.badge`, `.pill`, `.stat`, `.stat-row`, `.table-wrap` appear independently defined in multiple template `<style>` blocks. Consolidate into `core/web/static/components.css`, included by `base.html`. Per-app files keep only app-specific overrides.

18. **Per-app inline `<style>` blocks** — extract to one CSS file per app:
    - `core/web/templates/home.html` (~130 lines) → `core/web/static/home.css`
    - `core/web/templates/setup.html` (~250 lines) → `core/web/static/setup.css`
    - `applications/admin_panel/templates/admin.html` (~120 lines) → `applications/admin_panel/static/admin.css`
    - `applications/queue_viewer/templates/esi_queue_progress.html` (~180 lines) → `applications/queue_viewer/static/progress.css`
    - `applications/scheduler/templates/scheduler.html` (~50 lines) → `applications/scheduler/static/scheduler.css`
    - `applications/esi_browser/templates/admin_esi.html` (~35 lines) → `applications/esi_browser/static/admin_esi.css`

---

## Phase 5 — JS Hardcoded URLs → `data-*` Attributes *(~1.5 hrs)*

Every JS file hardcodes Flask route paths. Inject all endpoint URLs via `data-*` attributes on the app container using `url_for()` in the template, then read them in JS via `el.dataset.*`.

**Template pattern:**
```html
<div id="app"
     data-url-toggle="{{ url_for('scheduler.toggle_job', job_id='PLACEHOLDER') }}"
     data-url-run-now="{{ url_for('scheduler.run_now', job_id='PLACEHOLDER') }}">
</div>
```
**JS pattern:**
```js
const el = document.getElementById('app');
const toggleUrl = el.dataset.urlToggle.replace('PLACEHOLDER', jobId);
```

19. Add `data-url-*` attributes to each app's container element in the template.

20. Update hardcoded paths in JS files:
    - `scheduler.js` — `/admin/scheduler/{jobId}/toggle`, `/admin/scheduler/{jobId}/run-now`
    - `esi_queue_list.js` — `/queue/rate_stream`, `/queue/{taskId}/cancel`, `/queue/clear`
    - `esi_queue_progress.js` — `/queue/{taskId}/cancel`
    - `admin.js` — `/admin/stream`, `/admin/promote`, `/admin/demote`
    - `admin_esi.js` — `/admin/esi/{opId}`, `/admin/esi/{opId}/run`
    - `market_browser.js` — `/market/tree`, `/market/group/{gid}/types`, `/market/search`, `/market/orders`
    - `db_browser.js` — `/admin/db_browser/query`

---

## Phase 6 — Remove Inline Event Handlers *(~1 hr, depends on Phase 5)*

21. Remove all `onclick=`, `oninput=`, `onchange=` attributes from HTML. Register equivalent `addEventListener` calls in the corresponding external `.js` file, inside `DOMContentLoaded`. Affected templates:
    - `applications/esi_browser/templates/admin_esi.html` (5 handlers: `oninput`, 2× `onchange`, 2× `onclick`)
    - `applications/scheduler/templates/scheduler.html` (2 handlers: 2× `onclick`)
    - `applications/admin_panel/templates/admin.html` (3 handlers: `onclick`)
    - `applications/queue_viewer/templates/esi_queue_list.html` (2 handlers: `onclick`)
    - `applications/queue_viewer/templates/esi_queue_progress.html` (1 handler: `onclick`)
    - `applications/db_browser/templates/db_browser.html` (4 handlers: `onclick`)
    - `applications/market_browser/templates/market_browser.html` (1 handler: `onchange="...submit()"`)

---

## Phase 7 — Backwards Compatibility Shims & Layer Boundary Enforcement

This phase removes every backwards-compat shim still alive in the codebase and fixes the two confirmed import-layer violations. No new functionality is added.

### 7A — Remove Backwards Compatibility Shims

These exist because a previous state of the code needed them. That state no longer exists.

22. **`core/db/publicDB.py` — `database_file` on write-path functions only.**
    The write-path functions below call `db_write_nowait()` / `db_executemany_nowait()`, which are hardwired to the single DuckDB writer thread connection. The `database_file` parameter is accepted but structurally impossible to honor — passing it has no effect. Remove it from:
    - `upsert_market_orders()`
    - `upsert_structures()`
    - `upsert_market_structures()`
    - `mark_region_market_refreshed()`
    - any other write-path functions confirmed by grepping callers

    > **Do NOT remove** `database_file` from read-path functions (`connect()`, `warehouse_exists()`, `ensure_public_database()`, `link_public_user()`, `count_public_owners()`, `get_site_admin()`, etc.) — those functions correctly use the parameter via `connect(database_file or get_database_path())` and the override is legitimately useful for tests and CLI tooling.

23. **`core/db/privateDB.py` — `get_public_session()`** *(already in Phase 1 item 2, re-stated here for traceability).*
    Raises `RuntimeError("Public SQLite sessions have been retired...")` unconditionally. The SQLite→DuckDB migration is complete. Delete the function entirely.

24. **`analysis/market/structures.py` — `rate_limit_sleep` parameter** *(already in Phase 1 item 4, re-stated here for traceability).*
    Accepted by `fetch_structure_orders()` but never read inside the function body. The rate limiter in `esi_req.py` owns this responsibility. Remove the parameter and all call-sites that pass a value for it.

---

### 7B — Layer Boundary Violations

Per AGENTS.md the architectural contract is strict:

| Layer | May import from |
|-------|----------------|
| `core/` | other `core/` sub-modules only |
| `analysis/` | `core.*` only |
| `applications/` | `applications._base`, `applications._adapters` only; worker files may additionally import from `analysis.*` |

Two files currently violate this contract:

25. **`applications/queue_viewer/routes.py` — direct `core.*` imports in a routes file.**

    ```python
    # Lines 26–27 — VIOLATION
    from core.db.models import Character as _Character
    from core.db.privateDB import get_private_session as _gps
    ```

    These are used only inside `_make_char_name_lookup()` to resolve an `owner_id` → character name. The `char_data` adapter in `_adapters.py` already wraps private SQLite access (`get_character(owner_id, character_id)`) but does not expose a by-owner name lookup.

    **Fix (two parts):**
    - Add `get_characters(owner_id: int) -> list[dict]` method to the `_CharData` class in `applications/_adapters.py`. Internally it opens a private session, queries all `Character` rows for that owner, closes the session, and returns a list of `{character_id, name}` dicts.
    - Rewrite `_make_char_name_lookup()` in `queue_viewer/routes.py` to use `from applications._adapters import char_data` and call `char_data.get_characters(owner_id)` instead of opening sessions directly.

26. **`applications/market_browser/worker.py` — direct `core.*` imports in an application worker.**

    ```python
    # Lines 8–9 — VIOLATION
    from core.db import publicDB as sde_store
    from core.queue.esi_req import esi_get
    ```

    AGENTS.md restricts applications workers to `applications._base`, `applications._adapters`, and `analysis.*`. Both imports have correctly wrapped equivalents already present in `_adapters.py`:
    - `publicDB` → `db` adapter (`db.connect()`, `db.query()`, etc.)
    - `esi_get` → `raw_esi.get`

    **Fix:** Replace both imports with `from applications._adapters import db, raw_esi`. Update call-sites: `sde_store.connect()` → `db.connect()`, `esi_get(...)` → `raw_esi.get(...)`.

---

### 7C — Clarify Worker File Responsibility in Layer Contract

The AGENTS.md rule "Import ONLY from `applications._base` and `applications._adapters`" applies to the entire `applications/` layer. The one documented exception is that **worker files** within an application may additionally import from `analysis.*` — not from `core.*`.

This is documented in AGENTS.md but not enforced in any currently-named files. After fixing items 25 and 26, the rule is fully upheld. Any future application worker that needs a core capability should route it through `_adapters.py`, not import `core.*` directly.

**Rule summary (to be proposed as an addition to AGENTS.md):**

> `applications/*/worker.py`: may import from `applications._base`, `applications._adapters`, and `analysis.*`.  
> May NOT import from `core.*` directly.

---

## Verification Checklist

- [ ] **Phase 1:** Grep for each deleted function name — expect 0 remaining references
- [ ] **Phase 2:** `python -c "import analysis.market.structures"` — no import errors; confirm config loads once (add a `print` temporarily)
- [ ] **Phase 3:** Navigate to market browser, industry calc, ISK/hr — regions dropdown populated correctly
- [ ] **Phase 4:** Hard-reload each page — no unstyled elements, no 404s on `.css` files in Network tab
- [ ] **Phase 5:** Check Network tab on each page — all fetch/SSE requests resolve with 200
- [ ] **Phase 7:** `grep -r "from core\." applications/` returns only `_base.py` and `_adapters.py` — zero violations in routes or worker files; grep for each removed shim function name returns 0 hits

---

## Decisions & Scope

- `database_file` param: remove (zero callers use it; re-add via a proper DB-selection mechanism if multi-DB support is ever needed)
- `upsert_public_contracts` and `search_market_orders`: delete now; restore when a caller exists
- `get_public_session()` sentinel: delete entirely (migration is complete; the guard serves no purpose and misleads readers)
- Phases 1–3 are independent and can be executed in any order
- Phases 4–6 should be executed sequentially (CSS before URLs before event handlers)
- **Excluded from scope:**
  - `core/esi/generated/`, `core/esi/personal/`, `core/esi/corp/`, `core/esi/public/` — auto-generated, never hand-edit
  - `core/web/auth.py` token-in-session pattern — separate security review
  - `ToolManifest` nav configuration changes
  - Algorithmic or behavioral changes of any kind
