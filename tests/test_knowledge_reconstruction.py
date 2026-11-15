from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from merlin.knowledge_compression import store_knowledge_representation
from merlin.knowledge_reconstruction import (
    RECONSTRUCTION_SCHEMA,
    ReconstructionLimitError,
    reconstruct_source_artifacts,
)
from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry


class KnowledgeReconstructionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.registry = MerlinRegistry(self.root / "registry")
        self.registry.register_project("merlin", "Merlin")
        self.graph = MerlinKnowledgeGraph(self.root / "knowledge-graph.sqlite3")
        self.source_a = b"Exact source A\nwith two lines.\n"
        self.source_b = b"Exact source B."
        self.registry.put_artifact("merlin", "sources/a.txt", self.source_a, "text/plain")
        self.registry.put_artifact("merlin", "sources/b.txt", self.source_b, "text/plain")
        self.ref_a = self.registry.artifact_ref("merlin", "sources/a.txt")
        self.ref_b = self.registry.artifact_ref("merlin", "sources/b.txt")

    def tearDown(self):
        self.temp.cleanup()

    def _store(self, refs=None, bindings=None):
        refs = refs or [self.ref_a]
        bindings = bindings or [{
            "artifact_ref": refs[0],
            "locator_type": "line_range",
            "locator": {"start": 1, "end": 2},
        }]
        return store_knowledge_representation(
            self.registry,
            self.graph,
            project_id="merlin",
            representation_type="summary",
            payload={"summary": "A concise derived summary."},
            source_refs=refs,
            source_bindings=bindings,
            tool_id="test-compressor",
            tool_version="0.1.0",
            loss_character="lossy",
            source_repo="Mannyspiro/expert-robot",
            source_commit="b" * 40,
        )

    def test_recovers_exact_original_source_bytes_and_reports_limits(self):
        stored = self._store()
        result = reconstruct_source_artifacts(self.registry, stored["representation_ref"])
        report = result["report"]
        self.assertEqual(report["schema"], RECONSTRUCTION_SCHEMA)
        self.assertTrue(report["all_source_bytes_exact"])
        self.assertEqual(report["semantic_equivalence"], "not_assessed")
        self.assertEqual(report["cace_verification"], "not_requested")
        self.assertFalse(report["qualification"])
        self.assertEqual(result["source_payloads"][0]["content"], self.source_a)
        self.assertEqual(report["source_results"][0]["source_sha256"], self.ref_a["sha256"])
        self.assertEqual(report["total_source_bytes"], len(self.source_a))
        self.assertEqual(len(report["report_sha256"]), 64)

    def test_recovers_multiple_sources_and_all_exact_locators(self):
        stored = self._store(
            refs=[self.ref_a, self.ref_b],
            bindings=[
                {"artifact_ref": self.ref_a, "locator_type": "line_range", "locator": "1-2"},
                {"artifact_ref": self.ref_a, "locator_type": "section", "locator": "Intro"},
                {"artifact_ref": self.ref_b, "locator_type": "whole_artifact", "locator": "entire source"},
            ],
        )
        result = reconstruct_source_artifacts(self.registry, stored["representation_ref"])
        self.assertEqual(
            [item["content"] for item in result["source_payloads"]],
            [self.source_a, self.source_b],
        )
        self.assertEqual(result["report"]["source_count"], 2)
        self.assertEqual(
            len(result["report"]["source_results"][0]["source_bindings"]), 2,
        )
        self.assertEqual(
            result["report"]["total_source_bytes"],
            len(self.source_a) + len(self.source_b),
        )

    def test_rejects_modified_manifest_even_when_artifact_hash_is_valid(self):
        stored = self._store()
        ref = stored["representation_ref"]
        original = self.registry.read_artifact_ref(ref)["content"]
        manifest = json.loads(original)
        manifest["payload"]["summary"] = "tampered summary"
        self.registry.put_artifact(
            "merlin",
            ref["logical_path"],
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            "application/vnd.merlin.knowledge-representation+json",
        )
        latest_ref = self.registry.artifact_ref("merlin", ref["logical_path"])
        with self.assertRaisesRegex(ValueError, "identity does not match"):
            reconstruct_source_artifacts(self.registry, latest_ref)

    def test_enforces_total_and_per_source_byte_budgets(self):
        stored = self._store()
        with self.assertRaises(ReconstructionLimitError):
            reconstruct_source_artifacts(
                self.registry, stored["representation_ref"], max_total_bytes=4,
            )
        with self.assertRaises(ValueError):
            reconstruct_source_artifacts(
                self.registry, stored["representation_ref"], max_source_bytes=0,
            )

    def test_rejects_representation_path_and_schema_substitution(self):
        stored = self._store()
        bad_ref = dict(stored["representation_ref"])
        bad_ref["logical_path"] = "knowledge/representations/not-the-id.json"
        with self.assertRaisesRegex(ValueError, "unexpected logical path|does not match"):
            reconstruct_source_artifacts(self.registry, bad_ref)

    def test_rejects_malformed_source_locator_binding(self):
        stored = self._store()
        ref = stored["representation_ref"]
        manifest = json.loads(self.registry.read_artifact_ref(ref)["content"])
        manifest["source_bindings"] = []
        body = {k: v for k, v in manifest.items() if k != "representation_id"}
        import hashlib
        from merlin.knowledge_compression import canonical_json
        manifest["representation_id"] = hashlib.sha256(canonical_json(body)).hexdigest()
        path = f"knowledge/representations/{manifest['representation_id']}.json"
        self.registry.put_artifact(
            "merlin", path, canonical_json(manifest),
            "application/vnd.merlin.knowledge-representation+json",
        )
        new_ref = self.registry.artifact_ref("merlin", path)
        with self.assertRaises(ValueError):
            reconstruct_source_artifacts(self.registry, new_ref)


if __name__ == "__main__":
    unittest.main()
