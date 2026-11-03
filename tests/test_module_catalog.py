import hashlib
import tempfile
import unittest
from pathlib import Path

from merlin.cpu_fabric.catalog import (
    BoundedModuleManager, CatalogError, ModuleManifest, verify_manifest,
)
from merlin.cpu_fabric.router import choose_modules


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.artifact = self.root / "specialist.bin"
        self.artifact.write_bytes(b"approved test artifact")
        self.digest = hashlib.sha256(self.artifact.read_bytes()).hexdigest()
        self.base = "a" * 64
        self.manifest = ModuleManifest(
            module_id="math-specialist", artifact_path="specialist.bin",
            artifact_sha256=self.digest, base_model_sha256=self.base,
            module_type="adapter", task_scope=("math",), precision="int8",
            estimated_bytes=60, min_ram_bytes=20, quality_eval_id="eval-1",
            verifier_id="verifier-1", rollback_ref="core-v1", approved=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_hash_and_base_compatibility(self):
        self.assertEqual(verify_manifest(self.manifest, self.root, self.base, 100), self.artifact)
        with self.assertRaises(CatalogError):
            verify_manifest(self.manifest, self.root, "b" * 64, 100)

    def test_transient_artifact_limit_is_independent_of_resident_budget(self):
        manager = BoundedModuleManager(
            self.root, self.base, 100, 100, max_artifact_bytes=8,
        )
        with self.assertRaises(CatalogError):
            manager.register(self.manifest)

    def test_activation_uses_verified_bounded_snapshot(self):
        seen = []
        manager = BoundedModuleManager(
            self.root, self.base, 100, 100, loader=lambda payload: seen.append(bytes(payload)) or "handle",
            max_artifact_bytes=100,
        )
        manager.register(self.manifest)
        self.assertEqual(manager.activate("math-specialist"), "handle")
        self.assertEqual(seen, [self.artifact.read_bytes()])

    def test_tampered_artifact_rejected(self):
        self.artifact.write_bytes(b"changed")
        with self.assertRaises(CatalogError):
            verify_manifest(self.manifest, self.root, self.base, 100)

    def test_path_escape_rejected(self):
        bad = ModuleManifest(**{**self.manifest.__dict__, "artifact_path": "../outside"})
        with self.assertRaises(CatalogError):
            verify_manifest(bad, self.root, self.base, 100)

    def test_lru_respects_pinned_core(self):
        core = ModuleManifest(**{**self.manifest.__dict__, "module_id": "core",
            "task_scope": ("general",), "estimated_bytes": 40, "pinned": True})
        manager = BoundedModuleManager(self.root, self.base, 100, 100)
        third = ModuleManifest(**{**self.manifest.__dict__, "module_id": "other-specialist"})
        manager.register(core)
        manager.register(self.manifest)
        manager.register(third)
        manager.activate("core")
        manager.activate("math-specialist")
        manager.activate("other-specialist")  # evicts least-recent unpinned module
        self.assertEqual(manager.resident_ids(), ("core", "other-specialist"))
        with self.assertRaises(CatalogError):
            manager.deactivate("core")

    def test_budget_and_unknown_module(self):
        manager = BoundedModuleManager(self.root, self.base, 50, 100)
        with self.assertRaises(CatalogError):
            manager.register(self.manifest)
        with self.assertRaises(CatalogError):
            manager.activate("missing")


    def test_loader_emits_measured_load_and_unload_events(self):
        events = []
        manager = BoundedModuleManager(
            self.root, self.base, 100, 100, event_sink=events.append,
            run_id="loader-test-run",
        )
        manager.register(self.manifest)
        manager.activate("math-specialist")
        manager.deactivate("math-specialist")
        self.assertEqual([event["operation"] for event in events], ["load", "unload"])
        self.assertTrue(all(event["source"] == "runtime" for event in events))
        self.assertTrue(all(event["run_id"] == "loader-test-run" for event in events))
        self.assertEqual(events[0]["artifact_bytes"], len(self.artifact.read_bytes()))
        self.assertEqual(events[0]["outcome"], "succeeded")
        self.assertEqual(events[1]["resident_module_bytes"], 0)
        self.assertGreaterEqual(events[0]["duration_ms"], 0)
        self.assertIn(events[0]["rss_measurement"],
                      ("linux_proc_statm_current_rss", "unavailable"))

    def test_failed_loader_emits_failure_without_residency(self):
        events = []
        def broken_loader(payload):
            raise RuntimeError("synthetic loader failure")
        manager = BoundedModuleManager(
            self.root, self.base, 100, 100, loader=broken_loader,
            event_sink=events.append,
        )
        manager.register(self.manifest)
        with self.assertRaises(RuntimeError):
            manager.activate("math-specialist")
        self.assertEqual(manager.resident_ids(), ())
        self.assertEqual(events[-1]["outcome"], "failed")
        self.assertEqual(events[-1]["error_type"], "RuntimeError")

    def test_telemetry_sink_failure_does_not_break_loader(self):
        def broken_sink(event):
            raise RuntimeError("telemetry unavailable")
        manager = BoundedModuleManager(
            self.root, self.base, 100, 100, event_sink=broken_sink,
        )
        manager.register(self.manifest)
        manager.activate("math-specialist")
        self.assertEqual(manager.resident_ids(), ("math-specialist",))

    def test_router_is_conservative(self):
        manager = BoundedModuleManager(self.root, self.base, 100, 100)
        manager.register(self.manifest)
        self.assertEqual(choose_modules("unknown", .99, manager.catalog, 100)["route"], "core_only")
        self.assertEqual(choose_modules("math", .99, manager.catalog, 100)["modules"], ["math-specialist"])
        self.assertEqual(choose_modules("math", .2, manager.catalog, 100)["route"], "core_only")


if __name__ == "__main__":
    unittest.main()
