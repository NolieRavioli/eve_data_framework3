"""Integration tests for SDE warehouse population.

Builds a real DuckDB warehouse from the local ``_sde/`` YAML files and asserts
that all key tables are populated — including the blueprint tables that
exercise the most complex parts of the SDELoader.

These tests are skipped automatically when ``_sde/fsd/types.yaml`` is absent.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Make sure the project root is on the path when running from the tests/ dir.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SDE_ROOT = ROOT / "_sde"
_HAVE_SDE = (SDE_ROOT / "fsd" / "types.yaml").exists()
_SKIP_REASON = "SDE YAML files not present at _sde/"


@unittest.skipUnless(_HAVE_SDE, _SKIP_REASON)
class TestSDEWarehousePopulation(unittest.TestCase):
    """Build a full SDE warehouse into a temp file and assert row counts."""

    _db_file: str
    _tmp_dir: tempfile.TemporaryDirectory

    @classmethod
    def setUpClass(cls):
        # Patch config so SDELoader uses our temp dir rather than the live DB.
        import core.config as _config
        cls._orig_env = {k: os.environ.get(k) for k in ("PUBLIC_DATA_FOLDER",)}
        cls._tmp_dir = tempfile.TemporaryDirectory()
        os.environ["PUBLIC_DATA_FOLDER"] = cls._tmp_dir.name
        _config.load_config()   # re-read into os.environ

        cls._db_file = str(Path(cls._tmp_dir.name) / "test_sde.duckdb")

        from core.db.sde_loader import build_sde_warehouse
        build_sde_warehouse(
            database_file=cls._db_file,
            source_root=str(SDE_ROOT),
            supported_languages=["en"],
        )

    @classmethod
    def tearDownClass(cls):
        # Restore env
        for k, v in cls._orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        cls._tmp_dir.cleanup()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _count(self, table: str) -> int:
        import duckdb
        con = duckdb.connect(self._db_file, read_only=True)
        try:
            return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            con.close()

    def _query(self, sql: str, params=None):
        import duckdb
        con = duckdb.connect(self._db_file, read_only=True)
        try:
            if params:
                return con.execute(sql, params).fetchall()
            return con.execute(sql).fetchall()
        finally:
            con.close()

    # ------------------------------------------------------------------
    # Type / group / category dimensions
    # ------------------------------------------------------------------

    def test_sde_types_populated(self):
        count = self._count("sde_types")
        self.assertGreater(count, 30_000, f"sde_types has only {count} rows")

    def test_sde_groups_populated(self):
        count = self._count("sde_groups")
        self.assertGreater(count, 1_500, f"sde_groups has only {count} rows")

    def test_sde_categories_populated(self):
        count = self._count("sde_categories")
        self.assertGreater(count, 40, f"sde_categories has only {count} rows")

    def test_sde_marketGroups_populated(self):
        count = self._count("sde_marketGroups")
        self.assertGreater(count, 500, f"sde_marketGroups has only {count} rows")

    # ------------------------------------------------------------------
    # Blueprints — the most complex loader section
    # ------------------------------------------------------------------

    def test_sde_blueprints_populated(self):
        count = self._count("sde_blueprints")
        self.assertGreater(count, 5_000, f"sde_blueprints has only {count} rows")

    def test_sde_blueprintMaterials_populated(self):
        count = self._count("sde_blueprintMaterials")
        self.assertGreater(count, 30_000, f"sde_blueprintMaterials has only {count} rows")

    def test_sde_blueprintProducts_populated(self):
        count = self._count("sde_blueprintProducts")
        self.assertGreater(count, 5_000, f"sde_blueprintProducts has only {count} rows")

    def test_blueprints_have_manufacturing_activity(self):
        rows = self._query(
            "SELECT COUNT(*) FROM sde_blueprintMaterials WHERE activity = 'manufacturing'"
        )
        count = rows[0][0]
        self.assertGreater(count, 10_000,
            f"manufacturing materials: only {count} rows; blueprints.yaml may not have loaded correctly")

    def test_blueprints_have_research_activity(self):
        rows = self._query(
            "SELECT COUNT(*) FROM sde_blueprintMaterials WHERE activity IN ('research_time', 'research_material')"
        )
        count = rows[0][0]
        self.assertGreater(count, 0, "No research activity materials found")

    def test_specific_blueprint_tritanium(self):
        """Tritanium (type_id=34) should appear as a manufacturing material in many blueprints."""
        rows = self._query(
            "SELECT COUNT(*) FROM sde_blueprintMaterials WHERE material_type_id = 34 AND activity = 'manufacturing'"
        )
        count = rows[0][0]
        self.assertGreater(count, 500,
            f"Tritanium appears in only {count} manufacturing blueprints; seems wrong")

    # ------------------------------------------------------------------
    # Type materials & dogma
    # ------------------------------------------------------------------

    def test_sde_typeMaterials_populated(self):
        count = self._count("sde_typeMaterials")
        self.assertGreater(count, 5_000, f"sde_typeMaterials has only {count} rows")

    def test_sde_typeDogmaAttributes_populated(self):
        count = self._count("sde_typeDogmaAttributes")
        self.assertGreater(count, 100_000, f"sde_typeDogmaAttributes has only {count} rows")

    # ------------------------------------------------------------------
    # Universe
    # ------------------------------------------------------------------

    def test_sde_regions_populated(self):
        count = self._count("sde_regions")
        self.assertGreater(count, 100, f"sde_regions has only {count} rows")

    def test_sde_constellations_populated(self):
        count = self._count("sde_constellations")
        self.assertGreater(count, 1_000, f"sde_constellations has only {count} rows")

    def test_sde_systems_populated(self):
        count = self._count("sde_systems")
        self.assertGreater(count, 5_000, f"sde_systems has only {count} rows")

    # ------------------------------------------------------------------
    # Stations (bsd)
    # ------------------------------------------------------------------

    def test_sde_staStations_populated(self):
        count = self._count("sde_staStations")
        self.assertGreater(count, 500, f"sde_staStations has only {count} rows")

    # ------------------------------------------------------------------
    # Manifest integrity
    # ------------------------------------------------------------------

    def test_sde_manifest_populated(self):
        rows = self._query("SELECT fsd_file_count, bsd_file_count FROM sde_manifest")
        self.assertEqual(len(rows), 1, "sde_manifest should have exactly 1 row")
        fsd_count, bsd_count = rows[0]
        self.assertGreater(fsd_count, 10, f"Only {fsd_count} FSD files recorded")
        self.assertGreater(bsd_count, 0, f"No BSD files recorded")

    def test_dataset_manifest_covers_blueprints(self):
        rows = self._query(
            "SELECT table_name, row_count FROM sde_dataset_manifest WHERE table_name LIKE 'sde_blueprint%'"
        )
        tables = {r[0] for r in rows}
        self.assertIn("sde_blueprints", tables)
        self.assertIn("sde_blueprintMaterials", tables)
        self.assertIn("sde_blueprintProducts", tables)
        for table, count in rows:
            self.assertGreater(count, 0, f"{table} recorded 0 rows in dataset manifest")


@unittest.skipUnless(_HAVE_SDE, _SKIP_REASON)
class TestSDECacheFacade(unittest.TestCase):
    """Verify the in-memory SDE cache loads correctly from a pre-built warehouse."""

    # We rely on the live public.duckdb warehouse already built by the app.
    # These tests only run when the SDE YAML is present (implying the warehouse
    # was also built during setup). Skip gracefully if the DB doesn't exist yet.

    @classmethod
    def setUpClass(cls):
        from core.db.public import get_database_path
        cls._warehouse_exists = Path(get_database_path()).exists()

    def _skip_if_no_warehouse(self):
        if not self._warehouse_exists:
            self.skipTest("public.duckdb not yet built")

    def test_type_name_lookup(self):
        self._skip_if_no_warehouse()
        import core.db.sde as sde
        # Tritanium type_id = 34
        name = sde.name_from_type_id(34)
        self.assertEqual(name, "Tritanium", f"Expected 'Tritanium', got {name!r}")

    def test_unknown_type_returns_placeholder(self):
        self._skip_if_no_warehouse()
        import core.db.sde as sde
        result = sde.name_from_type_id(999_999_999)
        # The function never returns None; unknown IDs get a placeholder string.
        self.assertIn("Unknown", result)

    def test_region_from_system(self):
        self._skip_if_no_warehouse()
        import core.db.sde as sde
        # Jita is in The Forge (region 10000002), system 30000142
        region_id = sde.region_id_from_system_id(30000142)
        self.assertEqual(region_id, 10000002,
            f"Expected The Forge (10000002) for Jita, got {region_id}")

    def test_system_name_lookup(self):
        self._skip_if_no_warehouse()
        import core.db.sde as sde
        name = sde.system_name_from_id(30000142)
        self.assertEqual(name, "Jita", f"Expected 'Jita', got {name!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
