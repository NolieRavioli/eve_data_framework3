"""Comprehensive DuckDB statistics and performance analysis.

Functions
---------
get_table_stats(db_path)     — per-table row counts and estimated sizes
get_write_rate_stats()       — writer stats extended with error_rate_pct
optimization_hints(db_path)  — fast, human-readable hints (no heavy DB queries)
table_optimization_hints(table_stats, db_bytes) — table-level hints (needs counts)
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Tables we always try to count (accurate SELECT COUNT(*)).
_KEY_TABLES: list[str] = [
    "market_orders",
    "market_structures",
    "market_region_cooldowns",
    "structures",
    "users",
    "site_admins",
    "user_roles",
    "scheduler_jobs",
    "character_skills",
    "character_wallet",
    "character_assets",
    "esi_routes",
    "esi_schemas",
    "esi_scopes",
    "dim_types",
    "dim_regions",
    "dim_systems",
    "dim_stations",
    "dim_groups",
    "dim_categories",
]


def get_table_stats(db_path: str | Path | None = None) -> list[dict]:
    """Return per-table stats from DuckDB.

    Queries ``duckdb_tables()`` for metadata, then overlays accurate
    ``COUNT(*)`` for key high-traffic tables.

    Each entry:
        table_name           — str
        rows                 — int | None  (None = table unknown/inaccessible)
        estimated_size_bytes — int | None  (from DuckDB internal stats)
        column_count         — int | None
    """
    from core.db.publicDB import connect, get_database_path

    target = Path(db_path) if db_path else get_database_path()
    if not target.exists():
        return []

    con = connect(target)
    try:
        # duckdb_tables() virtual table — DuckDB 0.9+
        try:
            raw = con.execute(
                "SELECT table_name, estimated_size, column_count "
                "FROM duckdb_tables() ORDER BY table_name"
            ).fetchall()
        except Exception:
            # Fallback: SHOW TABLES (no size/column metadata)
            try:
                names = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
                raw = [(n, None, None) for n in names]
            except Exception:
                raw = []

        stats: dict[str, dict] = {}
        for table_name, est_size, col_count in raw:
            stats[table_name] = {
                "table_name": table_name,
                "rows": None,
                "estimated_size_bytes": est_size,
                "column_count": col_count,
            }

        # Accurate COUNT(*) for known key tables.
        for tbl in _KEY_TABLES:
            try:
                row = con.execute(f'SELECT COUNT(*) FROM "{tbl}"').fetchone()
                if tbl not in stats:
                    stats[tbl] = {
                        "table_name": tbl,
                        "rows": int(row[0]),
                        "estimated_size_bytes": None,
                        "column_count": None,
                    }
                else:
                    stats[tbl]["rows"] = int(row[0])
            except Exception:
                pass  # table not yet created in this deployment

        return sorted(stats.values(), key=lambda r: r["table_name"])
    finally:
        con.close()


def get_write_rate_stats() -> dict:
    """Extend writer stats with derived ``error_rate_pct``.

    Returns the full ``get_writer_stats()`` dict plus:
        error_rate_pct — float: percentage of writes that failed
    """
    from core.db.writer import get_writer_stats

    stats = get_writer_stats()
    total = stats.get("writes_total", 0)
    errors = stats.get("writes_error", 0)
    stats["error_rate_pct"] = round((errors / total * 100), 2) if total else 0.0
    return stats


def optimization_hints(db_path: str | Path | None = None) -> list[dict]:
    """Return fast, human-readable optimisation hints.

    Uses only filesystem stats (cheap) and in-memory writer stats (zero I/O).
    Does **not** open a DuckDB connection — safe to call on every SSE tick.

    Each hint dict:
        severity       — "info" | "warn" | "critical"
        category       — "db_layout" | "performance" | "reliability"
        message        — short problem description
        recommendation — actionable suggestion
    """
    hints: list[dict] = []

    # ── DB file / WAL ──────────────────────────────────────────────────────────
    from core.db.reader import get_db_file_stats
    fs = get_db_file_stats(db_path)
    wal_bytes = fs.get("wal_size_bytes", 0)
    db_bytes = fs.get("file_size_bytes", 0)

    if wal_bytes > 100 * 1024 * 1024:  # 100 MB
        hints.append({
            "severity": "critical",
            "category": "performance",
            "message": f"WAL file is {wal_bytes / 1048576:.1f} MB — auto-checkpoint is overdue.",
            "recommendation": "Writer idle-checkpoint fires after 30 s. Continuous writes may prevent it; consider reducing burst size.",
        })
    elif wal_bytes > 50 * 1024 * 1024:  # 50 MB
        hints.append({
            "severity": "warn",
            "category": "performance",
            "message": f"WAL file is {wal_bytes / 1048576:.1f} MB.",
            "recommendation": "WAL will be flushed on next 30 s idle window. No action needed unless writes never pause.",
        })

    # ── Writer performance ─────────────────────────────────────────────────────
    from core.db.writer import get_writer_stats
    ws = get_writer_stats()
    p95 = ws.get("p95_ms")
    p99 = ws.get("p99_ms")
    errors = ws.get("writes_error", 0)
    queue_depth = ws.get("queue_depth", 0)

    if p99 is not None and p99 > 5000:
        hints.append({
            "severity": "critical",
            "category": "performance",
            "message": f"p99 write latency is {p99:.0f}ms — tail latency is extreme.",
            "recommendation": "A very large executemany() batch is blocking the writer queue. Split into chunks of ≤10 000 rows.",
        })
    elif p95 is not None and p95 > 2000:
        hints.append({
            "severity": "warn",
            "category": "performance",
            "message": f"p95 write latency is {p95:.0f}ms.",
            "recommendation": "Large market-order or SDE batches are slow. Use db_executemany() and batch ≤5 000 rows per call.",
        })
    elif p95 is not None and p95 > 500:
        hints.append({
            "severity": "info",
            "category": "performance",
            "message": f"p95 write latency is {p95:.0f}ms — within acceptable range but elevated.",
            "recommendation": "Normal during large market refreshes. Monitor p99 for spikes.",
        })

    if errors > 0:
        hints.append({
            "severity": "critical",
            "category": "reliability",
            "message": f"{errors} write error(s) recorded since startup.",
            "recommendation": "Check application logs for [writer] Write failed. Errors cause the writer connection to reset.",
        })

    if queue_depth > 100:
        hints.append({
            "severity": "warn",
            "category": "performance",
            "message": f"Writer queue depth is {queue_depth} — ops are backing up.",
            "recommendation": "Use db_executemany() for bulk inserts. Avoid enqueueing single rows in a loop.",
        })

    if db_bytes > 2 * 1024 ** 3:  # 2 GB
        hints.append({
            "severity": "info",
            "category": "db_layout",
            "message": f"Database is {db_bytes / 1024**3:.1f} GB. Market orders and SDE share one WAL.",
            "recommendation": "Consider separate sde.duckdb (read-only after pipeline) and market.duckdb to isolate WAL pressure.",
        })

    if not hints:
        hints.append({
            "severity": "info",
            "category": "performance",
            "message": "No issues detected.",
            "recommendation": "System is operating within normal parameters.",
        })

    return hints


def table_optimization_hints(
    table_stats: list[dict],
    db_bytes: int = 0,
) -> list[dict]:
    """Hints that require table-level row counts from ``get_table_stats()``.

    Call this separately from ``optimization_hints()`` since it needs a
    DB connection.  Append results to the fast hints for a complete picture.
    """
    hints: list[dict] = []
    tbl_map = {t["table_name"]: t for t in table_stats}

    mo = tbl_map.get("market_orders")
    if mo and mo.get("rows") is not None:
        if mo["rows"] > 1_000_000:
            hints.append({
                "severity": "warn",
                "category": "db_layout",
                "message": f"market_orders has {mo['rows']:,} rows co-located with identity tables in public.duckdb.",
                "recommendation": "A dedicated market.duckdb would eliminate WAL contention between market writes and auth/scheduler reads.",
            })
        elif mo["rows"] > 500_000:
            hints.append({
                "severity": "info",
                "category": "db_layout",
                "message": f"market_orders has {mo['rows']:,} rows.",
                "recommendation": "Growing toward the threshold where a dedicated market.duckdb becomes beneficial (>1M rows).",
            })

    dim_types = tbl_map.get("dim_types")
    if dim_types and dim_types.get("rows") is not None and dim_types["rows"] > 0 and db_bytes > 512 * 1024 ** 2:
        hints.append({
            "severity": "info",
            "category": "db_layout",
            "message": f"SDE dim_types ({dim_types['rows']:,} rows) is co-located with live write tables.",
            "recommendation": "SDE data is read-only after the pipeline runs. A separate sde.duckdb would reduce the main file's WAL size.",
        })

    esi = tbl_map.get("esi_routes")
    if esi and esi.get("rows") is not None and esi["rows"] > 0:
        # ESI registry is read-rarely — no action needed, but surface for awareness
        pass

    return hints
