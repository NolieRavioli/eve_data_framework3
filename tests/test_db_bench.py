"""tests/test_db_bench.py
-----------------------
Realistic DuckDB (and SQLite) benchmark that mirrors the actual production
database interaction patterns used by this codebase.

Each test class maps directly to an analysis worker or core write path so the
timings reflect real serialisation overhead, writer-thread latency, and
DuckDB/SQLite commit cost — not synthetic microbenchmarks.

Power measurement
-----------------
Primary (Linux only):
    Intel RAPL via sysfs: /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj
    Reads the package-level µJ counter at the start and end of each test.
    Watts = Δµ​J / Δt.  Net energy above baseline is reported per-row.

Fallback (Windows / no RAPL access):
    psutil CPU% sampled every 500 ms in a background thread.
    Reports net CPU% above idle baseline and CPU-seconds as proxy metric.

Baseline:
    BENCH_BASELINE_S env var (default 60).  Set to 0 to skip baseline phase.

Patterns tested
---------------
TestMarketRegionRefresh   — public.replace_market_orders_for_region()
                            (blocking DELETE + vectorised pandas DataFrame INSERT)
TestStructureMarketOrders — public.upsert_market_orders()
                            (fire-and-forget db_executemany_nowait, INSERT ON CONFLICT)
TestWriterCoalescing      — 20× db_executemany_nowait same SQL vs single blocking
                            db_executemany — demonstrates writer coalesce gain
TestStructureDiscovery    — batch seed via db_executemany, then per-structure
                            single-row upsert loop (matches discover.py Phase 2)
TestCharacterData         — SQLAlchemy SQLite sa.text row-by-row loop + commit
                            (matches populate.py _fetch_skills/_fetch_assets)
TestDDLOps                — CREATE TABLE IF NOT EXISTS × N + ALTER TABLE ADD
                            COLUMN IF NOT EXISTS × N  (ensure_tables pattern)
TestMarketCooldowns       — db_write_nowait single-row INSERT ON CONFLICT × N
                            (matches public.mark_region_market_refreshed)

Setup
-----
setUpModule patches SDE_DATABASE_FILE to a temp DuckDB file and starts the
real core.db.writer thread so all write operations funnel through the actual
production serialisation path.  The temp DB is torn down in tearDownModule.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# PowerMonitor
# ---------------------------------------------------------------------------

class PowerMonitor:
    """Measure system power via Intel RAPL (Linux) or psutil CPU% (fallback).

    Instantiate once at module load.  Call measure_baseline() before any
    tests run, mark() around each test, and delta() to compute the result.
    """

    RAPL_PATH = Path("/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj")
    RAPL_MAX_PATH = Path("/sys/class/powercap/intel-rapl/intel-rapl:0/max_energy_range_uj")

    def __init__(self) -> None:
        self.mode = self._detect_mode()
        self._baseline_mean: float = 0.0
        self._baseline_stddev: float = 0.0
        self._psutil_samples: list[tuple[float, float]] = []  # (monotonic, cpu_pct)
        self._psutil_lock = threading.Lock()
        self._sampler_stop = threading.Event()
        if self.mode == "psutil":
            import psutil
            self._proc = psutil.Process(os.getpid())
            # warm up the first call (returns 0 otherwise)
            self._proc.cpu_percent(interval=None)
            self._sampler_thread = threading.Thread(
                target=self._psutil_sampler, daemon=True, name="power-sampler"
            )
            self._sampler_thread.start()

    def _detect_mode(self) -> str:
        if self.RAPL_PATH.exists():
            try:
                int(self.RAPL_PATH.read_text().strip())
                return "rapl"
            except Exception:
                pass
        try:
            import psutil  # noqa: F401
            return "psutil"
        except ImportError:
            return "none"

    def _read_rapl_uj(self) -> int:
        return int(self.RAPL_PATH.read_text().strip())

    def _rapl_max_uj(self) -> int:
        try:
            return int(self.RAPL_MAX_PATH.read_text().strip())
        except Exception:
            return 2 ** 32

    def _psutil_sampler(self) -> None:
        while not self._sampler_stop.wait(0.5):
            try:
                pct = self._proc.cpu_percent(interval=None)
                with self._psutil_lock:
                    self._psutil_samples.append((time.monotonic(), pct))
            except Exception:
                pass

    def measure_baseline(self, duration: float = 60.0) -> tuple[float, float]:
        """Sample idle power for *duration* seconds and store as baseline.

        Returns (mean, stddev) in Watts (RAPL) or CPU% (psutil).
        Immediately returns (0, 0) when duration <= 0 or mode is 'none'.
        """
        if duration <= 0 or self.mode == "none":
            return 0.0, 0.0
        unit = "W" if self.mode == "rapl" else "CPU%"
        print(
            f"\n  [PowerMonitor] Measuring {self.mode.upper()} baseline "
            f"for {duration:.0f}s …  (set BENCH_BASELINE_S=0 to skip)",
            flush=True,
        )
        if self.mode == "rapl":
            samples: list[float] = []
            tick = 2.0
            t_end = time.monotonic() + duration
            prev_uj = self._read_rapl_uj()
            prev_t = time.monotonic()
            while time.monotonic() < t_end:
                time.sleep(tick)
                cur_uj = self._read_rapl_uj()
                cur_t = time.monotonic()
                delta_uj = cur_uj - prev_uj
                if delta_uj < 0:
                    delta_uj += self._rapl_max_uj()
                dt = cur_t - prev_t
                if dt > 0:
                    samples.append(delta_uj / 1e6 / dt)
                prev_uj, prev_t = cur_uj, cur_t
        else:
            # Let the background sampler collect during the sleep
            with self._psutil_lock:
                start_idx = len(self._psutil_samples)
            time.sleep(duration)
            with self._psutil_lock:
                samples = [s[1] for s in self._psutil_samples[start_idx:]]
        if not samples:
            return 0.0, 0.0
        import statistics
        mean = statistics.mean(samples)
        stddev = statistics.stdev(samples) if len(samples) > 1 else 0.0
        self._baseline_mean = mean
        self._baseline_stddev = stddev
        print(
            f"  [PowerMonitor] Baseline: {mean:.2f} ± {stddev:.2f} {unit}",
            flush=True,
        )
        return mean, stddev

    def mark(self) -> dict:
        """Return a snapshot of the current power state."""
        snap: dict = {"wall": time.perf_counter(), "t": time.monotonic()}
        if self.mode == "rapl":
            snap["uj"] = self._read_rapl_uj()
        elif self.mode == "psutil":
            with self._psutil_lock:
                snap["sample_idx"] = len(self._psutil_samples)
        return snap

    def delta(self, start: dict, end: dict, n_rows: int) -> dict:
        """Compute metrics between two marks.

        Returns a dict with wall_s and mode-specific power fields.
        """
        wall_s = end["wall"] - start["wall"]
        result: dict = {"wall_s": wall_s, "mode": self.mode, "n_rows": n_rows}
        if self.mode == "rapl":
            delta_uj = end["uj"] - start["uj"]
            if delta_uj < 0:
                delta_uj += self._rapl_max_uj()
            total_j = delta_uj / 1e6
            baseline_j = self._baseline_mean * wall_s
            net_j = max(0.0, total_j - baseline_j)
            result["total_j"] = total_j
            result["net_j"] = net_j
            result["avg_w"] = total_j / wall_s if wall_s > 0 else 0.0
            result["net_w"] = net_j / wall_s if wall_s > 0 else 0.0
            result["j_per_row"] = net_j / n_rows if n_rows > 0 else 0.0
        elif self.mode == "psutil":
            with self._psutil_lock:
                samples = [
                    s[1] for s in self._psutil_samples[
                        start["sample_idx"]: end["sample_idx"]
                    ]
                ]
            mean_pct = sum(samples) / len(samples) if samples else 0.0
            net_pct = max(0.0, mean_pct - self._baseline_mean)
            result["avg_cpu_pct"] = mean_pct
            result["net_cpu_pct"] = net_pct
            result["cpu_seconds"] = net_pct / 100.0 * wall_s
        return result

    def shutdown(self) -> None:
        self._sampler_stop.set()


# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_BASELINE_S: float = float(os.environ.get("BENCH_BASELINE_S", "60"))
_power = PowerMonitor()

_tmp_dir: Optional[tempfile.TemporaryDirectory] = None
_db_path: Optional[Path] = None
_sqlite_path: Optional[Path] = None
_orig_env: dict = {}
_RESULTS: dict[str, dict] = {}  # test-class name → result dict


# ---------------------------------------------------------------------------
# Synthetic data builders
# ---------------------------------------------------------------------------

_ISSUED = "2024-01-01T00:00:00Z"
_REGION_A = 10_000_002  # The Forge
_REGION_B = 10_000_043  # Domain


def _market_order_rows(n: int, region_id: int = _REGION_A) -> list[dict]:
    """Build *n* synthetic ESI market-order dicts accepted by _market_order_payload."""
    return [
        {
            "order_id": region_id * 10_000_000 + i,
            "type_id": 34 + (i % 500),
            "location_id": 60_003_760,
            "region_id": region_id,
            "is_buy_order": i % 2 == 0,
            "issued": _ISSUED,
            "duration": 90,
            "price": 100.0 + i * 0.01,
            "order_range": "station",
            "volume_remain": 100 + i % 1000,
            "volume_total": 100 + i % 1000,
            "min_volume": 1,
            "last_seen": _ISSUED,
        }
        for i in range(n)
    ]


def _structure_bare_rows(n: int, id_offset: int = 1_000_000_000) -> list[dict]:
    """Build *n* bare structure seed rows (no metadata — Phase 1 pattern)."""
    return [{"structure_id": id_offset + i} for i in range(n)]


def _structure_enriched_rows(n: int, id_offset: int = 1_000_000_000) -> list[dict]:
    """Build *n* enriched structure rows (Phase 2 pattern)."""
    return [
        {
            "structure_id": id_offset + i,
            "solar_system_id": 30_000_142,
            "region_id": _REGION_A,
            "owner_id": 1_000_001,
            "name": f"Benchmark Structure {i}",
            "type_id": 35_832,
            "last_seen": datetime.now(timezone.utc),
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# Module setup / teardown
# ---------------------------------------------------------------------------

def setUpModule() -> None:  # noqa: N802 (unittest convention)
    global _tmp_dir, _db_path, _sqlite_path, _orig_env

    # Capture original env so tearDownModule can restore them
    _orig_env = {
        k: os.environ.get(k)
        for k in ("SDE_DATABASE_FILE", "PUBLIC_DATA_FOLDER", "EVE_PRIVATE_DATABASE_FOLDER")
    }

    # Create an isolated temp directory — nothing touches the production DB
    _tmp_dir = tempfile.TemporaryDirectory(prefix="bench_")
    tmp = Path(_tmp_dir.name)
    _db_path = tmp / "bench.duckdb"
    _sqlite_path = tmp / "bench_private.db"
    private_dir = tmp / "private"
    private_dir.mkdir()

    # Patch env BEFORE any core.* imports so every helper reads the temp path
    os.environ["SDE_DATABASE_FILE"] = str(_db_path)
    os.environ["PUBLIC_DATA_FOLDER"] = str(tmp)
    os.environ["EVE_PRIVATE_DATABASE_FOLDER"] = str(private_dir)

    # Deferred core imports (env must be set first)
    import core.config as _cfg
    try:
        _cfg.load_config()
    except Exception:
        pass  # config.yaml may not exist in CI; env vars are sufficient

    from core.db.writer import start_writer, db_write
    start_writer(db_path=_db_path)

    # Create production schemas in the temp DB
    import duckdb
    from collectors.market.regions import ensure_tables as _ensure_market
    from collectors.structures.discover import (
        ensure_tables as _ensure_structures,
        ensure_columns as _ensure_struct_cols,
    )
    con = duckdb.connect(str(_db_path))
    try:
        con.execute("PRAGMA threads=4")
        _ensure_market(con)
        _ensure_structures(con)
        _ensure_struct_cols(con)
        # Drain-sync table: a 1-row table used as a blocking sentinel to
        # ensure all preceding nowait ops have been committed before we
        # stop the timer.
        con.execute("CREATE TABLE IF NOT EXISTS _bench_sync (id INTEGER PRIMARY KEY)")
        # Coalesce bench table: no PK so DuckDB stays vectorised (no row-by-row
        # conflict resolution).  TRUNCATED between test_A and test_B.
        con.execute("CREATE TABLE IF NOT EXISTS _bench_coalesce (id BIGINT, val DOUBLE)")
    finally:
        con.close()

    # Baseline power measurement (skippable with BENCH_BASELINE_S=0)
    _power.measure_baseline(_BASELINE_S)


def tearDownModule() -> None:  # noqa: N802
    from core.db.writer import stop_writer
    stop_writer(timeout=30.0)

    _power.shutdown()
    _print_report()

    # Restore original environment
    for k, v in _orig_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

    if _tmp_dir is not None:
        try:
            _tmp_dir.cleanup()
        except Exception:
            pass


def _drain_writer() -> None:
    """Block until all preceding fire-and-forget writes have completed.

    Sends a blocking no-op write through the same writer queue so that by
    the time it returns, every earlier nowait op has been processed.
    """
    from core.db.writer import db_write
    db_write("INSERT OR REPLACE INTO _bench_sync VALUES (?)", [1])


def _record(name: str, metrics: dict) -> None:
    _RESULTS[name] = metrics


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _fmt_power(m: dict) -> str:
    """Format the power portion of a metrics dict into a short string."""
    mode = m.get("mode", "none")
    if mode == "rapl":
        return (
            f"avg {m['avg_w']:.1f}W  net {m['net_w']:.1f}W  "
            f"{m['j_per_row'] * 1e6:.2f} µJ/row"
        )
    if mode == "psutil":
        return (
            f"avg {m['avg_cpu_pct']:.1f}%  net {m['net_cpu_pct']:.1f}%  "
            f"{m['cpu_seconds']:.3f} CPU-s"
        )
    return "power: n/a"


def _print_report() -> None:
    if not _RESULTS:
        return

    sep = "─" * 100
    print(f"\n{sep}")
    print("  Production Pattern Benchmark — EVE Data Framework")
    print(f"  Power monitor mode: {_power.mode.upper()}")
    if _power._baseline_mean:
        unit = "W" if _power.mode == "rapl" else "CPU%"
        print(
            f"  Baseline: {_power._baseline_mean:.2f} ± "
            f"{_power._baseline_stddev:.2f} {unit}"
        )
    print(sep)
    print(
        f"  {'Test':<32} {'Rows':>8} {'Wall (s)':>10} {'ms/row':>10} "
        f"  Power"
    )
    print(sep)

    for name, m in _RESULTS.items():
        wall_s = m["wall_s"]
        n = m["n_rows"]
        ms_per_row = (wall_s / n * 1_000) if n else 0.0
        power_str = _fmt_power(m)
        print(
            f"  {name:<32} {n:>8,} {wall_s:>10.3f} {ms_per_row:>10.4f}  "
            f"{power_str}"
        )

    print(sep)
    print()


# ---------------------------------------------------------------------------
# Test 1 — Market region refresh
# (analysis/market/regions.py → public.replace_market_orders_for_region)
# Pattern: blocking DELETE then vectorised pandas DataFrame INSERT
# ---------------------------------------------------------------------------

N_MARKET_REGION_ROWS = 50_000


class TestMarketRegionRefresh(unittest.TestCase):
    """Time a full market-region replace: DELETE old rows + DataFrame INSERT.

    This is the hottest write path in the application — Jita alone is
    ~400k orders.  We test with 50k rows to keep the bench under a minute
    while remaining in the DuckDB vectorised regime.
    """

    @classmethod
    def setUpClass(cls) -> None:
        # Pre-build data outside the timed window
        cls.rows = _market_order_rows(N_MARKET_REGION_ROWS, region_id=_REGION_A)
        # Prime the table with stale data so the DELETE has real work to do
        from core.db.public import replace_market_orders_for_region
        replace_market_orders_for_region(_REGION_A, cls.rows)

    def test_region_market_replace(self) -> None:
        from core.db.public import replace_market_orders_for_region

        m0 = _power.mark()
        t0 = time.perf_counter()
        written = replace_market_orders_for_region(_REGION_A, self.rows)
        wall_s = time.perf_counter() - t0
        m1 = _power.mark()

        self.assertEqual(written, N_MARKET_REGION_ROWS)
        metrics = _power.delta(m0, m1, N_MARKET_REGION_ROWS)
        metrics["wall_s"] = wall_s
        _record("MarketRegionRefresh", metrics)


# ---------------------------------------------------------------------------
# Test 2 — Structure market orders
# (analysis/market/structures.py → public.upsert_market_orders)
# Pattern: fire-and-forget db_executemany_nowait, INSERT ON CONFLICT DO UPDATE
# ---------------------------------------------------------------------------

N_STRUCTURE_ORDERS = 1_000


class TestStructureMarketOrders(unittest.TestCase):
    """Time fire-and-forget upsert for structure market orders.

    upsert_market_orders() calls db_executemany_nowait — submissions are
    non-blocking.  We drain the writer queue with a blocking sentinel so
    the wall time reflects the full commit including writer overhead.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = _market_order_rows(N_STRUCTURE_ORDERS, region_id=_REGION_B)

    def test_structure_market_upsert(self) -> None:
        from core.db.public import upsert_market_orders

        m0 = _power.mark()
        t0 = time.perf_counter()
        upsert_market_orders(self.rows)
        _drain_writer()
        wall_s = time.perf_counter() - t0
        m1 = _power.mark()

        metrics = _power.delta(m0, m1, N_STRUCTURE_ORDERS)
        metrics["wall_s"] = wall_s
        _record("StructureMarketOrders", metrics)


# ---------------------------------------------------------------------------
# Test 3 — Writer coalescing
# (core/db/writer.py coalescing logic)
# Pattern A: single blocking db_executemany — one BEGIN/COMMIT round-trip
# Pattern B: N × db_executemany_nowait same SQL — writer batches into one txn
# ---------------------------------------------------------------------------

N_COALESCE_TOTAL = 20_000
N_COALESCE_CHUNKS = 20  # 1 000 rows per chunk


class TestWriterCoalescing(unittest.TestCase):
    """Compare coalesced nowait submits vs a single blocking executemany.

    The writer thread coalesces up to 50_000 rows from consecutive
    db_executemany_nowait() calls with identical SQL into one BEGIN/COMMIT
    cycle.  We use a simple no-PK table so DuckDB stays in its vectorised
    executor — this isolates writer-thread overhead from per-row SQL cost.

    Two sub-tests:
      A — single blocking db_executemany() — the minimum possible latency.
      B — N × db_executemany_nowait() + drain sentinel — coalesced path.
    In both cases the writer executes the same total number of rows; the
    difference in wall time reflects coalescing and queue-dispatch overhead.
    """

    # Simple 2-column INSERT on a no-PK table — stays vectorised in DuckDB.
    _SQL = "INSERT INTO _bench_coalesce VALUES (?, ?)"

    @classmethod
    def setUpClass(cls) -> None:
        chunk_size = N_COALESCE_TOTAL // N_COALESCE_CHUNKS
        cls.chunks: list[list[tuple]] = [
            [(c * chunk_size + i, float(c * chunk_size + i)) for i in range(chunk_size)]
            for c in range(N_COALESCE_CHUNKS)
        ]
        cls.all_rows: list[tuple] = [row for chunk in cls.chunks for row in chunk]

    def _reset_table(self) -> None:
        """TRUNCATE _bench_coalesce via the writer so each sub-test starts clean."""
        from core.db.writer import db_write
        db_write("TRUNCATE TABLE _bench_coalesce")

    def test_A_blocking_single(self) -> None:
        """Single blocking db_executemany() — one round-trip through the writer."""
        from core.db.writer import db_executemany
        self._reset_table()

        m0 = _power.mark()
        t0 = time.perf_counter()
        db_executemany(self._SQL, self.all_rows)
        wall_s = time.perf_counter() - t0
        m1 = _power.mark()

        metrics = _power.delta(m0, m1, N_COALESCE_TOTAL)
        metrics["wall_s"] = wall_s
        _record("Coalesce_Blocking", metrics)

    def test_B_coalesced_nowait(self) -> None:
        """N × db_executemany_nowait() with same SQL — writer coalesces into one txn."""
        from core.db.writer import db_executemany_nowait
        self._reset_table()

        m0 = _power.mark()
        t0 = time.perf_counter()
        for chunk in self.chunks:
            db_executemany_nowait(self._SQL, chunk)
        _drain_writer()
        wall_s = time.perf_counter() - t0
        m1 = _power.mark()

        metrics = _power.delta(m0, m1, N_COALESCE_TOTAL)
        metrics["wall_s"] = wall_s
        _record("Coalesce_Nowait", metrics)


# ---------------------------------------------------------------------------
# Test 4 — Structure discovery
# (analysis/structures/discover.py Phase 1 + Phase 2)
# Pattern: bulk seed via db_executemany then per-structure 1-row upsert loop
# ---------------------------------------------------------------------------

N_SEED_STRUCTURES = 500
N_ENRICH_STRUCTURES = 100


class TestStructureDiscovery(unittest.TestCase):
    """Time the two-phase structure discovery pattern.

    Phase 1 (seed): batch db_executemany inserts bare rows for new structure IDs.
    Phase 2 (enrich): per-structure single-row upsert with metadata, matching
    the discover.py loop that calls upsert_structures([row]) one at a time.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.bare_rows = _structure_bare_rows(N_SEED_STRUCTURES, id_offset=2_000_000_000)
        cls.enriched_rows = _structure_enriched_rows(N_ENRICH_STRUCTURES, id_offset=2_000_000_000)

    def test_A_phase1_seed(self) -> None:
        """Bulk seed: db_executemany INSERT OR REPLACE for N bare structure rows."""
        from core.db.public import upsert_structures

        m0 = _power.mark()
        t0 = time.perf_counter()
        upsert_structures(self.bare_rows)
        wall_s = time.perf_counter() - t0
        m1 = _power.mark()

        metrics = _power.delta(m0, m1, N_SEED_STRUCTURES)
        metrics["wall_s"] = wall_s
        _record("StrucDisc_Phase1_Seed", metrics)

    def test_B_phase2_enrich(self) -> None:
        """Enrich loop: one upsert_structures([row]) call per structure."""
        from core.db.public import upsert_structures

        m0 = _power.mark()
        t0 = time.perf_counter()
        for row in self.enriched_rows:
            upsert_structures([row])
        wall_s = time.perf_counter() - t0
        m1 = _power.mark()

        metrics = _power.delta(m0, m1, N_ENRICH_STRUCTURES)
        metrics["wall_s"] = wall_s
        _record("StrucDisc_Phase2_Enrich", metrics)


# ---------------------------------------------------------------------------
# Test 5 — Character data (SQLAlchemy SQLite)
# (analysis/character/populate.py _fetch_skills / _fetch_assets)
# Pattern: sa.text() row-by-row execute loop, single commit at end
# ---------------------------------------------------------------------------

N_SKILLS = 500
N_ASSETS = 2_000


class TestCharacterData(unittest.TestCase):
    """Time SQLite row-by-row writes via SQLAlchemy sa.text() loop.

    This matches populate.py exactly: no executemany, one sa.text() execute
    per skill/asset inside a with engine.connect() block, commit at end.
    """

    CHAR_ID = 999_000_001

    @classmethod
    def setUpClass(cls) -> None:
        import sqlalchemy as sa

        cls._engine = sa.create_engine(f"sqlite:///{_sqlite_path}")
        with cls._engine.connect() as con:
            con.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS character_skills (
                    character_id    INTEGER NOT NULL,
                    skill_id        INTEGER NOT NULL,
                    trained_level   INTEGER NOT NULL,
                    active_level    INTEGER NOT NULL,
                    skillpoints_in_skill INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (character_id, skill_id)
                )
            """))
            con.execute(sa.text("""
                CREATE TABLE IF NOT EXISTS character_assets (
                    item_id          INTEGER PRIMARY KEY,
                    character_id     INTEGER NOT NULL,
                    type_id          INTEGER NOT NULL,
                    location_id      INTEGER NOT NULL,
                    location_type    TEXT NOT NULL,
                    location_flag    TEXT NOT NULL,
                    quantity         INTEGER NOT NULL DEFAULT 1,
                    is_singleton     INTEGER NOT NULL DEFAULT 0,
                    is_blueprint_copy INTEGER
                )
            """))
            con.commit()

        cls.skills = [
            {
                "skill_id": 3300 + i,
                "trained_level": min(i % 5 + 1, 5),
                "active_level": min(i % 5 + 1, 5),
                "skillpoints_in_skill": i * 1000,
            }
            for i in range(N_SKILLS)
        ]
        cls.assets = [
            {
                "item_id": 400_000_000 + i,
                "type_id": 34 + i % 500,
                "location_id": 60_003_760,
                "location_type": "station",
                "location_flag": "Hangar",
                "quantity": 1 + i % 100,
            }
            for i in range(N_ASSETS)
        ]

    @classmethod
    def tearDownClass(cls) -> None:
        cls._engine.dispose()

    def test_A_skills_row_by_row(self) -> None:
        """Row-by-row skill upsert via sa.text() — mirrors _fetch_skills."""
        import sqlalchemy as sa

        char_id = self.CHAR_ID
        m0 = _power.mark()
        t0 = time.perf_counter()
        with self._engine.connect() as con:
            for skill in self.skills:
                con.execute(sa.text("""
                    INSERT INTO character_skills
                        (character_id, skill_id, trained_level, active_level,
                         skillpoints_in_skill)
                    VALUES
                        (:character_id, :skill_id, :trained_level, :active_level,
                         :skillpoints_in_skill)
                    ON CONFLICT (character_id, skill_id) DO UPDATE SET
                        trained_level        = excluded.trained_level,
                        active_level         = excluded.active_level,
                        skillpoints_in_skill = excluded.skillpoints_in_skill
                """), {
                    "character_id": char_id,
                    "skill_id": skill["skill_id"],
                    "trained_level": skill["trained_level"],
                    "active_level": skill["active_level"],
                    "skillpoints_in_skill": skill["skillpoints_in_skill"],
                })
            con.commit()
        wall_s = time.perf_counter() - t0
        m1 = _power.mark()

        metrics = _power.delta(m0, m1, N_SKILLS)
        metrics["wall_s"] = wall_s
        _record("CharData_Skills_SQLite", metrics)

    def test_B_assets_row_by_row(self) -> None:
        """Row-by-row asset upsert via sa.text() — mirrors _fetch_assets."""
        import sqlalchemy as sa

        char_id = self.CHAR_ID
        m0 = _power.mark()
        t0 = time.perf_counter()
        with self._engine.connect() as con:
            for asset in self.assets:
                con.execute(sa.text("""
                    INSERT INTO character_assets
                        (item_id, character_id, type_id, location_id,
                         location_type, location_flag, quantity, is_singleton)
                    VALUES
                        (:item_id, :character_id, :type_id, :location_id,
                         :location_type, :location_flag, :quantity, 0)
                    ON CONFLICT (item_id) DO UPDATE SET
                        location_id   = excluded.location_id,
                        location_flag = excluded.location_flag,
                        quantity      = excluded.quantity
                """), {
                    "item_id": asset["item_id"],
                    "character_id": char_id,
                    "type_id": asset["type_id"],
                    "location_id": asset["location_id"],
                    "location_type": asset["location_type"],
                    "location_flag": asset["location_flag"],
                    "quantity": asset["quantity"],
                })
            con.commit()
        wall_s = time.perf_counter() - t0
        m1 = _power.mark()

        metrics = _power.delta(m0, m1, N_ASSETS)
        metrics["wall_s"] = wall_s
        _record("CharData_Assets_SQLite", metrics)


# ---------------------------------------------------------------------------
# Test 6 — DDL operations
# (ensure_tables / ensure_columns pattern used by every collector)
# Pattern: CREATE TABLE IF NOT EXISTS + ALTER TABLE ADD COLUMN IF NOT EXISTS
# ---------------------------------------------------------------------------

N_DDL_ITERATIONS = 50


class TestDDLOps(unittest.TestCase):
    """Time CREATE TABLE IF NOT EXISTS and ALTER TABLE ADD COLUMN IF NOT EXISTS.

    These DDL statements run at startup and before every collector write.
    Cost is expected to be negligible on a warm DB but worth measuring since
    they run synchronously before any actual data work begins.
    """

    def test_A_create_table_if_not_exists(self) -> None:
        """N iterations of CREATE TABLE IF NOT EXISTS on an existing table."""
        import duckdb

        con = duckdb.connect(str(_db_path))
        try:
            con.execute("""
                CREATE TABLE IF NOT EXISTS _ddl_target (
                    id BIGINT PRIMARY KEY,
                    val DOUBLE
                )
            """)  # ensure it exists first
        finally:
            con.close()

        m0 = _power.mark()
        t0 = time.perf_counter()
        for _ in range(N_DDL_ITERATIONS):
            con = duckdb.connect(str(_db_path))
            try:
                con.execute("""
                    CREATE TABLE IF NOT EXISTS _ddl_target (
                        id BIGINT PRIMARY KEY,
                        val DOUBLE
                    )
                """)
            finally:
                con.close()
        wall_s = time.perf_counter() - t0
        m1 = _power.mark()

        metrics = _power.delta(m0, m1, N_DDL_ITERATIONS)
        metrics["wall_s"] = wall_s
        _record("DDL_CreateIfNotExists", metrics)

    def test_B_alter_table_add_column(self) -> None:
        """N iterations of ALTER TABLE ADD COLUMN IF NOT EXISTS."""
        import duckdb

        # Ensure the column exists for the first run (idempotent)
        con = duckdb.connect(str(_db_path))
        try:
            con.execute("ALTER TABLE _ddl_target ADD COLUMN IF NOT EXISTS extra VARCHAR")
        finally:
            con.close()

        m0 = _power.mark()
        t0 = time.perf_counter()
        for _ in range(N_DDL_ITERATIONS):
            con = duckdb.connect(str(_db_path))
            try:
                con.execute(
                    "ALTER TABLE _ddl_target ADD COLUMN IF NOT EXISTS extra VARCHAR"
                )
            finally:
                con.close()
        wall_s = time.perf_counter() - t0
        m1 = _power.mark()

        metrics = _power.delta(m0, m1, N_DDL_ITERATIONS)
        metrics["wall_s"] = wall_s
        _record("DDL_AlterAddColumn", metrics)


# ---------------------------------------------------------------------------
# Test 7 — Market region cooldowns
# (public.mark_region_market_refreshed)
# Pattern: fire-and-forget db_write_nowait single-row INSERT ON CONFLICT
# ---------------------------------------------------------------------------

N_COOLDOWNS = 200


class TestMarketCooldowns(unittest.TestCase):
    """Time per-region cooldown upserts — one db_write_nowait per region.

    mark_region_market_refreshed() fires a single-row INSERT OR REPLACE for
    each successfully refreshed region.  The writes are fire-and-forget; total
    time is measured from first submit to drain sentinel completing.
    """

    @classmethod
    def setUpClass(cls) -> None:
        from datetime import timedelta

        cls.region_ids = list(range(10_000_000, 10_000_000 + N_COOLDOWNS))
        cls.refreshed_until = datetime.now(timezone.utc) + timedelta(hours=1)

    def test_cooldown_nowait_loop(self) -> None:
        from core.db.writer import db_write_nowait

        sql = "INSERT OR REPLACE INTO market_region_cooldowns VALUES (?, ?)"
        until = self.refreshed_until

        m0 = _power.mark()
        t0 = time.perf_counter()
        for region_id in self.region_ids:
            db_write_nowait(sql, [region_id, until])
        _drain_writer()
        wall_s = time.perf_counter() - t0
        m1 = _power.mark()

        metrics = _power.delta(m0, m1, N_COOLDOWNS)
        metrics["wall_s"] = wall_s
        _record("MarketCooldowns_Nowait", metrics)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2, buffer=False)
