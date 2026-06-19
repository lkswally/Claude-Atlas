#!/usr/bin/env python3
"""
F24 — Test Registry Validation
================================

Validates that config/test.registry.yaml is well-formed and that
tools/test_registry.py API works correctly.

Layers tested: unit (registry data model), integration (file system checks).
"""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.test_registry import TestRegistry, Suite, REGISTRY_PATH, QA_DIR


class TC01_RegistryLoads(unittest.TestCase):
    def setUp(self):
        self.reg = TestRegistry()

    def test_registry_loaded(self):
        self.assertTrue(self.reg.loaded, f"load_error: {self.reg.load_error}")

    def test_no_load_error(self):
        self.assertIsNone(self.reg.load_error)

    def test_registry_file_exists(self):
        self.assertTrue(REGISTRY_PATH.exists(), f"Missing: {REGISTRY_PATH}")


class TC02_RegistryCounts(unittest.TestCase):
    def setUp(self):
        self.reg = TestRegistry()
        self.summary = self.reg.summary()

    def test_total_at_least_63(self):
        self.assertGreaterEqual(self.summary["total"], 63)

    def test_active_count(self):
        # At least 31 active (F-series) plus this new suite
        self.assertGreaterEqual(self.summary["active"], 31)

    def test_legacy_count(self):
        self.assertGreaterEqual(self.summary["legacy"], 32)

    def test_quick_count_reasonable(self):
        # quick < full (some suites excluded from quick)
        self.assertLessEqual(self.summary["quick_count"], self.summary["full_count"])

    def test_release_count_gte_quick(self):
        # release >= quick (release runs more than quick)
        self.assertGreaterEqual(self.summary["release_count"], self.summary["quick_count"])


class TC03_SuiteDataModel(unittest.TestCase):
    def setUp(self):
        self.reg = TestRegistry()

    def test_all_active_have_id(self):
        for s in self.reg.suites_for_mode("full"):
            self.assertIsInstance(s.id, str)
            self.assertTrue(s.id.startswith("bloque-"), f"Bad id: {s.id}")

    def test_all_active_have_timeout(self):
        for s in self.reg.suites_for_mode("full"):
            self.assertGreater(s.timeout, 0, f"{s.id} has zero timeout")

    def test_valid_layers(self):
        valid = {"unit", "integration", "system", "evidence", "release", "legacy"}
        for s in self.reg.list_suites():
            self.assertIn(s.layer, valid, f"{s.id} has unknown layer: {s.layer}")

    def test_valid_statuses(self):
        valid = {"active", "skipped", "legacy"}
        for s in self.reg.list_suites():
            self.assertIn(s.status, valid, f"{s.id} has unknown status: {s.status}")

    def test_legacy_not_quick(self):
        for s in self.reg.list_suites():
            if s.status == "legacy":
                self.assertFalse(s.can_run_in_quick, f"Legacy suite in quick: {s.id}")

    def test_legacy_not_release(self):
        for s in self.reg.list_suites():
            if s.status == "legacy":
                self.assertFalse(s.can_run_in_release, f"Legacy suite in release: {s.id}")


class TC04_APIFunctions(unittest.TestCase):
    def setUp(self):
        self.reg = TestRegistry()

    def test_get_suite_known(self):
        suite = self.reg.get_suite("bloque-F10-sot-drift")
        self.assertIsNotNone(suite)
        self.assertEqual(suite.id, "bloque-F10-sot-drift")

    def test_get_suite_unknown_returns_none(self):
        self.assertIsNone(self.reg.get_suite("bloque-F99-nonexistent"))

    def test_suites_for_quick(self):
        quick = self.reg.suites_for_mode("quick")
        self.assertGreater(len(quick), 0)
        for s in quick:
            self.assertTrue(s.is_active())
            self.assertTrue(s.can_run_in_quick)

    def test_suites_for_release(self):
        release = self.reg.suites_for_mode("release")
        self.assertGreater(len(release), 0)
        for s in release:
            self.assertTrue(s.is_active())
            self.assertTrue(s.can_run_in_release)

    def test_suites_for_full(self):
        full = self.reg.suites_for_mode("full")
        quick = self.reg.suites_for_mode("quick")
        # full >= quick
        self.assertGreaterEqual(len(full), len(quick))

    def test_suites_by_layer_unit(self):
        unit = self.reg.suites_by_layer("unit")
        self.assertGreater(len(unit), 0)
        for s in unit:
            self.assertEqual(s.layer, "unit")

    def test_suites_by_layer_legacy(self):
        legacy = self.reg.suites_by_layer("legacy")
        self.assertGreaterEqual(len(legacy), 32)

    def test_suites_for_invalid_mode_empty(self):
        self.assertEqual(self.reg.suites_for_mode("nonexistent"), [])


class TC05_FileSystemIntegrity(unittest.TestCase):
    def setUp(self):
        self.reg = TestRegistry()

    def test_no_missing_active_suite_files(self):
        missing = self.reg.detect_missing_files()
        # Only this file itself may be absent if run before the suite is committed
        ids = [s.id for s in missing if s.id != "bloque-F24-test-registry"]
        self.assertEqual(ids, [], f"Active suites with missing files: {ids}")

    def test_orphaned_suites_none(self):
        # All bloque-*.py files on disk should be registered
        orphans = self.reg.detect_orphaned_suites()
        names = [p.name for p in orphans]
        self.assertEqual(names, [], f"Unregistered suites on disk: {names}")

    def test_f23_not_in_quick(self):
        s = self.reg.get_suite("bloque-F23-runtime-settings-separation")
        self.assertIsNotNone(s)
        self.assertFalse(s.can_run_in_quick, "F23 must not run in quick (race condition risk)")

    def test_f13_engram_active_not_in_quick(self):
        s = self.reg.get_suite("bloque-F13-engram-active")
        self.assertIsNotNone(s)
        self.assertFalse(s.can_run_in_quick, "engram-active requires live binary, must not be in quick")


class TC06_RunAllIntegration(unittest.TestCase):
    """Verify run_all.py uses the registry (module-level, no subprocess)."""

    def test_run_all_imports_registry(self):
        import importlib.util, types
        spec = importlib.util.spec_from_file_location(
            "run_all",
            str(PROJECT_ROOT / "tools" / "run_all.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(hasattr(mod, "_REGISTRY"), "run_all._REGISTRY not defined")

    def test_run_all_discover_uses_registry(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_all",
            str(PROJECT_ROOT / "tools" / "run_all.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        suites = mod.discover_suites()
        self.assertIsInstance(suites, list)
        self.assertGreater(len(suites), 0)
        # All returned paths should exist
        for p in suites:
            self.assertTrue(p.exists(), f"Discovered non-existent path: {p}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
