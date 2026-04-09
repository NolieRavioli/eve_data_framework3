# Analysis Workers

An **analysis worker** is a Python module that performs computation on data already stored in the DuckDB warehouse — transforming, aggregating, or enriching it — and writes the results back. Analysis workers sit between collectors (which fetch raw data from ESI) and applications (which display results to users).

---

## Table of Contents

1. [When to Write an Analysis Worker](#when-to-write-an-analysis-worker)
2. [Folder Structure](#folder-structure)
3. [Writing an Analysis Worker](#writing-an-analysis-worker)
4. [Reading from DuckDB](#reading-from-duckdb)
5. [Writing Results Back](#writing-results-back)
6. [Using SDE Data](#using-sde-data)
7. [Logging & Progress](#logging--progress)
8. [Running Analysis Workers](#running-analysis-workers)
9. [Scheduling Analysis Jobs](#scheduling-analysis-jobs)
10. [Rules](#rules)

---

## When to Write an Analysis Worker

Write an analysis worker when:
- You have raw collected data (market orders, character assets, etc.) and need to derive something from it (profit margins, arbitrage opportunities, build cost calculations)
- The computation is too slow to run inside a Flask route
- The result should persist between page loads (cached in DuckDB)
- You want to re-run or schedule the computation independently

**Spectrum:**

| Layer | Purpose | Example |
|-------|---------|---------|
| Collector | Fetch raw ESI data | Market order prices from ESI |
| **Analysis** | **Compute derived data** | **Profit margins, route efficiency** |
| Application | Display results in UI | Table of top arbitrage opportunities |

If the computation is fast (< 100ms) and doesn't need to be cached, you can run it directly in an application route without a separate worker.

---

## Folder Structure

```
analysis/
  my_domain/
    __init__.py      # Re-export entry point
    worker.py        # ensure_tables(), analysis functions
```

The `analysis/` folder is at the repository root, alongside `collectors/`. Analysis workers follow the same structural patterns as collectors.

---

## Writing an Analysis Worker

```python
# analysis/my_domain/worker.py
import logging
import core.db.public as db
from core.db.writer import db_write, db_executemany

logger = logging.getLogger(__name__)


def ensure_tables(con) -> None:
    """Idempotent DDL for this analysis domain's output tables."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS my_analysis_results (
            type_id       INTEGER NOT NULL,
            region_id     BIGINT  NOT NULL,
            margin        DOUBLE,
            spread        DOUBLE,
            computed_at   TIMESTAMP DEFAULT now(),
            PRIMARY KEY (type_id, region_id)
        )
    """)


def compute_margins(region_id: int = 10000002) -> None:
    """
    Compute buy/sell spread for all types in a region.
    Reads from market_orders, writes results to my_analysis_results.
    """
    logger.info("my_analysis: computing margins for region %d", region_id)

    con = db.connect()
    try:
        ensure_tables(con)

        rows = con.execute("""
            SELECT
                type_id,
                MIN(CASE WHEN NOT is_buy_order THEN price END) AS best_sell,
                MAX(CASE WHEN     is_buy_order THEN price END) AS best_buy
            FROM market_orders
            WHERE region_id = ?
            GROUP BY type_id
            HAVING best_sell IS NOT NULL AND best_buy IS NOT NULL
        """, [region_id]).fetchall()

        results = []
        for type_id, best_sell, best_buy in rows:
            if best_sell > 0:
                margin = (best_sell - best_buy) / best_sell
                spread = best_sell - best_buy
                results.append((type_id, region_id, margin, spread))

        logger.info("my_analysis: %d types processed", len(results))
    finally:
        con.close()

    db_executemany("""
        INSERT INTO my_analysis_results (type_id, region_id, margin, spread)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (type_id, region_id) DO UPDATE SET
            margin = excluded.margin,
            spread = excluded.spread,
            computed_at = now()
    """, results)

    logger.info("my_analysis: done, %d results written", len(results))
```

And the `__init__.py`:

```python
# analysis/my_domain/__init__.py
from analysis.my_domain.worker import compute_margins
```

---

## Reading from DuckDB

Analysis workers have direct access to all tables in the warehouse:

```python
import core.db.public as db

con = db.connect()
try:
    rows = con.execute("""
        SELECT type_id, price, volume_remain, is_buy_order
        FROM market_orders
        WHERE region_id = ?
        ORDER BY type_id, is_buy_order, price
    """, [region_id]).fetchall()
finally:
    con.close()
```

DuckDB connections are not thread-safe — always get a fresh one and close it after use.

### Available Source Tables

| Table | Contents |
|-------|---------|
| `market_orders` | Live orders: type_id, price, is_buy_order, region_id, location_id, volume_remain |
| `market_structures` | Player structure orders |
| `market_history` | Daily OHLC price history |
| `structures` | Known player structures with metadata |
| `sde_types` | Item types: type_id, name_en, group_id, market_group_id, volume, mass |
| `sde_groups` | Item groups: group_id, name_en, category_id |
| `sde_categories` | Item categories: category_id, name_en |
| `sde_marketGroups` | Market group hierarchy |
| `sde_mapRegions` | Regions: region_id, name_en, faction_id |
| `sde_mapSolarSystems` | Systems: system_id, name_en, security_status, region_id |
| `sde_npcStations` | NPC stations with solar_system_id |

DuckDB supports rich SQL — window functions, CTEs, ARRAY aggregations, and JSON functions are all available.

---

## Writing Results Back

Use the serialized writer for INSERT / UPDATE / DELETE to avoid DuckDB write contention:

```python
from core.db.writer import db_write, db_executemany

# Single row
db_write("""
    INSERT INTO my_analysis_results (type_id, region_id, margin)
    VALUES (?, ?, ?)
    ON CONFLICT (type_id, region_id) DO UPDATE SET margin = excluded.margin
""", [type_id, region_id, margin])

# Bulk insert
db_executemany("""
    INSERT INTO my_analysis_results VALUES (?, ?, ?, ?)
    ON CONFLICT DO UPDATE SET ...
""", list_of_tuples)
```

If your analysis function already holds a DuckDB connection that nothing else will be writing to at the same time, you can also write directly on that connection. Use the writer thread for any writes that might conflict with concurrent collector operations.

---

## Using SDE Data

For fast name/ID lookups, use the in-memory SDE cache from `core.db.sde`:

```python
import core.db.sde as sde

name = sde.name_from_type_id(34)                    # "Tritanium"
group_id = sde.group_id_from_type_id(34)             # 18
region_name = sde.region_name_from_id(10000002)      # "The Forge"
system_name = sde.system_name_from_id(30000142)      # "Jita"
security = sde.security_from_system_id(30000142)     # 0.9459...
```

The SDE cache is loaded at startup and is always available. It is read-only and thread-safe.

For bulk lookups across many IDs, it is more efficient to JOIN directly against the DuckDB SDE tables in your SQL query:

```python
rows = con.execute("""
    SELECT
        r.type_id,
        t.name_en,
        r.margin
    FROM my_analysis_results r
    JOIN sde_types t USING (type_id)
    WHERE r.region_id = ?
    ORDER BY r.margin DESC
    LIMIT 100
""", [region_id]).fetchall()
```

---

## Logging & Progress

Use Python's standard `logging` module. When running as a background task, all log output is captured and streamed live to the Task Manager UI.

```python
logger = logging.getLogger(__name__)

logger.info("Starting margin computation for %d types", len(type_ids))

for i, type_id in enumerate(type_ids):
    if i % 500 == 0:
        logger.info("Progress: %d / %d", i, len(type_ids))
    # ... compute ...

logger.info("Done — wrote %d results", len(results))
```

**Levels:**
- `DEBUG` — detailed internals, individual item processing
- `INFO` — progress milestones, row counts, important state changes
- `WARNING` — unexpected but recoverable conditions
- `ERROR` — failure that stops the current operation

Do not use `print()` in production code — it bypasses the log routing and won't appear in the task log stream.

---

## Running Analysis Workers

### Manual trigger from an application route

```python
from applications._api import tasks
from analysis.my_domain.worker import compute_margins

@my_bp.route("/compute", methods=["POST"])
@require_role("my_tool")
def trigger():
    task_id = tasks.enqueue("Compute Margins", compute_margins, 10000002, queue="public", owner_id=0)
    return redirect(url_for("task_viewer.task_log", task_id=task_id))
```

### Manual trigger from the Task Manager

If the analysis function is registered as a scheduled job, you can click **Run Now** in the scheduler UI at `/tasks/scheduler/`.

### Chaining after a collector

To run analysis automatically after a collection run, you can enqueue the analysis from within the collector:

```python
from core.tasks.queue import enqueue

def fetch_all_market_data() -> None:
    # ... fetch data ...

    # Trigger downstream analysis
    enqueue("Compute Margins", compute_margins, 10000002, queue="public", owner_id=0)
```

Note: `core.tasks.queue.enqueue` is the low-level function. In collectors, import from `core.tasks` directly. In applications, use `tasks.enqueue` from `applications._api`.

---

## Scheduling Analysis Jobs

To schedule an analysis worker the same way as a collector, add it to `core/tasks/jobs.py`:

```python
try:
    from analysis.my_domain.worker import compute_margins
    jobs.append({
        "job_id": "my_analysis_margins",
        "label": "Compute Market Margins",
        "fn": compute_margins,
        "fn_path": _path(compute_margins),
        "interval_s": 3600,    # run shortly after market collection
    })
except Exception:
    logger.warning("[SchedulerJobs] Could not import my_analysis — skipping job")
```

For analysis that should run after a specific collector, consider using a chained enqueue (described above) rather than a separate scheduled job. This ensures analysis always uses the latest collected data.

---

## Rules

- **Never import from `applications.*`** — analysis workers must not depend on the web layer.
- **Never make ESI calls in analysis workers** — that's a collector's job. Analysis reads from the warehouse only.
- **Always call `ensure_tables(con)` before any writes** — DDL is idempotent.
- **Use parameterized queries** — never interpolate values into SQL strings.
- **Use the writer thread for concurrent writes** — `db_write` / `db_executemany`.
- **Log progress with `logger.info`** — not `print()`.
