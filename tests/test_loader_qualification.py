import hashlib
import tempfile
import time
import unittest
from pathlib import Path

from merlin.cpu_fabric.catalog import BoundedModuleManager, ModuleManifest
from merlin.cpu_fabric.qualification import measure_peak_rss, run_loader_qualification


class LoaderQualificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.artifact = self.root / "module.bin"
        self.artifact.write_bytes(b"module-payload" * 32)
        self.base = "b" * 64
        self.manifest = ModuleManifest(
            module_id="qual-module", artifact_path="module.bin",
            artifact_sha256=hashlib.sha256(self.artifact.read_bytes()).hexdigest(),
            base_model_sha256=self.base, module_type="adapter",
            task_scope=("test",), precision="int8", estimated_bytes=128,
            min_ram_bytes=1, quality_eval_id="eval", verifier_id="verifier",
            rollback_ref="core", approved=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_measure_peak_rss_reports_timing_and_memory_fields(self):
        result = measure_peak_rss(lambda: time.sleep(0.02), sample_interval_ms=1)
        self.assertGreaterEqual(result["duration_ms"], 0)
        self.assertIn("rss_peak_sampled_bytes", result)
        self.assertIn("rss_retained_delta_bytes", result)

    def test_repeated_cold_warm_unload_trials_are_evidence_only(self):
        manager = BoundedModuleManager(self.root, self.base, 1024, 1024)
        manager.register(self.manifest)
        report = run_loader_qualification(
            manager, "qual-module", trials=3, rss_ceiling_bytes=10**9,
            sample_interval_ms=1,
        )
        self.assertEqual(report["schema"], "merlin-loader-qualification/1")
        self.assertEqual(report["summary"]["trial_count"], 3)
        self.assertTrue(all(not row["resident_after_unload"] for row in report["trials"]))
        self.assertFalse(report["qualified"])
        self.assertFalse(report["promotion_authorized"])
        self.assertEqual(manager.resident_ids(), ())

    def test_invalid_trial_count_rejected(self):
        manager = BoundedModuleManager(self.root, self.base, 1024, 1024)
        manager.register(self.manifest)
        with self.assertRaises(ValueError):
            run_loader_qualification(manager, "qual-module", trials=1)

    def test_unknown_module_rejected(self):
        manager = BoundedModuleManager(self.root, self.base, 1024, 1024)
        with self.assertRaises(ValueError):
            run_loader_qualification(manager, "missing")


if __name__ == "__main__":
    unittest.main()
