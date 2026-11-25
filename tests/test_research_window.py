"""Observable state, exact evidence identity, and read-only window boundaries."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlsplit

from merlin.hud_activity import HudActivityProjector
from merlin.research_window import ResearchWindow
from merlin.research_window_ui import DASHBOARD_HTML


NOW = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)


def event(kind, *, run="weighted", when=NOW, source="operator", **payload):
    return {"source": source, "kind": kind, "run_id": run,
            "timestamp": when.isoformat(), "payload": payload}


def request(window, url, method="GET"):
    parsed = urlsplit(url)
    response = []
    body = b"".join(window.application(
        {"PATH_INFO": parsed.path, "QUERY_STRING": parsed.query,
         "REQUEST_METHOD": method},
        lambda status, headers: response.append((status, dict(headers))),
    ))
    return response[0][0], response[0][1], body


class ResearchActivityTests(unittest.TestCase):
    def test_recent_active_stale_waiting_and_explicit_completion(self):
        projection = HudActivityProjector()
        projection.ingest(event("task.started", question="Unequal positive weights"))
        self.assertEqual(projection.snapshot(now=NOW)["run_status"], "active")
        self.assertEqual(projection.snapshot(now=NOW + timedelta(seconds=91))["run_status"], "waiting")
        projection.ingest(event("task.progress", when=NOW + timedelta(seconds=92), status="waiting"))
        self.assertEqual(projection.snapshot(now=NOW + timedelta(seconds=93))["run_status"], "waiting")
        projection.ingest(event("task.completed", when=NOW + timedelta(seconds=94)))
        self.assertEqual(projection.snapshot(now=NOW + timedelta(days=1))["run_status"], "completed")

    def test_failure_is_terminal_until_explicit_resumption(self):
        projection = HudActivityProjector()
        projection.ingest_many([event("task.started"), event("system.error", summary="Checker unavailable"),
                                event("artifact.registered", summary="Source retained")])
        self.assertEqual(projection.snapshot(now=NOW)["run_status"], "failed")
        projection.ingest(event("task.progress", status="active", summary="Checker reconnected"))
        self.assertEqual(projection.snapshot(now=NOW)["run_status"], "active")

    def test_invalid_timestamp_does_not_indicate_live_activity(self):
        projection = HudActivityProjector()
        value = event("task.started")
        value["timestamp"] = "not-a-time"
        projection.ingest(value)
        snapshot = projection.snapshot(now=NOW)
        self.assertEqual(snapshot["run_status"], "waiting")
        self.assertIsNone(snapshot["latest_event_age_seconds"])

    def test_latest_run_does_not_inherit_prior_proof_or_metrics(self):
        projection = HudActivityProjector()
        projection.ingest(event("task.completed", run="prior", proof_status="Prior theorem checked",
                                metrics={"prior_theorems": 46}))
        projection.ingest(event("task.started", run="new", question="New candidate"))
        current = projection.snapshot(now=NOW)
        self.assertEqual(current["active_run_id"], "new")
        self.assertEqual(current["event_count"], 1)
        self.assertNotIn("proof_status", current["research"])
        self.assertNotIn("metrics", current["research"])
        self.assertEqual(projection.snapshot(run_id="prior", now=NOW)["run_status"], "completed")

    def test_artifact_cannot_complete_or_advance_pending_proof(self):
        projection = HudActivityProjector()
        projection.ingest_many([
            event("task.started", question="Weighted theorem"),
            event("task.progress", stage="formalization", status="active",
                  proof_status="Candidate; proof pending", summary="Checking the weighted bound"),
            event("artifact.registered", source="runtime", summary="Registered candidate source"),
            event("artifact.registered", source="runtime", summary="Registered explanatory graph",
                  node_id="artifact:graph", display_kind="graph"),
        ])
        state = projection.snapshot(now=NOW)
        self.assertEqual(state["phase"], "formalization")
        self.assertEqual(state["completed_stages"], [])
        self.assertEqual(state["research"]["summary"], "Checking the weighted bound")
        self.assertEqual(state["research"]["proof_status"], "Candidate; proof pending")
        self.assertIsNone(state["verification"])
        self.assertEqual(state["resources"], {})
        self.assertEqual(state["run_status"], "active")
        self.assertEqual(state["timeline"][-1]["artifact_node_id"], "artifact:graph")
        self.assertEqual(state["timeline"][-1]["artifact_display_kind"], "graph")
        projection.ingest(event("research.stage", stage="verification", completed_stages=["experiment", "formalization"]))
        state = projection.snapshot(now=NOW)
        self.assertEqual(state["completed_stages"], ["experiment", "formalization"])
        self.assertNotIn("verification", state["completed_stages"])

    def test_reported_verification_does_not_fabricate_cace_attestation(self):
        projection = HudActivityProjector()
        value = event("verification.completed", source="operator", status="verified", independent=True)
        value["evidence_refs"] = ["sha256:" + "a" * 64]
        projection.ingest(value)
        self.assertIsNone(projection.snapshot(now=NOW)["verification"])


class ResearchWindowBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.allowed = self.root / "research"
        self.allowed.mkdir()
        self.window = ResearchWindow(self.root / "state")

    def register(self, filename, content, kind="source"):
        path = self.allowed / filename
        path.write_bytes(content)
        return self.window.register_artifact(path, allowed_roots=[self.allowed],
                                            run_id="weighted", title=filename, display_kind=kind)

    def test_exact_lean_source_is_readable_as_plain_text_with_identity(self):
        content = "import Mathlib\n-- ∑ wᵢ = M; α² ≥ 0\n".encode("utf-8")
        registered = self.register("Weighted.lean", content)
        status, headers, body = request(self.window, registered["url"])
        self.assertEqual(status, "200 OK")
        self.assertEqual(body, content)
        self.assertEqual(headers["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(headers["X-Artifact-SHA256"], sha256(content).hexdigest())
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("sandbox", headers["Content-Security-Policy"])

    def test_exact_graph_bytes_and_historical_version_are_pinned(self):
        first = b'<svg xmlns="http://www.w3.org/2000/svg"><text>first</text></svg>'
        second = b'<svg xmlns="http://www.w3.org/2000/svg"><text>second</text></svg>'
        old = self.register("bound.svg", first, "graph")
        new = self.register("bound.svg", second, "graph")
        self.assertNotEqual(old["node_id"], new["node_id"])
        self.assertEqual(old["artifact_ref"]["version"], 1)
        self.assertEqual(new["artifact_ref"]["version"], 2)
        self.assertEqual(request(self.window, old["url"])[2], first)
        self.assertEqual(request(self.window, new["url"])[2], second)
        self.assertEqual(request(self.window, old["url"])[1]["Content-Type"], "image/svg+xml")
        _, _, detail = request(self.window, "/api/hud/node?node_id=" + old["node_id"])
        linked = json.loads(detail)["linked_artifacts"][0]
        self.assertEqual(linked["artifact_ref"], old["artifact_ref"])
        self.assertFalse(linked["is_current"])
        reverted = self.register("bound.svg", first, "graph")
        self.assertEqual(reverted["artifact_ref"]["version"], 3)
        self.assertNotEqual(old["node_id"], reverted["node_id"])
        _, _, detail = request(self.window, "/api/hud/node?node_id=" + reverted["node_id"])
        self.assertEqual(json.loads(detail)["node"]["payload"]["artifact_ref"], reverted["artifact_ref"])

    def test_tampered_blob_fails_closed_without_leaking_path(self):
        registered = self.register("Weighted.lean", b"original source")
        digest = registered["artifact_ref"]["sha256"]
        blob = self.window.registry.blobs / digest[:2] / digest[2:]
        blob.write_bytes(b"modified source")
        status, _, body = request(self.window, registered["url"])
        self.assertEqual(status, "503 Service Unavailable")
        self.assertEqual(json.loads(body)["error"], "hud_projection_unavailable")
        self.assertNotIn(str(self.root).encode(), body)
        self.assertNotIn(b"modified source", body)

    def test_disallowed_path_symlink_traversal_and_media_are_rejected(self):
        outside = self.root / "outside.lean"
        outside.write_text("outside")
        link = self.allowed / "escaped.lean"
        link.symlink_to(outside)
        for path in (outside, link):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "explicitly allowed"):
                self.window.register_artifact(path, allowed_roots=[self.allowed],
                                              run_id="weighted", title="outside", display_kind="source")
        inside = self.allowed / "inside.lean"
        inside.write_text("inside")
        with self.assertRaises(ValueError):
            self.window.register_artifact(inside, allowed_roots=[self.allowed], run_id="weighted",
                                          title="escape", display_kind="source", logical_path="../escape")
        with self.assertRaisesRegex(ValueError, "unsupported media"):
            self.register("executable.html", b"<script>alert(1)</script>")
        with self.assertRaisesRegex(ValueError, "image artifacts"):
            self.register("not-text.png", b"image bytes", "source")

    def test_unregistered_files_and_mutating_http_requests_are_unavailable(self):
        for url, expected in [("/api/hud/artifact", "400 Bad Request"),
                              ("/api/hud/artifact?node_id=artifact:missing", "404 Not Found"),
                              ("/api/hud/artifact?path=/etc/passwd", "400 Bad Request"),
                              ("/arbitrary/path", "404 Not Found")]:
            self.assertEqual(request(self.window, url)[0], expected)
        for url in ("/dashboard", "/api/hud/activity", "/api/hud/graph", "/api/hud/artifact"):
            status, headers, _ = request(self.window, url, method="POST")
            self.assertEqual(status, "405 Method Not Allowed")
            self.assertEqual(headers["Allow"], "GET")

    def test_restart_restores_canonical_events_without_acknowledging_them(self):
        self.window.emit(event("task.started", question="Restart checkpoint"))
        self.register("Proof.lean", b"candidate proof")
        before_counts = self.window.outbox.counts()
        before_graph = self.window.graph.export_snapshot()
        restored = ResearchWindow(self.root / "state")
        status, _, body = request(restored, "/api/hud/activity")
        self.assertEqual(status, "200 OK")
        state = json.loads(body)
        self.assertEqual(state["event_count"], 2)
        self.assertEqual(state["research"]["question"], "Restart checkpoint")
        for _ in range(3):
            request(restored, "/api/hud/activity")
            request(restored, "/api/hud/graph")
        self.assertEqual(restored.outbox.counts(), before_counts)
        self.assertEqual(restored.graph.export_snapshot(), before_graph)
        self.assertEqual(before_counts["pending"], 2)
        self.assertEqual(before_counts["acknowledged"], 0)

    def test_recent_projection_is_bounded_ordered_and_read_only(self):
        for index in range(4):
            self.window.outbox.enqueue(str(index), "test", {"index": index}, now=10)
        before = self.window.outbox.counts()
        recent = self.window.outbox.recent(topics=("test",), limit=2)
        self.assertEqual([record["payload"]["index"] for record in recent], [2, 3])
        self.assertEqual(self.window.outbox.counts(), before)
        for invalid in (0, 5001, True):
            with self.assertRaises(ValueError):
                self.window.outbox.recent(topics=("test",), limit=invalid)


class ResearchWindowPresentationContractTests(unittest.TestCase):
    def test_motion_is_event_gated_pausable_and_respects_reduced_motion(self):
        self.assertIn('body[data-state=active][data-motion=on] .coin', DASHBOARD_HTML)
        self.assertIn('@media(prefers-reduced-motion:reduce)', DASHBOARD_HTML)
        self.assertIn("document.body.dataset.state='disconnected'", DASHBOARD_HTML)
        self.assertIn("motion&&!reduced.matches?'on':'off'", DASHBOARD_HTML)
        self.assertIn("localStorage.setItem('merlin-motion'", DASHBOARD_HTML)
        self.assertNotIn('i<a.phase_index', DASHBOARD_HTML)
        self.assertIn('(a.completed_stages||[]).includes(phase)', DASHBOARD_HTML)

    def test_graphs_are_run_scoped_and_new_artifacts_can_be_followed(self):
        self.assertIn("e.source_id===session&&e.relation==='uses'", DASHBOARD_HTML)
        self.assertIn("$('follow').checked&&newest.node_id!==latestGraph", DASHBOARD_HTML)
        self.assertIn("arrival.event_id!==followedArtifact", DASHBOARD_HTML)
        self.assertIn("n.node_id===arrival.artifact_node_id", DASHBOARD_HTML)
        self.assertIn("const projectionKey=graph.snapshot_sha256+':'+activity.active_run_id", DASHBOARD_HTML)
        self.assertIn('The last received evidence is retained.', DASHBOARD_HTML)
        self.assertNotIn('https://cdn.', DASHBOARD_HTML)
        self.assertNotIn('innerHTML', DASHBOARD_HTML)


if __name__ == '__main__':
    unittest.main()
