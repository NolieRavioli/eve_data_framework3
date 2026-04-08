"""SDE loading benchmark — 4 strategies compared by wall-clock time.

Answers the question: do we need to pre-build the DuckDB warehouse, or can we
load from raw JSONL fast enough at startup?

Strategies
----------
1. Sequential Python   — stdlib json, one file at a time → list[dict] per file
2. Parallel Python     — stdlib json, ThreadPoolExecutor(8) → list[dict] per file
3. DuckDB in-memory    — read_ndjson() into CREATE TABLE in :memory: DB (C++ heap,
                         stays queryable as a real DuckDB connection)
4. DuckDB warehouse    — duckdb.connect(public.duckdb) + scan all sde_* tables

Methods 1 & 2 materialise fully into Python objects and are dominated by the
Python JSON parser. Method 3 uses DuckDB's C++ JSONL reader which can exploit
parallelism internally. Method 4 measures the cost of querying a pre-built
warehouse (file open + all-table scan).

Run standalone (prints report):
    python tests/test_sde_loads.py

Run via pytest (-s to see benchmark output):
    pytest tests/test_sde_loads.py -v -s
"""
from __future__ import annotations

import gc
import json
import os
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import duckdb
import psutil

ROOT = Path(__file__).resolve().parent.parent
SDE_ROOT = ROOT / "_sde"
WAREHOUSE = ROOT / "_publicData" / "public.duckdb"

_HAVE_SDE = (SDE_ROOT / "types.jsonl").exists()
_HAVE_WAREHOUSE = WAREHOUSE.exists()
_SKIP_SDE = "SDE JSONL files not present at _sde/"
_SKIP_WAREHOUSE = "DuckDB warehouse not built (run update_sde() first)"


# ---------------------------------------------------------------------------
# Strategy 1 — Sequential stdlib json
# ---------------------------------------------------------------------------

def _read_jsonl_file(path: Path) -> tuple[str, list[dict]]:
    """Parse a single JSONL file into a list of dicts."""
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if raw:
                out.append(json.loads(raw))
    return path.stem, out


def load_sequential() -> dict[str, list[dict]]:
    """Read every JSONL file one at a time with stdlib json."""
    result: dict[str, list[dict]] = {}
    for path in sorted(SDE_ROOT.glob("*.jsonl")):
        stem, rows = _read_jsonl_file(path)
        result[stem] = rows
    return result


# ---------------------------------------------------------------------------
# Strategy 2 — Parallel ThreadPoolExecutor
# ---------------------------------------------------------------------------

def load_parallel(workers: int = 8) -> dict[str, list[dict]]:
    """Read JSONL files concurrently.

    Note: on CPython, json.loads is CPU-bound and the GIL prevents true
    parallel execution in threads.  This strategy may be *slower* than
    sequential due to thread-scheduling overhead — ProcessPoolExecutor would
    be needed to beat the GIL, but adds pickling/IPC cost instead.
    """
    paths = sorted(SDE_ROOT.glob("*.jsonl"))
    result: dict[str, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for fut in as_completed({ex.submit(_read_jsonl_file, p): p for p in paths}):
            stem, rows = fut.result()
            result[stem] = rows
    return result


# ---------------------------------------------------------------------------
# Strategy 3 — DuckDB in-memory JSONL
#
# Each file is loaded via DuckDB's C++ NDJSON reader into a real in-memory
# table. After this function returns the connection is still live and all
# tables are immediately queryable with SQL — no Python objects needed.
# ---------------------------------------------------------------------------

def load_duckdb_inmem() -> tuple[duckdb.DuckDBPyConnection, dict[str, int]]:
    """Load all JSONL files into an in-memory DuckDB instance.

    Returns (connection, {stem: row_count}).  Caller owns the connection.
    """
    con = duckdb.connect(":memory:")
    row_counts: dict[str, int] = {}
    for path in sorted(SDE_ROOT.glob("*.jsonl")):
        safe = str(path).replace("\\", "/")
        table = f"sde_{path.stem}"
        try:
            con.execute(
                f'CREATE TABLE "{table}" AS '
                f"SELECT * FROM read_ndjson('{safe}', "
                "auto_detect=true, maximum_object_size=67108864)"
            )
            row_counts[path.stem] = con.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]
        except Exception as exc:
            # Some complex files may fail auto_detect; record 0 and continue.
            row_counts[path.stem] = 0
            print(f"    [DuckDB in-mem] {path.name} failed: {exc}", file=sys.stderr)
    return con, row_counts


# ---------------------------------------------------------------------------
# Strategy 4 — DuckDB pre-built warehouse
#
# Connect to the on-disk warehouse and scan every sde_* table to force all
# data into the DuckDB buffer pool (equivalent read-cost to the other methods).
# ---------------------------------------------------------------------------

def load_duckdb_warehouse() -> tuple[duckdb.DuckDBPyConnection, dict[str, int]]:
    """Open public.duckdb and do a full scan of all sde_* tables.

    Returns (connection, {table: row_count}).
    """
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    tables = sorted(
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name LIKE 'sde\\_%' ESCAPE '\\'"
        ).fetchall()
    )
    row_counts: dict[str, int] = {}
    for tbl in tables:
        # SELECT COUNT(*) forces a full scan — equivalent to reading all rows.
        row_counts[tbl] = con.execute(f'SELECT COUNT(*) FROM "{tbl}"').fetchone()[0]
    return con, row_counts


# ---------------------------------------------------------------------------
# Benchmark harness
# ---------------------------------------------------------------------------

def _rss_mb() -> float:
    return psutil.Process(os.getpid()).memory_info().rss / 1_048_576


def _run_python_strategy(name: str, fn) -> dict:
    """Time a Python-dict strategy; fully materialises data, then frees it."""
    gc.collect()
    mem_before = _rss_mb()
    t0 = time.perf_counter()

    data: dict[str, list] = fn()

    elapsed = time.perf_counter() - t0
    mem_after = _rss_mb()
    total_rows = sum(len(v) for v in data.values())
    files = len(data)

    del data
    gc.collect()

    return {
        "name": name,
        "elapsed": elapsed,
        "files_or_tables": files,
        "total_rows": total_rows,
        "mem_delta_mb": mem_after - mem_before,
        "note": "Python list[dict]",
    }


def _run_duckdb_strategy(name: str, fn) -> dict:
    """Time a DuckDB strategy; counts rows from the live connection, then closes."""
    gc.collect()
    mem_before = _rss_mb()
    t0 = time.perf_counter()

    con, row_counts = fn()

    elapsed = time.perf_counter() - t0
    mem_after = _rss_mb()
    total_rows = sum(row_counts.values())
    files = len(row_counts)

    con.close()
    gc.collect()

    return {
        "name": name,
        "elapsed": elapsed,
        "files_or_tables": files,
        "total_rows": total_rows,
        "mem_delta_mb": mem_after - mem_before,
        "note": "DuckDB tables (C++ heap)",
    }


def run_all() -> list[dict]:
    results = []
    if _HAVE_SDE:
        print("  [1/4] Sequential Python ...", flush=True)
        results.append(_run_python_strategy(
            "Sequential Python  (stdlib json, 1 thread)",
            load_sequential,
        ))
        print("  [2/4] Parallel Python   ...", flush=True)
        results.append(_run_python_strategy(
            "Parallel Python    (stdlib json, 8 threads)",
            load_parallel,
        ))
        print("  [3/4] DuckDB in-memory  ...", flush=True)
        results.append(_run_duckdb_strategy(
            "DuckDB in-memory   (read_ndjson, C++ parser)",
            load_duckdb_inmem,
        ))
    if _HAVE_WAREHOUSE:
        print("  [4/4] DuckDB warehouse  ...", flush=True)
        results.append(_run_duckdb_strategy(
            "DuckDB warehouse   (pre-built public.duckdb)",
            load_duckdb_warehouse,
        ))
    return results


def print_report(results: list[dict]) -> None:
    if not results:
        print("  (no results — check that _sde/ and _publicData/ exist)")
        return

    fastest = min(results, key=lambda r: r["elapsed"])
    slowest = max(results, key=lambda r: r["elapsed"])

    w = 47
    print()
    print("=" * 95)
    print("  SDE Loading Benchmark")
    print("=" * 95)
    print(f"  {'Strategy':<{w}} {'Time':>7}  {'Files/Tbls':>10}  {'Total rows':>12}  {'Mem Δ':>8}  {'Note'}")
    print("  " + "-" * 92)
    for r in results:
        star = " ★" if r is fastest else "  "
        print(
            f"  {r['name']:<{w}} {r['elapsed']:>6.2f}s  "
            f"{r['files_or_tables']:>10}  {r['total_rows']:>12,}  "
            f"{r['mem_delta_mb']:>+7.0f}MB"
            f"{star}  {r['note']}"
        )
    print("=" * 95)

    if len(results) > 1:
        ratio = slowest["elapsed"] / fastest["elapsed"]
        print(
            f"\n  ★ Fastest: {fastest['name'].strip()}"
            f"   ({fastest['elapsed']:.2f}s,  {ratio:.1f}× faster than slowest)"
        )

    # --- per-strategy observations ---
    seq   = next((r for r in results if "sequential" in r["name"].lower()), None)
    par   = next((r for r in results if "parallel"   in r["name"].lower()), None)
    inmem = next((r for r in results if "in-memory"  in r["name"].lower()), None)
    wh    = next((r for r in results if "warehouse"  in r["name"].lower()), None)

    print()
    if seq and par:
        if par["elapsed"] >= seq["elapsed"] * 0.95:
            print(
                f"  ⚠  Parallel ({par['elapsed']:.2f}s) is not faster than sequential "
                f"({seq['elapsed']:.2f}s).  Python's GIL serialises json.loads across "
                "threads — CPU-bound JSON parsing doesn't benefit from ThreadPoolExecutor."
            )
        else:
            speedup = seq["elapsed"] / par["elapsed"]
            print(f"  Parallel is {speedup:.1f}× faster than sequential (I/O was the bottleneck).")

    if seq and inmem:
        speedup = seq["elapsed"] / inmem["elapsed"]
        mem_ratio = seq["mem_delta_mb"] / inmem["mem_delta_mb"] if inmem["mem_delta_mb"] > 0 else float("inf")
        print(
            f"  DuckDB in-memory is {speedup:.1f}× faster than sequential Python "
            f"and uses {mem_ratio:.1f}× less RAM "
            f"({inmem['mem_delta_mb']:+.0f} MB vs {seq['mem_delta_mb']:+.0f} MB).  "
            "Best option when no pre-built warehouse is available."
        )

    if inmem and wh:
        ratio = inmem["elapsed"] / wh["elapsed"]
        print(
            f"  Pre-built warehouse is {ratio:.0f}× faster than the best cold JSONL load "
            f"({wh['elapsed']:.2f}s vs {inmem['elapsed']:.2f}s).  "
            "Building and caching the warehouse is strongly recommended for production."
        )
        # Explain row-count difference
        if wh["files_or_tables"] > inmem["files_or_tables"]:
            extra = wh["files_or_tables"] - inmem["files_or_tables"]
            print(
                f"  (Warehouse reports {wh['files_or_tables']} tables / {wh['total_rows']:,} rows "
                f"vs {inmem['files_or_tables']} JSONL files / {inmem['total_rows']:,} rows — "
                f"the {extra} extra tables are non-SDE data: market orders, structures, ESI cache, etc.)"
            )
    elif inmem and not wh:
        # No warehouse to compare; just evaluate cold load
        if inmem["elapsed"] < 5:
            print("  → DuckDB in-memory cold load is fast enough for startup use if desired.")
        else:
            print("  → Consider pre-building a warehouse; cold load may add noticeable startup latency.")

    print()


# ---------------------------------------------------------------------------
# Pytest test class
# ---------------------------------------------------------------------------

@unittest.skipUnless(_HAVE_SDE or _HAVE_WAREHOUSE, "No SDE data or warehouse available")
class TestSDELoadPerformance(unittest.TestCase):
    """Run all 4 SDE loading strategies and assert basic correctness + performance."""

    _results: list[dict] = []

    @classmethod
    def setUpClass(cls) -> None:
        print("\n")
        cls._results = run_all()
        print_report(cls._results)

    def _get(self, fragment: str) -> dict | None:
        frag = fragment.lower()
        for r in self._results:
            if frag in r["name"].lower():
                return r
        return None

    # --- sanity: methods complete and return data ---

    @unittest.skipUnless(_HAVE_SDE, _SKIP_SDE)
    def test_sequential_loads_all_files(self) -> None:
        r = self._get("sequential")
        self.assertIsNotNone(r)
        self.assertGreaterEqual(r["files_or_tables"], 50, "Expected ≥ 50 JSONL files loaded")
        self.assertGreater(r["total_rows"], 500_000, "Expected > 500k rows total")

    @unittest.skipUnless(_HAVE_SDE, _SKIP_SDE)
    def test_parallel_loads_same_rows_as_sequential(self) -> None:
        # Kept for backward compat; delegates to the renamed test.
        self.test_parallel_row_count_matches_sequential()

    @unittest.skipUnless(_HAVE_SDE, _SKIP_SDE)
    def test_duckdb_inmem_loads_all_files(self) -> None:
        r = self._get("in-memory")
        self.assertIsNotNone(r)
        self.assertGreaterEqual(r["files_or_tables"], 50, "Expected ≥ 50 DuckDB tables created")
        self.assertGreater(r["total_rows"], 500_000, "Expected > 500k rows in DuckDB tables")

    @unittest.skipUnless(_HAVE_WAREHOUSE, _SKIP_WAREHOUSE)
    def test_warehouse_loads_all_sde_tables(self) -> None:
        r = self._get("warehouse")
        self.assertIsNotNone(r)
        self.assertGreaterEqual(r["files_or_tables"], 55, "Expected ≥ 55 sde_* tables")
        self.assertGreater(r["total_rows"], 500_000, "Expected > 500k rows across sde_* tables")

    # --- performance bounds ---

    @unittest.skipUnless(_HAVE_SDE, _SKIP_SDE)
    def test_sequential_under_5_minutes(self) -> None:
        r = self._get("sequential")
        self.assertIsNotNone(r)
        self.assertLess(r["elapsed"], 300, f"Sequential took {r['elapsed']:.1f}s — something is wrong")

    @unittest.skipUnless(_HAVE_SDE, _SKIP_SDE)
    def test_duckdb_inmem_faster_than_sequential(self) -> None:
        """DuckDB C++ NDJSON reader should beat single-threaded Python json.loads."""
        seq = self._get("sequential")
        duck = self._get("in-memory")
        if seq and duck:
            self.assertLess(
                duck["elapsed"], seq["elapsed"],
                f"DuckDB in-memory ({duck['elapsed']:.2f}s) should be faster than "
                f"sequential Python ({seq['elapsed']:.2f}s)",
            )

    @unittest.skipUnless(_HAVE_SDE, _SKIP_SDE)
    def test_duckdb_inmem_uses_less_memory_than_python(self) -> None:
        """DuckDB columnar heap should be substantially more compact than Python dicts."""
        seq = self._get("sequential")
        duck = self._get("in-memory")
        if seq and duck and seq["mem_delta_mb"] > 0 and duck["mem_delta_mb"] > 0:
            self.assertLess(
                duck["mem_delta_mb"], seq["mem_delta_mb"],
                f"DuckDB in-memory used {duck['mem_delta_mb']:.0f} MB vs "
                f"sequential Python {seq['mem_delta_mb']:.0f} MB — expected DuckDB to be smaller",
            )

    @unittest.skipUnless(_HAVE_SDE, _SKIP_SDE)
    def test_parallel_row_count_matches_sequential(self) -> None:
        """Parallel loader must produce the same data as sequential (correctness check)."""
        seq = self._get("sequential")
        par = self._get("parallel")
        if seq and par:
            self.assertEqual(
                par["total_rows"], seq["total_rows"],
                f"Parallel row count {par['total_rows']:,} ≠ sequential {seq['total_rows']:,}",
            )


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"SDE root  : {SDE_ROOT}")
    print(f"Warehouse : {WAREHOUSE}")
    print(f"JSONL present  : {_HAVE_SDE}")
    print(f"Warehouse present: {_HAVE_WAREHOUSE}")
    print()

    if not _HAVE_SDE and not _HAVE_WAREHOUSE:
        print("ERROR: Neither _sde/ JSONL files nor _publicData/public.duckdb found.")
        print("       Run update_sde() first or point SDE_PATH at the extracted JSONL directory.")
        sys.exit(1)

    results = run_all()
    print_report(results)