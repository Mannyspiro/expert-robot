"""Verified staged segment views preserve history without granting a handover."""
import json
import unittest
from unittest.mock import patch

import test_wilborn_security_rotation as fixture
from wilborn_ops.security_ledger import EVENT_CLAIM
from wilborn_ops.security_monitor import SecurityEvent
from wilborn_ops.security_rotation import inspect_rotation
from wilborn_ops.security_segments import inspect_staged_segments
from wilborn_ops.security_dashboard import studio_segment_snapshot


class SegmentReviewTests(unittest.TestCase):
    def setUp(self):
        self.r = fixture.RotationTests()
        self.addCleanup(self.r.doCleanups)
        self.r.setUp()

    def prepare(self):
        staged = self.r.stage()
        self.r.anchor()
        self.r.seal(staged)

    def inspect(self, **overrides):
        return inspect_staged_segments(
            self.r.f.path, self.r.a.directory, self.r.directory,
            **{**self.r.options, "rotation_review_keys": self.r.reviewer.trust, **overrides})

    def test_segments_preserve_pending_history_and_source_bytes(self):
        self.prepare()
        paths = [self.r.f.path, self.r.a.directory / "history.sqlite3",
                 self.r.directory / "successor.sqlite3", self.r.directory / "continuity.json",
                 self.r.directory / "review.json"]
        before = {p: p.read_bytes() for p in paths}
        result = self.inspect()
        self.assertEqual(result["schema"], "wilborn-staged-segment-review/1")
        self.assertEqual(result["review_scope"], "staged_rotation")
        old, new = result["segments"]
        self.assertEqual([(x["segment_index"], x["role"]) for x in result["segments"]],
                         [(0, "predecessor_archive"), (1, "successor_genesis")])
        self.assertEqual(old["ledger_id"], self.r.f.options["ledger_id"])
        self.assertEqual(new["ledger_id"], self.r.new_id)
        self.assertNotEqual(old["ledger_id"], new["ledger_id"])
        self.assertEqual(old["revision"], 3)
        self.assertEqual(new["revision"], 1)
        self.assertEqual(old["history_entries_verified"], 2)
        self.assertEqual(new["history_entries_verified"], 0)
        self.assertEqual(new["accepted_events"], 0)
        self.assertEqual(new["pending_alerts"], {})
        self.assertTrue(all(x["external_anchor_verified"] for x in result["segments"]))
        self.assertEqual(result["accepted_events"], 2)
        self.assertEqual(result["operator_reviews"], 0)
        self.assertEqual(result["pending_alerts"], {"integrity_failure": 1})
        self.assertEqual(old["pending_alerts"], result["pending_alerts"])
        self.assertEqual([(e["segment_index"], e["revision"], e["kind"])
                          for e in result["recent_incidents"]],
                         [(0, 2, "auth_failure"), (0, 3, "integrity_failure")])
        for key in ("writer_handover_verified", "active_history_verified",
                    "activation_authorized", "execution_authorized", "deletion_authorized",
                    "production_qualified", "predecessor_alerts_resolved", "history_reconstructed"):
            self.assertIs(result[key], False)
        text = json.dumps(result, sort_keys=True)
        for secret_or_identity in ("fixture-sensor", "fixture-operator", "rotation-reviewer",
                                   self.r.new_options["master_key"].hex(),
                                   self.r.a.options["master_key"].hex()):
            self.assertNotIn(secret_or_identity, text)
        self.assertEqual({p: p.read_bytes() for p in paths}, before)
        self.assertEqual(self.inspect(), result)

    def test_complete_verification_with_bounded_or_hidden_history(self):
        for _ in range(25):
            self.r.f.observe("tool_denied")
        self.r.a.custody.retain(self.r.f.anchor())
        self.r.a.directory = self.r.a.fixture.restore_dir / "archive-many"
        self.r.a.seal(self.r.a.stage())
        self.prepare()
        result = self.inspect()
        self.assertEqual(result["history_entries_verified"], 27)
        self.assertEqual(result["history_entries_displayed"], 20)
        self.assertTrue(result["history_display_truncated"])
        self.assertEqual(result["recent_incidents"][0]["revision"], 9)
        self.assertEqual(result["recent_incidents"][-1]["revision"], 28)
        self.assertEqual(result["pending_alerts"],
                         {"integrity_failure": 1, "tool_policy_denial_burst": 1})
        hidden = self.inspect(history_limit=0)
        self.assertEqual(hidden["recent_incidents"], [])
        self.assertEqual(hidden["history_entries_verified"], 27)
        self.assertEqual(hidden["history_entries_displayed"], 0)
        with (self.r.a.directory / "history.sqlite3").open("ab") as stream:
            stream.write(b"tampered encrypted archive")
        with self.assertRaises((PermissionError, ValueError)):
            self.inspect(history_limit=0)

    def test_history_limit_validated_before_crypto_or_storage(self):
        for value in (-1, 21, True, False, 1.0, "20", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.inspect(history_limit=value)
        self.assertFalse(self.r.directory.exists())

    def test_unsigned_modified_and_reordered_rotations_rejected(self):
        staged = self.r.stage()
        self.r.anchor()
        with self.assertRaises(ValueError):
            self.inspect()
        self.r.seal(staged)
        with self.assertRaises(PermissionError):
            self.inspect(successor=self.r.a.custody)
        with self.assertRaises((PermissionError, ValueError)):
            self.inspect(predecessor=self.r.successor, successor=self.r.a.custody,
                         old_options=self.r.new_options, new_options=self.r.a.options)
        path = self.r.directory / "continuity.json"
        path.write_bytes(b"{}")
        with self.assertRaises((PermissionError, ValueError)):
            self.inspect()

    def test_predecessor_advancement_rejected(self):
        self.prepare()
        self.r.f.observe("tool_denied")
        self.r.a.custody.retain(self.r.f.anchor())
        with self.assertRaises(PermissionError):
            self.inspect()

    def test_successor_activation_and_stale_custody_rejected(self):
        self.prepare()
        self.r.f.now += 86401
        with self.assertRaises(PermissionError):
            self.inspect()
        self.r.f.now -= 86401
        self.r.ledger().observe_local(
            SecurityEvent("auth_failure", "demo", "synthetic"),
            lambda b, now: self.r.f.sign(self.r.sensor, EVENT_CLAIM, b, now,
                                       "artifact-integrity"))
        with self.assertRaises(PermissionError):
            self.inspect()

    def test_change_between_verification_passes_rejected(self):
        self.prepare()
        calls = []

        def changing(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                self.r.f.observe("tool_denied")
                self.r.a.custody.retain(self.r.f.anchor())
            return inspect_rotation(*args, **kwargs)

        with patch("wilborn_ops.security_segments.inspect_rotation", side_effect=changing):
            with self.assertRaises(PermissionError):
                self.inspect()
        self.assertEqual(len(calls), 2)

    def export(self, **overrides):
        return studio_segment_snapshot(
            self.r.f.path, self.r.a.directory, self.r.directory,
            **{**self.r.options, "rotation_review_keys": self.r.reviewer.trust, **overrides})

    def test_studio_export_is_exact_minimized_v2_without_host_identities(self):
        self.prepare()
        result = self.export()
        self.assertEqual(set(result), {
            "schema", "environment", "data_class", "execution_authorized",
            "production_qualified", "activation_authorized", "writer_handover_verified",
            "review_scope", "accepted_events", "operator_reviews", "counts",
            "pending_alerts", "segments", "recent_incidents"})
        self.assertEqual(result["schema"], "merlin-studio-security-summary/2")
        fields = {"segment_index", "role", "revision", "accepted_events",
                  "operator_reviews", "counts", "pending_alerts", "active_correlations",
                  "external_anchor_revision", "external_anchor_verified"}
        for segment in result["segments"]:
            self.assertEqual(set(segment), fields)
            self.assertEqual(segment["external_anchor_revision"], segment["revision"])
            self.assertIs(segment["external_anchor_verified"], True)
        for entry in result["recent_incidents"]:
            self.assertEqual(set(entry), {"segment_index", "revision", "type", "kind"})
        text = json.dumps(result, sort_keys=True)
        for private_value in (self.r.f.options["ledger_id"], self.r.new_id,
                              self.r.new_options["master_key"].hex(),
                              self.r.a.options["master_key"].hex(),
                              "ledger_id", "sha256", "attestation", "signature",
                              "fixture-sensor", "rotation-anchor", "received_at_utc"):
            self.assertNotIn(private_value, text)
        self.assertEqual(result["pending_alerts"], {"integrity_failure": 1})
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["writer_handover_verified"])

    def test_studio_export_requires_real_verification_and_fixed_history_window(self):
        self.prepare()
        with self.assertRaises(ValueError):
            self.export(history_limit=0)
        with (self.r.a.directory / "history.sqlite3").open("ab") as stream:
            stream.write(b"tampered archive cannot be exported")
        with self.assertRaises((PermissionError, ValueError)):
            self.export()


if __name__ == "__main__":
    unittest.main()
