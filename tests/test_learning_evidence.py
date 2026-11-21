from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from dot_ai_os.bridge import DotContextBridge, canonical
from merlin.learning_evidence import LearningEvidenceService
from merlin.learning_platform import Actor, LearningPlatform, LearningConflictError, LearningPermissionError
from merlin.project_registry import MerlinRegistry


class LearningEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.platform = LearningPlatform(self.root / "learning.sqlite3")
        self.registry = MerlinRegistry(self.root / "registry")
        self.registry.register_project("tenant-a-sources", "Reviewed fixture sources")
        self.registry.register_project("tenant-b-sources", "Separate fixture sources")
        self.teacher = Actor("tenant-a", "teacher", "instructor"); self.reviewer = Actor("tenant-a", "reviewer", "reviewer")
        self.learner = Actor("tenant-a", "learner", "learner")
        self.bridge = DotContextBridge(self.registry, project_id="tenant-a-sources", namespaces=("merlin",))
        self.originals = {"unicode": "αβ Titan placeholders are structural data, not decryptable ciphertext.\n",
                          "historical": "Naming conflict: historical Titan described CPU fabric.\n",
                          "current": "Naming conflict: current Titan describes encryption protocol research.\n"}
        self.pins = {name: self.ingest(name, content) for name, content in self.originals.items()}
        self.course = self.platform.create_course(self.teacher, "source-course", "Exact reviewed sources")
        manifest = self.course["manifest"]
        manifest["objectives"] = [{"id": "scope", "title": "Use exact sources", "prerequisites": []}]
        manifest["lessons"] = [{"id": "full", "title": "All sources", "objective_id": "scope", "source_ids": list(self.originals)},
                                 {"id": "unicode-only", "title": "One source", "objective_id": "scope", "source_ids": ["unicode"]},
                                 {"id": "current-only", "title": "One conflict member", "objective_id": "scope", "source_ids": ["current"]}]
        manifest["resources"] = [{"id": name, "title": name, "source_uri": "https://example.org/" + name,
                                    "license": "Synthetic fixture", "creator": "Test", "source_commit": "fixture-v1"} for name in self.originals]
        self.course = self.platform.update_manifest(self.teacher, self.course["course_id"], manifest)
        self.platform.review_course(self.reviewer, self.course["course_id"], 1, "approved", "Synthetic fixture curation")
        self.course = self.platform.publish_course(self.teacher, self.course["course_id"])
        self.platform.enroll(self.learner, self.course["course_id"])
        self.service = LearningEvidenceService(self.platform, self.registry,
            tenant_projects={"tenant-a": "tenant-a-sources", "tenant-b": "tenant-b-sources"}, namespaces=("merlin",))
        self.scope = {"course_id": self.course["course_id"], "course_version": 1, "manifest_sha256": self.course["manifest_sha256"]}
        self.sources = [{"resource_id": name, "record_ref": pin["record_ref"], "source_ref": pin["source_ref"],
                         "review_note": "Curator reviewed this exact synthetic snapshot"} for name, pin in self.pins.items()]
        self.conflicts = [{"conflict_id": "naming", "resource_ids": ["historical", "current"], "note": "Curator-declared historical/current naming disagreement; review before reconciling"}]

    def ingest(self, name, text, version="fixture-v1", **changes):
        return self.bridge.ingest(namespace="merlin", source_id=name, title=name, content=text.encode(),
            source_url="https://example.org/" + name, source_version=version, epistemic="source_snapshot",
            captured_at="2026-11-18T00:00:00Z", **changes)

    def provision(self, **changes):
        return self.service.provision_course_sources(self.teacher, **{**self.scope,
            "sources": self.sources, "conflicts": self.conflicts, **changes})

    def retrieve(self, query="placeholders", **changes):
        return self.service.retrieve(self.learner, **{**self.scope, "query": query, **changes})

    def test_utf8_citations_bind_exact_reviewed_metadata_bytes_and_spans(self):
        receipt = self.provision(); result = self.retrieve()
        self.assertEqual(result["status"], "evidence_available")
        self.assertEqual(result["source_manifest_ref"], receipt["source_manifest_ref"])
        self.assertEqual(len(result["citations"]), 1)
        hit = result["citations"][0]; raw = self.originals["unicode"].encode()
        self.assertEqual(hit["text"].encode(), raw[hit["start_byte"]:hit["end_byte"]])
        self.assertEqual(hit["excerpt_sha256"], hashlib.sha256(hit["text"].encode()).hexdigest())
        self.assertEqual(hit["source_ref"], self.pins["unicode"]["source_ref"])
        self.assertEqual(hit["record_ref"], self.pins["unicode"]["record_ref"])
        self.assertNotIn("answer", result)
        for key in ("qualification", "promotion_authority", "mastery_updated"):
            self.assertFalse(result[key])

    def test_historical_metadata_and_source_remain_pinned_after_latest_changes(self):
        self.provision()
        self.ingest("unicode", "Updated context with a different answer", version="fixture-v2")
        result = self.retrieve()
        self.assertEqual(result["citations"][0]["text"], self.originals["unicode"])
        self.assertEqual(result["citations"][0]["source_version"], "fixture-v1")
        self.assertEqual(result["citations"][0]["record_ref"]["version"], 1)

    def test_abstains_without_relevant_authorized_evidence(self):
        self.provision(); self.ingest("unreviewed", "zebraextraneous secret external source")
        result = self.retrieve("zebraextraneous")
        self.assertEqual(result["status"], "abstain"); self.assertEqual(result["citations"], [])
        self.assertEqual(result["matched_chunks"], 0)

    def test_unrelated_corrupt_context_is_not_read_or_ranked(self):
        self.provision(); pin = self.ingest("unreviewed", "Titan unreviewed evidence")
        blob = self.registry.blobs / pin["source_ref"]["sha256"][:2] / pin["source_ref"]["sha256"][2:]
        blob.write_bytes(b"tampered")
        self.assertEqual(self.retrieve()["status"], "evidence_available")

    def test_curator_conflict_is_explicit_and_includes_all_member_references(self):
        self.provision(); result = self.retrieve("Naming conflict")
        self.assertEqual(result["status"], "requires_review")
        group = result["conflicts"][0]; self.assertEqual(group["conflict_id"], "naming")
        self.assertEqual({row["resource_id"] for row in group["members"]}, {"historical", "current"})
        for member in group["members"]:
            self.assertEqual(member["source_ref"], self.pins[member["resource_id"]]["source_ref"])
            self.assertEqual(member["record_ref"], self.pins[member["resource_id"]]["record_ref"])

    def test_conflict_survives_tight_budget_and_missing_excerpt_members(self):
        self.provision(); full = self.retrieve("Naming conflict")
        for budget in (4000, 5000, 6000):
            result = self.retrieve("Naming conflict", budget_bytes=budget, limit=1)
            self.assertEqual(result["status"], "requires_review")
            self.assertEqual(result["conflicts"][0]["conflict_id"], "naming")
            self.assertEqual(len(result["conflicts"][0]["members"]), 2)
            self.assertLessEqual(len(canonical(result)), budget)
        self.assertGreaterEqual(full["matched_chunks"], 2)

    def test_lesson_scope_filters_before_ranking_and_exposes_omitted_conflict_member(self):
        self.provision()
        self.assertEqual(self.retrieve("Naming conflict", lesson_id="unicode-only")["status"], "abstain")
        result = self.retrieve("Naming conflict", lesson_id="current-only")
        self.assertEqual(result["status"], "requires_review")
        self.assertEqual({hit["resource_id"] for hit in result["citations"]}, {"current"})
        group = result["conflicts"][0]
        self.assertEqual({member["resource_id"] for member in group["members"]}, {"current"})
        self.assertEqual(group["omitted_member_count"], 1); self.assertTrue(group["omission_reason"])

    def test_enrollment_roles_tenants_and_exact_course_version_are_enforced(self):
        self.provision()
        for actor in (self.teacher, {"tenant_id": "tenant-a", "role": "learner"}, Actor("tenant-a", "unknown", "learner"), Actor("tenant-b", "learner", "learner")):
            with self.subTest(actor=actor), self.assertRaises((LearningPermissionError, KeyError)):
                self.service.retrieve(actor, **self.scope, query="Titan")
        with self.assertRaises(LearningConflictError): self.retrieve(manifest_sha256="0" * 64)
        self.platform.create_revision(self.teacher, self.course["course_id"])
        with self.assertRaises((LearningConflictError, LearningPermissionError)):
            self.retrieve(course_version=2)

    def test_only_owner_or_admin_may_attest_source_review(self):
        for actor in (self.learner, self.reviewer, Actor("tenant-a", "other-owner", "instructor")):
            with self.subTest(actor=actor), self.assertRaises(LearningPermissionError):
                self.service.provision_course_sources(actor, **self.scope, sources=self.sources)

    def test_cross_project_wrong_resource_and_unmatched_pin_pairs_are_rejected(self):
        bad = deepcopy(self.sources); bad[0]["source_ref"]["project_id"] = "tenant-b-sources"
        with self.assertRaises(ValueError): self.provision(sources=bad)

    def test_boolean_artifact_or_course_versions_cannot_alias_integer_identity(self):
        sources = deepcopy(self.sources); ref = sources[0]["record_ref"]
        record = json.loads(self.registry.read_artifact_ref(ref)["content"])
        record["source_ref"]["version"] = True
        self.registry.put_artifact(ref["project_id"], ref["logical_path"], canonical(record), "application/json")
        sources[0]["record_ref"] = self.registry.artifact_ref(ref["project_id"], ref["logical_path"])
        with self.assertRaises(ValueError): self.provision(sources=sources)
        receipt = self.provision(); ref = receipt["source_manifest_ref"]
        manifest = json.loads(self.registry.read_artifact_ref(ref)["content"])
        manifest["binding"]["course_version"] = True
        # An exact self-consistent replacement at a fresh course index must also
        # fail structural binding validation, not rely only on a blob hash.
        alternate = self.root / "boolean-registry"
        registry = MerlinRegistry(alternate); registry.register_project("tenant-a-sources", "Fixture")
        registry.register_project("tenant-b-sources", "Fixture")
        for source in self.sources:
            for kind in ("source_ref", "record_ref"):
                original = source[kind]
                registry.put_artifact(original["project_id"], original["logical_path"], self.registry.read_artifact_ref(original)["content"])
        registry.put_artifact(ref["project_id"], ref["logical_path"], canonical(manifest), "application/json")
        service = LearningEvidenceService(self.platform, registry,
            tenant_projects={"tenant-a": "tenant-a-sources", "tenant-b": "tenant-b-sources"}, namespaces=("merlin",))
        with self.assertRaises(LearningConflictError): service.retrieve(self.learner, **self.scope, query="placeholders")
        bad = deepcopy(self.sources); bad[0]["resource_id"] = "not-in-course"
        with self.assertRaises(LearningPermissionError): self.provision(sources=bad)
        bad = deepcopy(self.sources); bad[0]["source_ref"] = self.sources[1]["source_ref"]
        with self.assertRaises(ValueError): self.provision(sources=bad)

    def test_resource_url_version_and_source_review_are_not_inferred(self):
        replacement = self.bridge.ingest(namespace="merlin", source_id="unicode-wrong-url", title="Wrong source",
            content=b"Titan", source_url="https://example.org/another", source_version="fixture-v1",
            epistemic="source_snapshot", captured_at="2026-11-18T00:00:00Z")
        bad = deepcopy(self.sources); bad[0].update(record_ref=replacement["record_ref"], source_ref=replacement["source_ref"])
        with self.assertRaises(LearningConflictError): self.provision(sources=bad)
        replacement = self.ingest("unicode", "Titan modified", version="wrong-version")
        bad[0].update(record_ref=replacement["record_ref"], source_ref=replacement["source_ref"])
        with self.assertRaises(LearningConflictError): self.provision(sources=bad)

    def test_curation_exact_replay_is_one_version_and_changed_curation_is_rejected(self):
        first = self.provision(); second = self.provision()
        self.assertEqual(first, second)
        bad = deepcopy(self.sources); bad[0]["review_note"] = "Changed curation"
        with self.assertRaises(LearningConflictError): self.provision(sources=bad)
        ref = first["source_manifest_ref"]
        self.assertEqual(len(self.registry.artifact_history(ref["project_id"], ref["logical_path"])), 1)

    def test_concurrent_different_curations_cannot_poison_the_frozen_index(self):
        entered = threading.Event(); release = threading.Event(); results = []; errors = []
        put = self.registry.put_artifact
        def paused(*args, **kwargs):
            if args[1].startswith("learning-evidence/"):
                entered.set()
                if not release.wait(3): raise RuntimeError("test release deadline")
            return put(*args, **kwargs)
        def first():
            try: results.append(self.provision())
            except Exception as exc: errors.append(exc)
        with patch.object(self.registry, "put_artifact", side_effect=paused):
            thread = threading.Thread(target=first); thread.start()
            try:
                self.assertTrue(entered.wait(3))
                changed = deepcopy(self.sources); changed[0]["review_note"] = "Conflicting concurrent curation"
                with self.assertRaisesRegex(LearningConflictError, "busy"):
                    self.provision(sources=changed)
            finally:
                release.set(); thread.join(5)
        self.assertFalse(thread.is_alive()); self.assertEqual(errors, [])
        ref = results[0]["source_manifest_ref"]
        self.assertEqual(len(self.registry.artifact_history(ref["project_id"], ref["logical_path"])), 1)
        self.assertEqual(self.provision(), results[0])

    def test_tampered_record_source_or_manifest_cannot_support_retrieval(self):
        receipt = self.provision(); ref = self.pins["unicode"]["record_ref"]
        blob = self.registry.blobs / ref["sha256"][:2] / ref["sha256"][2:]
        original = blob.read_bytes(); blob.write_bytes(b"tampered")
        with self.assertRaises(RuntimeError): self.retrieve()
        blob.write_bytes(original)
        ref = receipt["source_manifest_ref"]
        blob = self.registry.blobs / ref["sha256"][:2] / ref["sha256"][2:]; blob.write_bytes(b"tampered")
        with self.assertRaises(RuntimeError): self.retrieve()

    def test_unknown_ref_arguments_and_invalid_conflict_annotations_are_rejected(self):
        self.provision()
        with self.assertRaises(TypeError): self.retrieve(source_ref=self.pins["unicode"]["source_ref"])
        with self.assertRaises(ValueError): self.provision(conflicts=[{"conflict_id": "bad", "resource_ids": ["unicode", "unknown"], "note": "Bad scope"}])
        with self.assertRaises(ValueError): self.retrieve(budget_bytes=100)

    def test_source_count_and_byte_caps_precede_loading_text(self):
        with self.assertRaises(ValueError): self.provision(sources=self.sources * 11)
        large = self.ingest("unicode", "x" * (self.service.MAX_SOURCE_BYTES + 1))
        sources = deepcopy(self.sources); sources[0].update(record_ref=large["record_ref"], source_ref=large["source_ref"])
        with patch.object(DotContextBridge, "_pinned_records", side_effect=AssertionError("must not load over-budget text")):
            with self.assertRaisesRegex(ValueError, "byte ceiling"):
                self.provision(sources=sources)

    def test_python_39_grammar_and_large_unicode_packet_budget(self):
        import ast
        import merlin.learning_evidence as module
        ast.parse(Path(module.__file__).read_text(), feature_version=(3, 9))
        self.provision()
        with self.assertRaises(ValueError):
            self.retrieve("漢" * 1000, budget_bytes=2000)


if __name__ == "__main__": unittest.main()
