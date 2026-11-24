"""Active lineage review uses real configured cryptographic/storage fixtures."""
import json
import sqlite3
import unittest
from uuid import uuid4

import test_wilborn_security_handover as fixture
import test_wilborn_security_generations_adversarial as generation_fixture
from wilborn_ops.security_handover import WriterHandover
from wilborn_ops.security_dashboard import studio_lineage_snapshot
from wilborn_ops.security_lineage import inspect_active_lineage
from wilborn_ops.security_ledger import REVIEW_CLAIM,review_bindings


class LineageReviewTests(unittest.TestCase):
    def setUp(self):
        self.x=fixture.HandoverTests()
        self.addCleanup(self.x.doCleanups)
        self.x.setUp()

    def activate(self,*kinds):
        self.lease=self.x.activate()
        self.writer=self.x.control.open_writer(self.lease)
        for kind in kinds:
            self.x.observe(self.writer,kind)
        return self.x.control

    def three_segments(self,label):
        g=generation_fixture.GenerationAdversarialTests()
        self.addCleanup(g.doCleanups)
        g.setUp()
        g.x.observe(g.writer_b,"auth_failure")
        g.x.observe(g.writer_b,"integrity_failure")
        child=g.child(label)
        lease=g.activate(child)
        writer=child["control"].open_writer(lease)
        g.observe_child(child,writer)
        g.observe_child(child,writer)
        return g,child,writer

    def test_actual_active_lineage_preserves_each_segment_and_pending_alerts(self):
        control=self.activate("auth_failure","integrity_failure")
        paths=[self.x.f.path,self.x.r.directory/"successor.sqlite3",
               self.x.r.a.directory/"history.sqlite3",control._path,
               self.x.r.directory/"continuity.json",self.x.r.directory/"review.json"]
        before={p:p.read_bytes() for p in paths}
        result=inspect_active_lineage(control)
        self.assertEqual(result["schema"],"wilborn-active-lineage-review/1")
        self.assertEqual(result["review_scope"],"active_lineage")
        self.assertEqual(result["ownership_epoch"],1)
        self.assertEqual(result["active_segment_index"],1)
        self.assertEqual([(s["segment_index"],s["role"]) for s in result["segments"]],
                         [(0,"archived_predecessor"),(1,"active_successor")])
        self.assertEqual([s["revision"] for s in result["segments"]],[3,3])
        self.assertEqual([s["external_anchor_revision"] for s in result["segments"]],[3,1])
        self.assertEqual(result["accepted_events"],4)
        self.assertEqual(result["operator_reviews"],0)
        self.assertEqual(result["counts"],{"auth_failure":2,"integrity_failure":2})
        self.assertEqual(result["pending_alerts"],{"integrity_failure":2})
        self.assertEqual([s["pending_alerts"] for s in result["segments"]],
                         [{"integrity_failure":1},{"integrity_failure":1}])
        self.assertEqual([(e["segment_index"],e["revision"]) for e in result["recent_incidents"]],
                         [(0,2),(0,3),(1,2),(1,3)])
        self.assertEqual(result["history_entries_verified"],4)
        self.assertTrue(result["writer_handover_verified"])
        self.assertTrue(result["active_history_verified"])
        for key in ("activation_authorized","deletion_authorized","execution_authorized",
                    "production_qualified","predecessor_alerts_resolved","history_reconstructed"):
            self.assertIs(result[key],False)
        self.assertEqual({p:p.read_bytes() for p in paths},before)

    def test_reopened_ownership_epoch_is_reflected_without_changing_history(self):
        control=self.activate("tool_denied")
        before=inspect_active_lineage(control)
        current=self.x.reopen().claim_writer(expected_epoch=1,owner_id=str(uuid4()))
        result=inspect_active_lineage(self.x.reopen())
        self.assertEqual(result["ownership_epoch"],current.epoch)
        self.assertEqual(result["ownership_epoch"],2)
        self.assertEqual(result["segments"],before["segments"])
        self.assertEqual(result["recent_incidents"],before["recent_incidents"])

    def test_successor_operator_review_does_not_clear_predecessor_alerts(self):
        control=self.activate("integrity_failure")
        report=self.writer.report()
        binding=review_bindings(self.writer._id,report["revision"],report["state_sha256"])
        signed=self.x.f.sign(self.x.r.operator,REVIEW_CLAIM,binding,self.x.f.now,
                             "independent-reproduction")
        self.writer.acknowledge(binding,signed)
        result=inspect_active_lineage(control)
        self.assertEqual(result["accepted_events"],3)
        self.assertEqual(result["operator_reviews"],1)
        self.assertEqual(result["pending_alerts"],{"integrity_failure":1})
        self.assertEqual(result["segments"][0]["pending_alerts"],{"integrity_failure":1})
        self.assertEqual(result["segments"][1]["pending_alerts"],{})
        self.assertEqual(result["recent_incidents"][-1],{
            "segment_index":1,"ledger_id":self.writer._id,"revision":3,"type":"operator_review"})
        self.assertFalse(result["predecessor_alerts_resolved"])

    def test_actual_three_segment_lineage_preserves_both_frozen_predecessors(self):
        g,child,writer=self.three_segments("lineage-three")
        result=inspect_active_lineage(child["control"])
        self.assertEqual(result["active_segment_index"],2)
        self.assertEqual([s["role"] for s in result["segments"]],
                         ["archived_predecessor","archived_predecessor","active_successor"])
        self.assertEqual([s["revision"] for s in result["segments"]],[3,3,3])
        self.assertEqual([s["external_anchor_revision"] for s in result["segments"]],[3,3,1])
        self.assertEqual(result["accepted_events"],6)
        self.assertEqual(result["counts"],{"auth_failure":2,"integrity_failure":4})
        self.assertEqual(result["pending_alerts"],{"integrity_failure":4})
        self.assertEqual([s["pending_alerts"] for s in result["segments"]],
                         [{"integrity_failure":1},{"integrity_failure":1},{"integrity_failure":2}])
        self.assertEqual([(e["segment_index"],e["revision"]) for e in result["recent_incidents"]],
                         [(0,2),(0,3),(1,2),(1,3),(2,2),(2,3)])
        snapshot=studio_lineage_snapshot(child["control"])
        self.assertEqual(snapshot["accepted_events"],6)
        self.assertEqual(snapshot["pending_alerts"],result["pending_alerts"])
        with self.assertRaises(PermissionError):
            inspect_active_lineage(g.x.control)

    def test_omitted_reordered_or_damaged_ancestor_cannot_export_active_lineage(self):
        g,child,writer=self.three_segments("lineage-ancestry")
        for previous in (None,child["control"]):
            with self.subTest(previous=previous),self.assertRaises((PermissionError,ValueError)):
                changed=WriterHandover(child["directory"],**{**child["kwargs"],"previous":previous})
                studio_lineage_snapshot(changed)
        proof=g.x.r.directory/"review.json"
        original=proof.read_bytes()
        proof.write_bytes(b"{}")
        with self.assertRaises((PermissionError,ValueError)):
            inspect_active_lineage(child["control"],history_limit=0)
        with self.assertRaises((PermissionError,ValueError)):
            studio_lineage_snapshot(child["control"])
        proof.write_bytes(original)
        self.assertEqual(inspect_active_lineage(child["control"])["accepted_events"],6)

    def test_entire_history_verified_before_display_window_or_zero_limit(self):
        control=self.activate(*(["tool_denied"]*25))
        result=inspect_active_lineage(control)
        self.assertEqual(result["history_entries_verified"],27)
        self.assertEqual(result["history_entries_displayed"],20)
        self.assertTrue(result["history_display_truncated"])
        self.assertEqual([(e["segment_index"],e["revision"]) for e in result["recent_incidents"]],
                         [(1,r) for r in range(7,27)])
        hidden=inspect_active_lineage(control,history_limit=0)
        self.assertEqual(hidden["history_entries_verified"],27)
        self.assertEqual(hidden["recent_incidents"],[])
        with sqlite3.connect(self.writer._path) as db:
            db.execute("DELETE FROM history WHERE revision=2")
        with self.assertRaises((PermissionError,ValueError,RuntimeError)):
            inspect_active_lineage(control,history_limit=0)

    def test_archived_history_cannot_hide_behind_display_truncation(self):
        control=self.activate(*(["tool_denied"]*25))
        with (self.x.r.a.directory/"history.sqlite3").open("ab") as stream:
            stream.write(b"tampered archived predecessor")
        with self.assertRaises((PermissionError,ValueError,RuntimeError)):
            inspect_active_lineage(control,history_limit=0)
        with self.assertRaises((PermissionError,ValueError,RuntimeError)):
            studio_lineage_snapshot(control)

    def test_current_custody_required_for_host_report(self):
        control=self.activate("tool_denied")
        self.x.f.now+=86401
        with self.assertRaises(PermissionError):
            inspect_active_lineage(control)
        self.x.r.a.custody.retain(self.x.f.anchor())
        with self.assertRaises(PermissionError):
            inspect_active_lineage(control)
        self.x.r.anchor()
        self.assertEqual(inspect_active_lineage(control)["accepted_events"],3)

    def test_studio_export_is_exact_minimized_v3(self):
        control=self.activate("auth_failure","integrity_failure")
        result=studio_lineage_snapshot(control)
        self.assertEqual(set(result),{"schema","environment","data_class","execution_authorized",
            "production_qualified","activation_authorized","writer_handover_verified",
            "review_scope","ownership_epoch","active_segment_index","accepted_events",
            "operator_reviews","counts","pending_alerts","segments","recent_incidents"})
        self.assertEqual(result["schema"],"merlin-studio-security-summary/3")
        fields={"segment_index","role","revision","accepted_events","operator_reviews",
            "counts","pending_alerts","active_correlations","external_anchor_revision",
            "external_anchor_verified"}
        self.assertTrue(all(set(s)==fields for s in result["segments"]))
        self.assertTrue(result["writer_handover_verified"])
        self.assertFalse(result["activation_authorized"])
        text=json.dumps(result,sort_keys=True)
        for private in (self.x.f.options["ledger_id"],self.x.r.new_id,self.x.control._id,
                        self.x.r.new_options["master_key"].hex(),self.x.r.a.options["master_key"].hex(),
                        "ledger_id","sha256","attestation","signature","received_at_utc",
                        "fixture-sensor","rotation-anchor","handover-reviewer"):
            self.assertNotIn(private,text)

    def test_invalid_limits_untrusted_reports_and_inactive_handover_rejected(self):
        for limit in (-1,21,True,False,1.0,"20",None):
            with self.subTest(limit=limit),self.assertRaises(ValueError):
                inspect_active_lineage(self.x.control,history_limit=limit)
        with self.assertRaises(TypeError):
            inspect_active_lineage({"writer_handover_verified":True})
        with self.assertRaises(ValueError):
            studio_lineage_snapshot(self.x.control,history_limit=0)
        with self.assertRaises(PermissionError):
            inspect_active_lineage(self.x.control)
        self.x.control.prepare()
        with self.assertRaises(PermissionError):
            inspect_active_lineage(self.x.control)


if __name__=="__main__":
    unittest.main()
