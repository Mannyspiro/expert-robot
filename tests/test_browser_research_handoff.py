"""Synthetic retained-record tests; no browser, network or model execution."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from merlin.project_registry import MerlinRegistry
from dot_ai_os.bridge import canonical, digest
from merlin.browser_research_handoff import (
    BrowserResearchHandoff, HandoffError, MAX_FILES, PROGRAM_ID, PROJECT, SCHEMA, TRACK,
)


PROGRAM = canonical({"schema": "merlin-research-program/1", "program_id": PROGRAM_ID,
                     "version": 1, "tracks": [{"id": TRACK}],
                     "qualification": False, "promotion_authority": False})
STAMP = "2026-11-21T12:00:00+00:00"


def retained_fixture(registry, *, episode="retained-fixture", urls=None, usable=True, mutate=None):
    """Synthetic publication shape, explicitly not a browser-execution attestation."""
    urls = urls or ["https://example.org/source"]
    base = "browser/episodes/" + episode + "/"
    files = {}; artifacts = {}; observations = []; sources = []; actions = []

    def add(path, raw, media):
        descriptor = {"path": path, "bytes": len(raw), "sha256": digest(raw), "media_type": media}
        registry.put_artifact(PROJECT, base + path, raw, media)
        artifacts[path] = registry.artifact_ref(PROJECT, base + path)
        files[path] = descriptor
        return descriptor

    for number, url in enumerate(urls, 1):
        oid, aid = "o%04d" % number, "a%04d" % number
        path = "observations/" + oid + "/"
        descriptors = {
            "text": add(path + "text.txt", ("source text 梅林 " + str(number)).encode() if usable else b"", "text/plain"),
            "dom": add(path + "dom.html", b"<html><body>synthetic fixture</body></html>", "text/html"),
            "screenshot": add(path + "viewport.png", b"\x89PNG\r\n\x1a\nsynthetic", "image/png"),
            "response_body": add(path + "response.bin", b"fixture response", "application/octet-stream"),
        }
        observation = {"id": oid, "action_id": aid, "url": url, "document_url": url,
                       "document_status": 200 if usable else 503, "captured_at": STAMP,
                       "artifacts": descriptors, "qualification": False, "epistemic": "source_snapshot"}
        envelope = {"sequence": number, "previous_sha256": "0" * 64, "recorded_at": STAMP,
                    "event": {"kind": "observation", "observation": observation}}
        envelope["event_sha256"] = digest(canonical(envelope))
        event = add("events/%04d.json" % number, canonical(envelope), "application/json")
        observations.append({"id": oid, "action_id": aid, "event_ref": event})
        sources.append({"observation_id": oid, "acquisition_url": url,
                        "capture_event_ref": artifacts[event["path"]],
                        "artifacts": {name: artifacts[desc["path"]] for name, desc in descriptors.items()},
                        "context_intake": "ineligible_url_contract" if "?" in url or url.startswith("http:") else "source_snapshot",
                        "source_ref": None, "qualification": False})
        actions.append({"id": aid, "status": "succeeded" if usable else "failed", "observation_id": oid})
    manifest = {"schema": "merlin-public-browser-episode/1", "episode_id": episode,
                "started_at": STAMP, "completed_at": STAMP,
                "status": "completed" if usable else "completed_with_failures",
                "files": list(files.values()), "observations": observations, "actions": actions,
                "model_calls": 0, "external_model_cost_usd": 0, "qualification": False, "promotion_authority": False}
    publication = {"schema": "merlin-browser-publication/1", "episode_id": episode,
                   "manifest_sha256": "", "manifest_ref": None, "handoff_ref": None,
                   "context_handoff_ref": None, "artifacts": artifacts, "sources": sources,
                   "status": manifest["status"], "model_calls": 0, "qualification": False, "promotion_authority": False}
    if mutate:
        mutate(manifest, publication)
    registry.put_artifact(PROJECT, base + "episode.json", canonical(manifest), "application/json")
    mref = registry.artifact_ref(PROJECT, base + "episode.json")
    handoff = {"schema": "merlin-browser-handoff/1", "episode_id": episode,
               "manifest_ref": mref, "manifest_sha256": mref["sha256"], "sources": sources,
               "status": manifest["status"], "model_calls": 0, "qualification": False, "promotion_authority": False}
    registry.put_artifact(PROJECT, base + "handoff.json", canonical(handoff), "application/json")
    publication.update(manifest_ref=mref, manifest_sha256=mref["sha256"],
                       handoff_ref=registry.artifact_ref(PROJECT, base + "handoff.json"))
    registry.put_artifact(PROJECT, base + "publication.json", canonical(publication), "application/json")
    return {"schema": SCHEMA, "request_id": str(uuid.uuid4()), "episode_id": episode,
            "publication_ref": registry.artifact_ref(PROJECT, base + "publication.json")}


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "registry"
        self.registry = MerlinRegistry(self.root)
        self.registry.register_project(PROJECT, "Synthetic retained-source fixture")
        self.allowed = True
        self.worker = self.reopen()

    def reopen(self, **changes):
        arguments = {"source_commit": "a" * 40, "program_bytes": PROGRAM,
                     "authorize": lambda operation, binding: self.allowed}
        arguments.update(changes)
        return BrowserResearchHandoff(MerlinRegistry(self.root), **arguments)

    def body(self, ref):
        return json.loads(self.registry.read_artifact_ref(ref)["content"])

    def corrupt(self, ref):
        (self.registry.blobs / ref["sha256"][:2] / ref["sha256"][2:]).write_bytes(b"corrupt")

    def test_plan_precedes_measurement_and_review_has_only_source_claims(self):
        request = retained_fixture(self.registry)
        original = self.worker._measure
        def checked(identity, observed_at):
            self.registry.artifact_ref(PROJECT, "research/browser-intake-" + identity["request_id"] + "/plan.json")
            return original(identity, observed_at)
        with patch.object(self.worker, "_measure", checked):
            answer = self.worker.submit(request)
        self.assertEqual(answer["status"], "recorded")
        result = answer["result"]; plan = self.body(result["plan_ref"])
        measurement = self.body(result["measurement_ref"]); review = self.body(result["review_ref"])
        self.assertEqual(measurement["counts"]["verified_input_artifacts"], 8)
        self.assertEqual(measurement["counts"]["usable_captures"], 1)
        self.assertEqual(review["deductive_assessments"][0]["overall"], "consistent_with_prediction")
        self.assertEqual(set(plan["representation_checks"]), {"simplex", "n_ality", "continuum", "fuzzy_logic"})
        for value in (result, measurement):
            self.assertEqual(value["domain_execution"], "not_run")
            self.assertEqual(value["model_calls"], 0); self.assertEqual(value["new_browser_calls"], 0)
            self.assertFalse(value["qualification"]); self.assertFalse(value["promotion_authority"])
        self.assertIn("predates", plan["frame"]["assumptions"][1])

    def test_restart_replays_exact_refs_without_measurement_or_new_versions(self):
        request = retained_fixture(self.registry)
        first = self.worker.submit(request)
        before = self.registry.artifact_paths(PROJECT, limit=1000)["paths"]
        restored = self.reopen()
        with patch.object(restored, "_measure", side_effect=AssertionError("must not remeasure")):
            replay = restored.submit(request)
            status = restored.status(request["request_id"])
        self.assertTrue(replay["replayed"]); self.assertEqual(replay["result_ref"], first["result_ref"])
        self.assertEqual(replay["result"], first["result"]); self.assertEqual(status["result"], first["result"])
        self.assertEqual(self.registry.artifact_paths(PROJECT, limit=1000)["paths"], before)
        self.assertTrue(all(len(self.registry.artifact_history(PROJECT, path)) == 1 for path in before))

    def test_http_query_and_unicode_urls_remain_exact_usable_sources(self):
        urls = ["http://example.org/data?q=%E6%A2%85%E6%9E%97", "https://example.org/search?q=rank&part=2"]
        answer = self.worker.submit(retained_fixture(self.registry, urls=urls))
        measurement = self.body(answer["result"]["measurement_ref"])
        self.assertEqual([row["acquisition_url"] for row in measurement["captures"]], urls)
        self.assertEqual(measurement["counts"]["usable_captures"], 2)
        self.assertEqual(measurement["counts"]["reported_bridge_source_snapshots"], 0)

    def test_no_usable_capture_retains_a_negative_typed_review(self):
        answer = self.worker.submit(retained_fixture(self.registry, usable=False))
        self.assertEqual(answer["status"], "recorded")
        self.assertEqual(answer["result"]["decision"], "no_usable_capture")
        review = self.body(answer["result"]["review_ref"])
        self.assertEqual(review["deductive_assessments"][0]["overall"], "contradicted")
        self.assertFalse(review["qualification"])

    def test_optional_bridge_snapshot_count_is_reported_not_verified(self):
        answer = self.worker.submit(retained_fixture(self.registry))
        measurement = self.body(answer["result"]["measurement_ref"])
        self.assertEqual(measurement["counts"]["reported_bridge_source_snapshots"], 1)
        self.assertNotIn("bridge_source_snapshots", measurement["counts"])
        self.assertEqual(measurement["optional_bridge_records"], "reported_intake_only_not_resolved_by_this_measurement")

    def test_cross_project_publication_is_rejected_before_intent(self):
        request = retained_fixture(self.registry)
        request["publication_ref"]["project_id"] = "private-project"
        with self.assertRaisesRegex(HandoffError, "cross-project"):
            self.worker.submit(request)
        self.assertEqual(self.worker.status(request["request_id"])["status"], "not_found")

    def test_cross_project_nested_file_is_rejected_and_failure_is_retained(self):
        def change(manifest, publication):
            publication["artifacts"][next(iter(publication["artifacts"]))]["project_id"] = "other"
        request = retained_fixture(self.registry, mutate=change)
        answer = self.worker.submit(request)
        self.assertEqual(answer["status"], "reconciliation_needed")
        self.assertEqual(answer["failure"]["stage"], "measurement")
        self.assertIn("cross-project", answer["failure"]["reason"])

    def test_corrupt_capture_bytes_cannot_produce_a_review(self):
        request = retained_fixture(self.registry)
        publication = self.body(request["publication_ref"])
        self.corrupt(publication["sources"][0]["artifacts"]["text"])
        answer = self.worker.submit(request)
        self.assertEqual(answer["status"], "reconciliation_needed")
        self.assertEqual(answer["failure"]["error_type"], "RuntimeError")
        paths = self.registry.artifact_paths(PROJECT, prefix="research/browser-intake-" + request["request_id"], limit=100)["paths"]
        self.assertEqual(len(paths), 1)

    def test_same_request_id_with_changed_episode_is_rejected(self):
        request = retained_fixture(self.registry)
        self.worker.submit(request)
        other = retained_fixture(self.registry, episode="other")
        other["request_id"] = request["request_id"]
        with self.assertRaisesRegex(HandoffError, "reused"):
            self.worker.submit(other)

    def test_changed_program_or_source_pin_cannot_replay_old_success(self):
        request = retained_fixture(self.registry); self.worker.submit(request)
        with self.assertRaisesRegex(HandoffError, "binding"):
            self.reopen(source_commit="b" * 40).status(request["request_id"])
        altered = json.loads(PROGRAM); altered["version"] = 2
        with self.assertRaisesRegex(HandoffError, "binding"):
            self.reopen(program_bytes=canonical(altered)).submit(request)

    def test_fully_rehashed_publication_cannot_substitute_capture_url(self):
        def change(manifest, publication):
            publication["sources"][0]["acquisition_url"] = "https://example.org/wrong"
        answer = self.worker.submit(retained_fixture(self.registry, mutate=change))
        self.assertEqual(answer["status"], "reconciliation_needed")
        self.assertIn("URL", answer["failure"]["reason"])

    def test_fully_rehashed_action_reassignment_is_rejected(self):
        def change(manifest, publication):
            manifest["actions"][0]["observation_id"] = "o0002"
        answer = self.worker.submit(retained_fixture(self.registry, urls=["https://example.org/1", "https://example.org/2"], mutate=change))
        self.assertEqual(answer["status"], "reconciliation_needed")
        self.assertIn("lineage", answer["failure"]["reason"])

    def test_uncaptured_action_cannot_bypass_status_validation(self):
        def change(manifest, publication):
            manifest["actions"].append({"id": "a0002", "status": "unknown", "observation_id": None})
        answer = self.worker.submit(retained_fixture(self.registry, mutate=change))
        self.assertEqual(answer["status"], "reconciliation_needed")
        self.assertIn("status", answer["failure"]["reason"])

    def test_orphan_partial_records_without_intent_are_not_reused(self):
        request = retained_fixture(self.registry)
        self.registry.put_artifact(PROJECT, "research-handoffs/" + request["request_id"] + "/program.json", PROGRAM)
        with self.assertRaisesRegex(HandoffError, "orphan"):
            self.worker.submit(request)
        self.assertEqual(self.worker.status(request["request_id"])["status"], "reconciliation_needed")

    def test_interrupted_after_measurement_does_not_execute_again(self):
        request = retained_fixture(self.registry)
        original = self.worker._typed_put
        def crash(record):
            if record["schema"] == "merlin-research-review/1":
                raise SystemExit("simulated host process interruption")
            return original(record)
        with patch.object(self.worker, "_typed_put", crash), self.assertRaises(SystemExit):
            self.worker.submit(request)
        before = self.registry.artifact_paths(PROJECT, limit=1000)["paths"]
        restored = self.reopen()
        with patch.object(restored, "_measure", side_effect=AssertionError("must not remeasure")):
            status = restored.submit(request)
        self.assertEqual(status["status"], "reconciliation_needed")
        self.assertIsNone(status["failure_ref"]); self.assertFalse(status["execution_retried"])
        self.assertEqual(self.registry.artifact_paths(PROJECT, limit=1000)["paths"], before)

    def test_completed_replay_rejects_corrupt_review(self):
        request = retained_fixture(self.registry); answer = self.worker.submit(request)
        self.corrupt(answer["result"]["review_ref"])
        with self.assertRaises(RuntimeError):
            self.reopen().status(request["request_id"])

    def test_completed_replay_rejects_corrupt_original_capture(self):
        request = retained_fixture(self.registry); self.worker.submit(request)
        publication = self.body(request["publication_ref"])
        self.corrupt(publication["sources"][0]["artifacts"]["response_body"])
        with self.assertRaises(RuntimeError):
            self.reopen().status(request["request_id"])

    def test_fully_rehashed_result_cannot_invent_domain_execution_or_success(self):
        request = retained_fixture(self.registry, usable=False)
        answer = self.worker.submit(request)
        other = MerlinRegistry(Path(self.temp.name) / "cloned-fixture")
        other.register_project(PROJECT, "Synthetic malformed retained result")
        for path in self.registry.artifact_paths(PROJECT, limit=1000)["paths"]:
            raw = self.registry.read_artifact_ref(self.registry.artifact_ref(PROJECT, path))["content"]
            if path == answer["result_ref"]["logical_path"]:
                value = json.loads(raw)
                value.update(domain_execution="completed", new_browser_calls=7,
                             external_model_cost_usd=100, decision="source_intake_available")
                raw = canonical(value)
            other.put_artifact(PROJECT, path, raw, "application/json")
        worker = BrowserResearchHandoff(other, source_commit="a" * 40, program_bytes=PROGRAM,
                                       authorize=lambda operation, binding: True)
        with self.assertRaisesRegex(HandoffError, "result contract"):
            worker.status(request["request_id"])

    def test_retained_intent_request_identity_must_match_its_path(self):
        request = retained_fixture(self.registry)
        intent = {"schema": "merlin-browser-research-handoff-intent/1", "request": request,
                  "binding": self.worker.binding, "observed_at": STAMP,
                  "effect_policy": "no_automatic_retry_after_intent", "qualification": False, "promotion_authority": False}
        different = str(uuid.uuid4())
        self.registry.put_artifact(PROJECT, "research-handoffs/" + different + "/intent.json", canonical(intent))
        with self.assertRaisesRegex(HandoffError, "request/path identity"):
            self.worker.status(different)

    def test_authorization_denial_cannot_create_an_intent(self):
        request = retained_fixture(self.registry); self.allowed = False
        with self.assertRaises(PermissionError):
            self.worker.submit(request)
        self.allowed = True
        self.assertEqual(self.worker.status(request["request_id"])["status"], "not_found")

    def test_unlisted_inventory_entry_is_rejected(self):
        def change(manifest, publication):
            manifest["files"] = manifest["files"][1:]
        answer = self.worker.submit(retained_fixture(self.registry, mutate=change))
        self.assertEqual(answer["status"], "reconciliation_needed")
        self.assertIn("coverage", answer["failure"]["reason"])

    def test_oversized_inventory_is_rejected_before_reading_files(self):
        def change(manifest, publication):
            manifest["files"] = manifest["files"] * (MAX_FILES + 1)
        answer = self.worker.submit(retained_fixture(self.registry, mutate=change))
        self.assertEqual(answer["status"], "reconciliation_needed")
        self.assertIn(answer["failure"]["error_type"], {"HandoffError", "ArtifactSizeLimitError"})

    def test_duplicate_or_extra_request_fields_do_not_expand_the_api(self):
        request = retained_fixture(self.registry)
        for extra in ({"shell": "ignored"}, {"project_id": "other"}, {"url": "https://example.org"}, {"actions": []}):
            with self.subTest(extra=extra), self.assertRaises(HandoffError):
                self.worker.submit({**request, **extra})
        self.assertEqual(self.worker.status(request["request_id"])["status"], "not_found")


if __name__ == "__main__":
    unittest.main(verbosity=2)
