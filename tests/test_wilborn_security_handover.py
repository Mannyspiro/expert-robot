"""Real cryptography and SQLite with synthetic event/owner fixtures only."""
from dataclasses import replace
import sqlite3
import unittest
from unittest.mock import patch
from uuid import uuid4

from test_wilborn_attested_integration import Signer
import test_wilborn_security_rotation as fixtures
from wilborn_ops.security_handover import WriterHandover,WriterLease,CLAIM
from wilborn_ops.security_ledger import EVENT_CLAIM,REVIEW_CLAIM,event_bindings,review_bindings
from wilborn_ops.security_monitor import SecurityEvent


class HandoverTests(unittest.TestCase):
    def setUp(self):
        self.r=fixtures.RotationTests()
        self.addCleanup(self.r.doCleanups)
        self.r.setUp()
        self.f=self.r.f
        staged=self.r.stage()
        self.r.anchor()
        self.r.seal(staged)
        self.reviewer=Signer("handover-reviewer")
        self.directory=self.r.a.fixture.root/"writer-control"
        self.directory.mkdir(mode=0o700)
        self.kwargs=dict(handover_id=str(uuid4()),source=self.f.path,archive=self.r.a.directory,
            stage=self.r.directory,**self.r.options,rotation_review_keys=self.r.reviewer.trust,
            handover_review_keys=self.reviewer.trust)
        self.control=WriterHandover(self.directory,**self.kwargs,create=True,owner_id=str(uuid4()))

    def reopen(self):
        return WriterHandover(self.directory,**self.kwargs)

    def grant(self):
        binding=self.control.prepare()
        return self.f.sign(self.reviewer,CLAIM,binding,self.f.now,"independent-reproduction")

    def activate(self):
        return self.control.activate(self.grant())

    def observe(self,ledger,kind="tool_denied"):
        return ledger.observe_local(SecurityEvent(kind,"demo","synthetic"),
            lambda b,now:self.f.sign(self.r.sensor,EVENT_CLAIM,b,now,"artifact-integrity"))

    def test_separate_review_and_durable_restart_preserve_evidence(self):
        archive=(self.r.a.directory/"history.sqlite3").read_bytes()
        before=self.f.ledger.review_snapshot()
        grant=self.grant()
        self.assertEqual(self.control.status()["phase"],"ready")
        with self.assertRaises(PermissionError):
            self.observe(self.r.ledger())
        lease=self.control.activate(grant)
        writer=self.control.open_writer(lease)
        self.assertEqual(self.observe(writer)["revision"],2)
        recovered=self.reopen()
        next_lease=recovered.claim_writer(expected_epoch=1,owner_id=str(uuid4()))
        self.assertEqual(next_lease.epoch,2)
        self.assertEqual(self.observe(recovered.open_writer(next_lease))["revision"],3)
        with self.assertRaises(PermissionError):
            self.observe(writer)
        # An activation retry is not an authority upgrade for the first owner.
        self.assertEqual(recovered.activate(grant),lease)
        with self.assertRaises(PermissionError):
            recovered.open_writer(recovered.activate(grant))
        result=recovered.status()
        self.assertTrue(result["local_writer_handover_verified"])
        self.assertEqual(result["predecessor_unresolved_alerts"],{"integrity_failure":1})
        self.assertFalse(result["predecessor_alerts_resolved"])
        self.assertFalse(result["production_qualified"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["deployment_authorized"])
        self.assertEqual(self.f.ledger.review_snapshot(),before)
        self.assertEqual((self.r.a.directory/"history.sqlite3").read_bytes(),archive)

    def test_all_write_paths_fenced_on_old_and_unleased_new_objects(self):
        old=self.f.ledger
        new=self.r.ledger()
        self.activate()
        for ledger,signer in ((old,self.f.sensor),(new,self.r.sensor)):
            report=ledger.report()
            eb=event_bindings(ledger._id,report["accepted_events"]+1,"tool_denied")
            ea=self.f.sign(signer,EVENT_CLAIM,eb,self.f.now,"artifact-integrity")
            rb=review_bindings(ledger._id,report["revision"],report["state_sha256"])
            op=self.f.operator if ledger is old else self.r.operator
            ra=self.f.sign(op,REVIEW_CLAIM,rb,self.f.now,"independent-reproduction")
            for call in (lambda:ledger.ingest(eb,ea),lambda:ledger.acknowledge(rb,ra),
                         lambda:ledger.observe_local(SecurityEvent("tool_denied","demo","synthetic"),
                                                     lambda *_:self.fail("fenced signer invoked"))):
                with self.subTest(ledger=ledger._id,call=call),self.assertRaises(PermissionError):
                    call()
            self.assertEqual(ledger.report(),report)

    def test_interrupt_after_each_freeze_resumes_same_intent(self):
        original=self.control._freeze
        def stop_after_successor(role):
            original(role)
            if role=="successor":
                raise InterruptedError("simulated process boundary")
        with patch.object(self.control,"_freeze",side_effect=stop_after_successor):
            with self.assertRaises(InterruptedError):
                self.control.prepare()
        self.assertEqual(self.reopen().status()["phase"],"preparing")
        with self.assertRaises(PermissionError):
            self.observe(self.r.ledger())
        def stop_after_predecessor(role):
            original(role)
            if role=="predecessor":
                raise InterruptedError("simulated process boundary")
        with patch.object(self.control,"_freeze",side_effect=stop_after_predecessor):
            with self.assertRaises(InterruptedError):
                self.control.prepare()
        with self.assertRaises(PermissionError):
            self.f.observe("tool_denied")
        ready=self.reopen().prepare()
        self.assertEqual(ready,self.control.prepare())
        grant=self.f.sign(self.reviewer,CLAIM,ready,self.f.now,"independent-reproduction")
        self.assertEqual(self.observe(self.reopen().open_writer(self.control.activate(grant)))["revision"],2)

    def test_predecessor_advancing_before_freeze_keeps_both_closed(self):
        self.f.observe("tool_denied")
        with self.assertRaises(PermissionError):
            self.control.prepare()
        self.assertEqual(self.control.status()["phase"],"preparing")
        for ledger in (self.f.ledger,self.r.ledger()):
            with self.assertRaises(PermissionError):
                self.observe(ledger)
        with self.assertRaises(PermissionError):
            self.reopen().prepare()

    def test_wrong_expired_or_rotation_grant_cannot_activate(self):
        binding=self.control.prepare()
        bad=self.f.sign(self.r.reviewer,CLAIM,binding,self.f.now,"independent-reproduction")
        with self.assertRaises((ValueError,PermissionError)):
            self.control.activate(bad)
        import json
        with self.assertRaises((ValueError,PermissionError)):
            self.control.activate(json.loads((self.r.directory/"review.json").read_bytes()))
        stale=self.f.sign(self.reviewer,CLAIM,binding,self.f.now-86401,"independent-reproduction")
        with self.assertRaises((ValueError,PermissionError)):
            self.control.activate(stale)
        different=dict(binding,owner_id=str(uuid4()))
        with self.assertRaises((ValueError,PermissionError)):
            self.control.activate(self.f.sign(self.reviewer,CLAIM,different,self.f.now,"independent-reproduction"))
        self.assertEqual(self.control.status()["phase"],"ready")

    def test_failed_signer_and_failed_commit_preserve_sequence(self):
        writer=self.control.open_writer(self.activate())
        before=writer.report()
        with self.assertRaises(RuntimeError):
            writer.observe_local(SecurityEvent("tool_denied","demo","synthetic"),
                                 lambda *_:(_ for _ in ()).throw(RuntimeError("signer unavailable")))
        original=writer._save
        def fail_after_save(db,state,**kwargs):
            original(db,state,**kwargs)
            raise InterruptedError("before ledger transaction commit")
        with patch.object(writer,"_save",side_effect=fail_after_save):
            with self.assertRaises(InterruptedError):
                self.observe(writer)
        self.assertEqual(writer.report(),before)
        self.assertEqual(self.observe(writer)["accepted_events"],1)

    def test_claim_compare_and_swap_and_token_validation(self):
        lease=self.activate()
        for candidate in (None,replace(lease,epoch=2),replace(lease,owner_id=str(uuid4()))):
            with self.assertRaises(PermissionError):
                self.control.open_writer(candidate)
        next_lease=self.reopen().claim_writer(expected_epoch=1,owner_id=str(uuid4()))
        with self.assertRaises(PermissionError):
            self.control.claim_writer(expected_epoch=1,owner_id=str(uuid4()))
        with self.assertRaises(ValueError):
            self.control.claim_writer(expected_epoch=True,owner_id=str(uuid4()))
        self.assertEqual(self.reopen().status()["epoch"],2)
        self.assertEqual(self.observe(self.control.open_writer(next_lease))["accepted_events"],1)

    def test_current_custody_and_untampered_archive_required_on_restart(self):
        self.activate()
        with sqlite3.connect(self.r.a.directory/"history.sqlite3") as db:
            db.execute("DELETE FROM history WHERE revision=2")
        with self.assertRaises((PermissionError,ValueError,RuntimeError)):
            self.reopen().claim_writer(expected_epoch=1,owner_id=str(uuid4()))


if __name__=="__main__":
    unittest.main()
