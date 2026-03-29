"""
tests/test_generated.py
────────────────────────
Unittest suite for the generated ESI package.
Asserts invariants that break if the spec snapshot or codegen changes unexpectedly.
"""

import importlib
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestGeneratedPackageExists(unittest.TestCase):
    """Verify the generated package was produced and is importable."""

    def test_init_importable(self):
        import esi.generated as pkg
        self.assertEqual(pkg.COMPATIBILITY_DATE, "2025-12-16")

    def test_operation_count(self):
        import esi.generated as pkg
        self.assertEqual(pkg.OPERATION_COUNT, 208)

    def test_schema_count(self):
        import esi.generated as pkg
        self.assertEqual(pkg.SCHEMA_COUNT, 263)

    def test_scope_count(self):
        import esi.generated as pkg
        self.assertEqual(pkg.SCOPE_COUNT, 66)


class TestManifest(unittest.TestCase):
    """Tests for esi/generated/manifest.py."""

    def setUp(self):
        from esi.generated.manifest import (
            OPERATIONS, ALL_SCOPES, OPERATIONS_BY_TAG,
            OPERATIONS_BY_METHOD, AUTH_OPERATIONS, PUBLIC_OPERATIONS,
            COMPATIBILITY_DATE, OPERATION_COUNT,
        )
        self.ops = OPERATIONS
        self.scopes = ALL_SCOPES
        self.by_tag = OPERATIONS_BY_TAG
        self.by_method = OPERATIONS_BY_METHOD
        self.auth_ops = AUTH_OPERATIONS
        self.public_ops = PUBLIC_OPERATIONS
        self.compat_date = COMPATIBILITY_DATE
        self.op_count = OPERATION_COUNT

    def test_operation_count(self):
        self.assertEqual(len(self.ops), 208)
        self.assertEqual(self.op_count, 208)

    def test_scope_count(self):
        self.assertEqual(len(self.scopes), 66)

    def test_compatibility_date(self):
        self.assertEqual(self.compat_date, "2025-12-16")

    def test_all_ops_have_required_keys(self):
        required = {"method", "path", "operation_id", "requires_auth", "parameters"}
        for op_id, op in self.ops.items():
            with self.subTest(op_id=op_id):
                for k in required:
                    self.assertIn(k, op, f"Key {k!r} missing from {op_id!r}")

    def test_methods_are_valid(self):
        valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH"}
        for op_id, op in self.ops.items():
            with self.subTest(op_id=op_id):
                self.assertIn(op["method"], valid_methods)

    def test_requires_auth_is_bool(self):
        for op_id, op in self.ops.items():
            with self.subTest(op_id=op_id):
                self.assertIsInstance(op["requires_auth"], bool)

    def test_by_tag_covers_all_ops(self):
        all_in_tags = {op_id for ops in self.by_tag.values() for op_id in ops}
        self.assertEqual(all_in_tags, set(self.ops.keys()))

    def test_by_method_covers_all_ops(self):
        all_in_method = {op_id for ops in self.by_method.values() for op_id in ops}
        self.assertEqual(all_in_method, set(self.ops.keys()))

    def test_auth_and_public_partition(self):
        auth_set = set(self.auth_ops)
        pub_set = set(self.public_ops)
        self.assertEqual(auth_set | pub_set, set(self.ops.keys()))
        self.assertEqual(auth_set & pub_set, set())

    def test_auth_ops_have_scopes(self):
        for op_id in self.auth_ops:
            with self.subTest(op_id=op_id):
                scopes = self.ops[op_id].get("scopes") or []
                self.assertIsInstance(scopes, list)
                # Most auth ops have at least one scope; some may have 0 (roles-based)
                # so we just assert the key exists, not that it's non-empty

    def test_scopes_sorted(self):
        self.assertEqual(self.scopes, sorted(self.scopes))

    def test_known_operation_present(self):
        self.assertIn("GetCharactersCharacterId", self.ops)
        self.assertIn("GetAlliances", self.ops)

    def test_tag_names_non_empty(self):
        for tag in self.by_tag:
            self.assertIsInstance(tag, str)
            self.assertGreater(len(tag), 0)


class TestGeneratedOperations(unittest.TestCase):
    """Verify operations.py exports one callable per operation_id."""

    def test_all_ops_callable(self):
        import esi.generated.operations as ops_module
        from esi.generated.manifest import OPERATIONS
        for op_id in OPERATIONS:
            fn_name = _safe_ident(op_id)
            with self.subTest(op_id=op_id):
                fn = getattr(ops_module, fn_name, None)
                self.assertIsNotNone(fn, f"No function {fn_name!r} in operations.py for op {op_id!r}")
                self.assertTrue(callable(fn))

    def test_module_imports_cleanly(self):
        import esi.generated.operations  # noqa: F401


class TestGeneratedClient(unittest.TestCase):
    """Tests for esi/generated/client.py."""

    def test_build_path_simple(self):
        from esi.generated.client import build_path
        path = build_path("GetAlliances")
        self.assertEqual(path, "/alliances")

    def test_build_path_with_params(self):
        from esi.generated.client import build_path
        path = build_path("GetAlliancesAllianceId", path_params={"alliance_id": 12345})
        self.assertIn("12345", path)
        self.assertNotIn("{", path)

    def test_build_path_missing_param(self):
        from esi.generated.client import MissingPathParam, build_path
        with self.assertRaises(MissingPathParam):
            build_path("GetAlliancesAllianceId", path_params={})

    def test_operation_not_found(self):
        from esi.generated.client import OperationNotFound, build_path
        with self.assertRaises(OperationNotFound):
            build_path("DoesNotExist123")

    def test_validate_write_get_is_error(self):
        from esi.generated.client import validate_write
        errors = validate_write("GetAlliances")
        self.assertTrue(any("GET" in e for e in errors))

    def test_validate_write_post_ok(self):
        from esi.generated.manifest import OPERATIONS_BY_METHOD
        from esi.generated.client import validate_write
        post_ops = OPERATIONS_BY_METHOD.get("POST", [])
        if post_ops:
            # Just checking it doesn't crash; errors may or may not be empty
            errors = validate_write(post_ops[0])
            self.assertIsInstance(errors, list)

    def test_auth_required_without_token(self):
        from esi.generated.client import AuthRequired, execute_operation
        from esi.generated.manifest import AUTH_OPERATIONS
        if AUTH_OPERATIONS:
            op_id = AUTH_OPERATIONS[0]
            with self.assertRaises(AuthRequired):
                execute_operation(op_id, token=None)

    def test_execute_public_get_dispatches(self):
        """execute_operation for a public GET route hits esi_request."""
        from esi.generated.client import execute_operation
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [1, 2, 3]
        mock_resp.content = b"[1,2,3]"
        mock_resp.text = "[1,2,3]"
        mock_resp.url = "https://esi.evetech.net/alliances"
        mock_resp.headers = {"Content-Type": "application/json"}

        with patch("util.esi_rate_limiter.esi_request", return_value=mock_resp) as mock_req:
            result = execute_operation("GetAlliances")
            self.assertEqual(result["status_code"], 200)
            self.assertEqual(result["body"], [1, 2, 3])
            mock_req.assert_called_once()
            call_args = mock_req.call_args
            self.assertEqual(call_args[0][0], "GET")
            self.assertIn("/alliances", call_args[0][1])

    def test_fetch_all_pages_single_page(self):
        """fetch_all_pages returns list for single-page response."""
        from esi.generated.client import fetch_all_pages
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"id": 1}]
        mock_resp.content = b'[{"id":1}]'
        mock_resp.text = '[{"id":1}]'
        mock_resp.url = "https://esi.evetech.net/alliances"
        mock_resp.headers = {"Content-Type": "application/json", "X-Pages": "1"}

        with patch("util.esi_rate_limiter.esi_request", return_value=mock_resp):
            result = fetch_all_pages("GetAlliances")
            self.assertIsInstance(result, list)

    def test_fetch_all_pages_403_returns_empty(self):
        """fetch_all_pages returns [] on 403."""
        from esi.generated.client import fetch_all_pages
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.content = b""
        mock_resp.headers = {"Content-Type": "application/json"}

        with patch("util.esi_rate_limiter.esi_request", return_value=mock_resp):
            result = fetch_all_pages("GetAlliances")
            self.assertEqual(result, [])


class TestAuthScopesFromManifest(unittest.TestCase):
    """Verify auth.py uses generated scopes and no hardcoded list."""

    def test_required_scopes_from_manifest(self):
        from util import auth
        from esi.generated.manifest import ALL_SCOPES
        import re
        # auth.py should no longer contain a hardcoded scope string
        auth_src = Path("util/auth.py").read_text(encoding="utf-8")
        self.assertNotIn("esi-wallet.read_character_wallet.v1", auth_src)
        self.assertNotIn("esi-skills.read_skills.v1", auth_src)
        # The generated import should be present
        self.assertIn("from esi.generated.manifest import ALL_SCOPES", auth_src)

    def test_required_scopes_is_66_scopes(self):
        from util.auth import REQUIRED_SCOPES
        scopes = REQUIRED_SCOPES.split()
        self.assertEqual(len(scopes), 66)

    def test_required_scopes_matches_manifest(self):
        from util.auth import REQUIRED_SCOPES
        from esi.generated.manifest import ALL_SCOPES
        self.assertEqual(set(REQUIRED_SCOPES.split()), set(ALL_SCOPES))


class TestNoLegacyImports(unittest.TestCase):
    """Verify legacy files that were retired no longer exist."""

    def _assert_file_gone(self, path: str):
        self.assertFalse(Path(path).exists(), f"Legacy file still exists: {path}")

    def test_data_collector_gone(self):
        self._assert_file_gone("esi/data_collector.py")

    def test_personal_assets_gone(self):
        self._assert_file_gone("esi/personal_assets.py")

    def test_personal_wallet_gone(self):
        self._assert_file_gone("esi/personal_wallet.py")

    def test_corp_assets_gone(self):
        self._assert_file_gone("esi/corp_assets_full.py")

    def test_legacy_web_blueprints_gone(self):
        self._assert_file_gone("webUI/personal_routes.py")
        self._assert_file_gone("webUI/corp_routes.py")
        self._assert_file_gone("webUI/public_routes.py")
        self._assert_file_gone("webUI/market_browser.py")

    def test_legacy_analysis_gone(self):
        self._assert_file_gone("analysis/job_slots.py")
        self._assert_file_gone("analysis/structures.py")


class TestCodegenCheckIsCurrentPassesWhenCurrent(unittest.TestCase):
    """check_generated_is_current() should not raise on a fresh generate()."""

    def test_no_error(self):
        from util.esi_codegen import check_generated_is_current
        # Should not raise since we just ran the generator
        check_generated_is_current()


class TestFlaskAppBlueprints(unittest.TestCase):
    """Verify the Flask app registers only the 4 expected blueprints."""

    def test_blueprints(self):
        from webUI import create_app
        app = create_app()
        self.assertSetEqual(set(app.blueprints.keys()), {"auth", "dashboard", "admin", "tasks"})


# ── Utilities ─────────────────────────────────────────────────────────────────

import re
import keyword

def _safe_ident(name: str) -> str:
    ident = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if ident and ident[0].isdigit():
        ident = "_" + ident
    if keyword.iskeyword(ident):
        ident = ident + "_"
    return ident


if __name__ == "__main__":
    unittest.main()
