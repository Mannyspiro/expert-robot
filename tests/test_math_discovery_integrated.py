"""Contract tests for the integrated mathematical discovery adapters."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from merlin.math_discovery_integrated import (
    BoundedCounterexampleAdapter, IdeonomyConjectureAdapter,
    LeanCompilerAdapter, ReproducibleNumericalAdapter, discover_lean_project,
)


class IntegratedAdapterTests(unittest.TestCase):
    def test_ideonomy_preserves_source_ids_and_blocks_unformalized_claims(self):
        adapter = IdeonomyConjectureAdapter()
        result = adapter({"candidate": {"candidate_id": "candidate-x"},
                          "seeds": [{"conjecture_id": "seed-x"}]})
        self.assertTrue(result)
        self.assertIn("source_ids", result[0])
        self.assertEqual(result[0]["epistemic_status"], "ideonomy_proposal_unformalized")
        self.assertFalse(result[0]["lean_translation_eligible"])

    def test_ideonomy_requires_assumptions_and_falsifiable_formal_statement(self):
        def invalid_factory(_proposal):
            return {"assumptions": [], "falsifiable_statement": "claim",
                    "formal_statement": "True"}
        adapter = IdeonomyConjectureAdapter(invalid_factory)
        with self.assertRaises(ValueError):
            adapter({"candidate": {"candidate_id": "candidate-x"}, "seeds": []})

    def test_lean_project_discovery_reads_pinned_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lean-toolchain").write_text("leanprover/lean4:v4.34.0")
            (root / "lakefile.toml").write_text('name = "test"')
            (root / "lake-manifest.json").write_text('{"packages":[]}')
            project = discover_lean_project(root)
            self.assertEqual(project.toolchain, "leanprover/lean4:v4.34.0")
            self.assertEqual(len(project.manifest_sha256), 64)

    def test_lean_rejects_sorry_without_claiming_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lean-toolchain").write_text("leanprover/lean4:v4.34.0")
            (root / "lakefile.toml").write_text('name = "test"')
            (root / "lake-manifest.json").write_text('{"packages":[]}')
            project = discover_lean_project(root)
            adapter = LeanCompilerAdapter(project)
            result = adapter({"conjecture": {"lean_translation_eligible": True,
                                               "formal_statement": "True"},
                              "source": "theorem x : True := by sorry"})
            self.assertEqual(result["status"], "rejected_placeholder")
            self.assertFalse(result["proof_verified"])

    def test_numerical_reproducibility_requires_identical_replay(self):
        adapter = ReproducibleNumericalAdapter(
            lambda spec: {"value": spec["parameters"]["x"]},
            engine="test", engine_version="1", tool_version="1",
            environment={"runtime": "test"},
        )
        result = adapter({"seed": 7, "precision": "float64",
                          "parameters": {"x": 3}})
        self.assertTrue(result["reproducible"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["raw_output_sha256"]), 64)

    def test_counterexample_timeout_is_not_completed_search(self):
        adapter = BoundedCounterexampleAdapter(
            lambda _spec: {"termination_status": "timeout", "counterexample": None},
            engine="test", engine_version="1", tool_version="1",
        )
        result = adapter({"search_domain": "integers", "bounds": {"min": -10, "max": 10},
                          "method": "exhaustive", "seed": 1})
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["termination_status"], "timeout")


if __name__ == "__main__":
    unittest.main()
