# Phase 7 — `/market` + Analysis Architecture

> **Depends on:** Phase 1 (core refactor), Phase 2 (market_browser shell)
> **Blocks:** Nothing (final phase)
> **Scope:** `applications/market_browser/`, `analysis/market/`, `analysis/structures/`, `analysis/character/`

---

## Goal

1. Expand the market browser with a type detail page (price history chart + order book).
2. Enforce collector write discipline: **all** analysis collectors must go through centralized write paths — no raw `publicDB.connect()` or `session.execute()` bypasses.
3. Formalize the `analysis/` → `collectors/` (future) naming distinction documented in `website layout.md` Appendix.

---

## Part A — `/market` Route Expansion

### Target Route Table

| Method | Route | Auth | Source | Implementation |
|--------|-------|------|--------|---------------|
| GET | `/market/` | `[public]` | existing | **Keep** — hub/region selector |
| GET | `/market/orders` | `[public]` | existing | **Keep** — live order book |
| GET | `/market/search` | `[public]` | existing | **Keep** — type search + best prices |
| GET | `/market/type/<int:type_id>` | `[public]` | `[TBD]` | **New** — price history chart + full order book |
| GET | `/market/tree` | `[public]` | existing | **Keep** — category/group hierarchy |
| GET | `/market/group/<int:group_id>/types` | `[public]` | existing | **Keep** — types in group |

### Type Detail (`GET /market/type/<int:type_id>`)

**Data sources:**
- SDE: type name, group, category, description, icon_id (for EVE image server URL)
- `market_orders` (DuckDB): all current orders for this type across all regions
- Market history: ESI `GetMarketsRegionIdHistory` → daily OHLC + volume (if cached or fetched on demand)

**Template: `market_type.html`**

Layout:
```
┌──────────────────────────────────────────┐
│ [Type Icon]  Type Name                   │
│ Group > Category                         │
│ Base Price: 6.00 ISK                     │
├──────────────────────────────────────────┤
│ Price History Chart (30d/90d/1y toggle)  │
│ [Canvas chart: daily close + volume]     │
├──────────────┬───────────────────────────┤
│  Buy Orders  │  Sell Orders              │
│  price  vol  │  price  vol               │
│  ...         │  ...                      │
│  (sorted     │  (sorted                  │
│   desc)      │   asc)                    │
└──────────────┴───────────────────────────┘
```

**Route:**
```python
@market_bp.route("/type/<int:type_id>")
def type_detail(type_id):
    type_name = sde.name_from_type_id(type_id)
    if not type_name:
        abort(404)

    # Current orders from DuckDB
    con = db.connect()
    try:
        buy_orders = con.execute("""
            SELECT price, volume_remain, location_id, issued
            FROM market_orders
            WHERE type_id = ? AND is_buy_order = true
            ORDER BY price DESC
            LIMIT 200
        """, [type_id]).fetchall()

        sell_orders = con.execute("""
            SELECT price, volume_remain, location_id, issued
            FROM market_orders
            WHERE type_id = ? AND is_buy_order = false
            ORDER BY price ASC
            LIMIT 200
        """, [type_id]).fetchall()
    finally:
        con.close()

    return render_template("market_type.html",
                           **base_ctx("market_browser"),
                           type_id=type_id,
                           type_name=type_name,
                           buy_orders=buy_orders,
                           sell_orders=sell_orders)
```

### Price History Chart

**Option A — Server-rendered data, client-side chart:**
- Route returns historical price data as JSON via a `data-*` attribute or a separate AJAX endpoint
- Client uses Chart.js or a lightweight canvas lib to render OHLC + volume bars

**Option B — Fetch on demand:**
- `GET /market/type/<id>/history?region_id=10000002` returns cached history or fetches from ESI

**Recommendation:** Option B with caching. Market history doesn't change retroactively — cache aggressively.

```python
@market_bp.route("/type/<int:type_id>/history")
def type_history(type_id):
    region_id = request.args.get("region_id", 10000002, type=int)

    # Check DuckDB cache first
    con = db.connect()
    try:
        cached = con.execute("""
            SELECT date, lowest, highest, average, volume, order_count
            FROM market_history
            WHERE type_id = ? AND region_id = ?
            ORDER BY date DESC
            LIMIT 365
        """, [type_id, region_id]).fetchall()

        if cached:
            return jsonify([dict(zip(["date", "low", "high", "avg", "volume", "orders"], r)) for r in cached])
    finally:
        con.close()

    # Fallback: fetch from ESI
    resp = raw_esi.get(
        f"https://esi.evetech.net/latest/markets/{region_id}/history/",
        params={"type_id": type_id}
    )
    if not resp.ok:
        return jsonify([])
    return jsonify(resp.json())
```

### Market History Collector (New)

If price history is cached in DuckDB, a new collector is needed:

```python
# analysis/market/history.py (new)
def ensure_tables(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS market_history (
            type_id     INTEGER NOT NULL,
            region_id   INTEGER NOT NULL,
            date        DATE NOT NULL,
            lowest      DOUBLE,
            highest     DOUBLE,
            average     DOUBLE,
            volume      BIGINT,
            order_count INTEGER,
            PRIMARY KEY (type_id, region_id, date)
        )
    """)

def fetch_market_history(type_id: int, region_id: int) -> None:
    """Fetch and cache market history for a type in a region."""
    from core.queue.esi_req import esi_get
    from core.db import publicDB

    resp = esi_get(
        f"https://esi.evetech.net/latest/markets/{region_id}/history/",
        params={"type_id": type_id}
    )
    if not resp.ok:
        return

    con = publicDB.connect()
    try:
        ensure_tables(con)
        # ... write history rows ...
    finally:
        con.close()
```

**Note:** This collector still uses the old direct-connect pattern for DuckDB. It will be refactored as part of the write discipline enforcement (Part B below).

---

## Part B — Collector Write Discipline Enforcement

### The Problem

All analysis collectors currently bypass centralized write infrastructure:

| Collector | Violation | Current Code |
|-----------|-----------|-------------|
| `analysis/market/regions.py` | Direct `publicDB.connect()` + raw execute | `con.execute("INSERT OR REPLACE ...")` |
| `analysis/market/structures.py` | Direct `publicDB.connect()` + raw execute | `con.execute("INSERT OR REPLACE ...")` |
| `analysis/structures/discover.py` | Direct `publicDB.connect()` + raw execute | `con.execute(...)` |
| `analysis/character/populate.py` | Raw `session.execute()` + `session.commit()` | SQLAlchemy session bypass |

### The Goal

Every write to DuckDB must go through `core/db/writer.py` (`db_write`, `db_executemany`, `db_write_dataframe`). Every write to private SQLite must go through the private write queue in `core/db/private.py`.

### Migration Strategy

#### DuckDB Collectors

Replace direct `con.execute(...)` write patterns with writer calls:

**Before:**
```python
con = publicDB.connect()
try:
    ensure_tables(con)
    con.executemany("INSERT OR REPLACE INTO market_orders VALUES (...)", rows)
finally:
    con.close()
```

**After:**
```python
from core.db.writer import db_write, db_executemany, db_write_dataframe

# DDL still uses direct connect (DDL must be synchronous)
con = publicDB.connect()
try:
    ensure_tables(con)
finally:
    con.close()

# Data writes go through the writer
db_executemany("INSERT OR REPLACE INTO market_orders VALUES (...)", rows)
# Or for large DataFrames:
db_write_dataframe("market_orders", df)
```

**Key distinction:**
- DDL (`ensure_tables`) → direct connect is OK (idempotent, runs once at startup/before first write)
- Data writes → must go through writer

**Note:** Reads can still use direct `publicDB.connect()`. The writer serialization is only required for writes.

#### SQLite Character Collectors

Replace raw `session.execute()` + `session.commit()` with private write queue:

**Before:**
```python
session = get_private_session(owner_id)
try:
    session.execute(text("DELETE FROM character_skills WHERE character_id = :cid"), {"cid": character_id})
    for skill in skills:
        session.execute(text("INSERT INTO character_skills ..."), skill)
    session.commit()
finally:
    session.close()
```

**After:**
```python
from core.db.private import write_private, write_private_batch

write_private(owner_id, "DELETE FROM character_skills WHERE character_id = ?", [character_id])
write_private_batch(owner_id, "INSERT INTO character_skills VALUES (?, ?, ?, ?)", skill_rows)
```

The `write_private` / `write_private_batch` functions in `core/db/private.py` serialize writes per-owner, preventing concurrent SQLite access issues.

### Affected Files

| File | Changes Needed |
|------|---------------|
| `analysis/market/regions.py` | Replace `con.executemany(...)` writes with `db_executemany()` or `db_write_dataframe()` |
| `analysis/market/structures.py` | Replace `con.execute(...)` writes with `db_write()` / `db_executemany()` |
| `analysis/structures/discover.py` | Replace `con.execute(...)` writes with `db_write()` / `db_executemany()` |
| `analysis/character/populate.py` | Replace `session.execute()` + `session.commit()` with `write_private()` |

### Validation

After refactoring, grep the entire `analysis/` directory for violations:

```powershell
# Should return ZERO matches in data-write contexts (DDL ensure_tables is allowed)
Select-String -Path "analysis\**\*.py" -Pattern "con\.execute|con\.executemany|session\.execute|session\.commit" -Recurse
```

Manually verify each remaining match is DDL (CREATE TABLE, ALTER TABLE) and not a data write.

---

## Part C — Analysis Architecture Documentation

### Current vs. Future

As noted in `website layout.md` Part 4:

> The current `analysis/` folder name implies analysis but contains only collectors.

This phase documents the architectural distinction but does **not** rename `analysis/` to `collectors/`. That rename is reserved for when the first true analysis module is added.

### Document the Pattern

Add a comment block at the top of `analysis/__init__.py`:

```python
"""
analysis/ — Data Collection Layer
==================================

This package contains ESI data collectors that fetch raw data from EVE Online's
ESI API and write it to the framework's databases (DuckDB for public data,
SQLite for per-character private data).

Architecture:
    analysis/<domain>/
        __init__.py       — re-exports entry-point functions
        <module>.py       — ensure_tables(), data-fetch/write functions

Write Discipline:
    - DuckDB writes → core.db.writer (db_write, db_executemany, db_write_dataframe)
    - DuckDB DDL → direct publicDB.connect() (synchronous, idempotent)
    - DuckDB reads → direct publicDB.connect() (no serialization needed)
    - SQLite writes → core.db.private (write_private, write_private_batch)

Future:
    When true analysis modules are added (derived computation, not raw collection),
    this package may be renamed to collectors/ with analysis/ reserved for
    derived-data modules. See `website layout.md` Part 4 for the full rationale.
"""
```

---

## Dead Code Removal

### `core/queue/db.py` — Already Deleted in Phase 1

Verify that `write_private()` and `write_private_many()` (identified as dead code) were properly removed in Phase 1. If any references remain, clean them up now.

### Unused Imports

After all collector refactoring, scan for unused imports:

```powershell
# Quick check for unused publicDB imports in analysis/
Select-String -Path "analysis\**\*.py" -Pattern "from core\.db import publicDB|from core\.db\.publicDB import" -Recurse
```

Remove any imports that are no longer needed (e.g., if a collector now only uses writer functions).

---

## JavaScript for Market Type Detail

### `market_type.js`

```javascript
// Fetch and render price history chart
const typeId = document.getElementById("type-data").dataset.typeId;
const regionId = document.getElementById("type-data").dataset.regionId || "10000002";

fetch(`/market/type/${typeId}/history?region_id=${regionId}`)
    .then(r => r.json())
    .then(data => {
        renderPriceChart(data);  // Chart.js or similar
    });

function renderPriceChart(data) {
    const ctx = document.getElementById("price-chart").getContext("2d");
    // ... Chart.js OHLC + volume rendering ...
}

// Time range toggles
document.querySelectorAll("[data-range]").forEach(btn => {
    btn.addEventListener("click", () => {
        const days = parseInt(btn.dataset.range);
        // Filter chart data to last N days
        updateChartRange(days);
    });
});
```

---

## Templates

| Template | Purpose |
|----------|---------|
| `market_type.html` | Type detail: icon, name, price chart, buy/sell order book |

All other market templates already exist from the current `market_browser` package.

---

## Verification Checklist

### Market
- [ ] `GET /market/type/34` shows Tritanium with buy/sell order book
- [ ] Price history chart renders with 30d/90d/1y toggle
- [ ] Order book is sorted correctly (buy desc, sell asc)
- [ ] `GET /market/type/999999999` returns 404 for unknown types
- [ ] History endpoint returns cached data when available

### Write Discipline
- [ ] `analysis/market/regions.py` uses `db_write_dataframe()` for bulk market orders
- [ ] `analysis/market/structures.py` uses `db_executemany()` for structure orders
- [ ] `analysis/structures/discover.py` uses `db_write()` / `db_executemany()`
- [ ] `analysis/character/populate.py` uses `write_private()` / `write_private_batch()`
- [ ] Zero raw data-write `con.execute()` calls remain in `analysis/` (DDL excluded)
- [ ] All existing functionality still works after refactoring write paths

### Architecture
- [ ] `analysis/__init__.py` has architecture docstring
- [ ] Dead code from Phase 1 cleanup verified removed
- [ ] No unused imports remain in analysis/

---

## File Operation Summary

| Operation | Count | Details |
|-----------|-------|---------|
| **Created** | ~4 | market_type.html, market_type.js, market/history.py, analysis/__init__.py docstring |
| **Modified** | ~6 | market routes.py, regions.py, structures.py, discover.py, populate.py, analysis/__init__.py |
| **Deleted** | 0 | |

---

## Phase Completion Criteria

When this phase is done:
1. Every route in `website layout.md` has been implemented or has a clear `[TBD]` placeholder with collector scaffolding
2. No analysis collector writes data outside of centralized write paths
3. The market type detail page is functional with real data
4. The architecture documentation accurately reflects the current state
5. All 7 phases are complete and the codebase matches the target layout
