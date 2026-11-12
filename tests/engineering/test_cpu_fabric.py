import hashlib
import tempfile
import unittest
from pathlib import Path

from python.merlin.cpu_fabric.catalog import BoundedModuleManager, CatalogError, ModuleManifest
from python.merlin.cpu_fabric.strategy_eval import run_paired_trials


class CpuFabricRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.artifact = self.root / "adapter.bin"
        self.artifact.write_bytes(b"bounded test artifact")
        self.base = "a" * 64
        self.manifest = ModuleManifest(
            module_id="adapter", artifact_path="adapter.bin",
            artifact_sha256=hashlib.sha256(self.artifact.read_bytes()).hexdigest(),
            base_model_sha256=self.base, module_type="adapter",
            task_scope=("math",), precision="int8", estimated_bytes=64,
            min_ram_bytes=1, quality_eval_id="eval", verifier_id="verifier",
            rollback_ref="core", approved=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_registration_and_activation_enforce_transient_cap(self):
        manager = BoundedModuleManager(self.root, self.base, 128, 128,
                                       max_artifact_bytes=8)
        with self.assertRaises(CatalogError):
            manager.register(self.manifest)

    def test_activation_rechecks_transient_cap_after_registration(self):
        manager = BoundedModuleManager(self.root, self.base, 128, 128,
                                       max_artifact_bytes=128)
        manager.register(self.manifest)
        self.artifact.write_bytes(b"x" * 129)
        with self.assertRaisesRegex(CatalogError, "transient memory limit"):
            manager.activate("adapter")

    def test_loader_receives_exact_verified_snapshot(self):
        received = []
        manager = BoundedModuleManager(
            self.root, self.base, 128, 128,
            loader=lambda payload: received.append(bytes(payload)) or "handle",
            max_artifact_bytes=128,
        )
        manager.register(self.manifest)
        self.assertEqual(manager.activate("adapter"), "handle")
        self.assertEqual(received, [self.artifact.read_bytes()])

    def test_randomized_paired_differences_and_heldout_split(self):
        def baseline(seed):
            return {"quality": .97, "latency_ms": 20 + seed,
                    "peak_rss_bytes": 100, "resident_bytes": 80}
        def candidate(seed):
            return {"quality": .98, "latency_ms": 15 + seed,
                    "peak_rss_bytes": 90, "resident_bytes": 70}
        result = run_paired_trials(
            {"baseline": baseline, "candidate": candidate},
            (1, 2, 3, 4), .95, held_out_seeds=(21, 22, 23), order_seed=91,
        )
        dev = result["development"]
        self.assertEqual(dev["paired_differences"]["candidate"]["latency_ms"]["mean_difference_vs_baseline"], -5)
        self.assertEqual(result["held_out"]["seed_set"], [21, 22, 23])
        self.assertEqual(len(dev["randomized_order"]), 4)
        self.assertFalse(result["promotion_authorized"])

    def test_development_and_heldout_seeds_must_be_disjoint(self):
        evaluator = lambda seed: {"quality": .9, "latency_ms": 1,
                                  "peak_rss_bytes": 1, "resident_bytes": 1}
        with self.assertRaises(ValueError):
            run_paired_trials({"baseline": evaluator}, (1, 2), .8,
                              held_out_seeds=(2, 3))


if __name__ == "__main__":
    unittest.main()
