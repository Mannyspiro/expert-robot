"""Synthetic reviewed rotation preserves the old segment and unresolved alerts."""
import os
import unittest
from uuid import uuid4

import test_wilborn_security_archive as fixture
from test_wilborn_attested_integration import Signer
from wilborn_ops.security_ledger import SecurityLedger,ANCHOR_CLAIM,anchor_bindings,MAX_HISTORY,EVENT_CLAIM
from wilborn_ops.security_monitor import SecurityEvent
from wilborn_ops.security_recovery import AnchorCustody
from wilborn_ops.security_rotation import CLAIM,stage_rotation,seal_rotation,inspect_rotation

class RotationTests(unittest.TestCase):
    def setUp(self):
        self.a=fixture.ArchiveTests()
        self.addCleanup(self.a.doCleanups)
        self.a.setUp()
        self.f=self.a.f
        self.a.seal(self.a.stage())
        self.sensor=Signer("rotation-sensor")
        self.operator=Signer("rotation-operator")
        self.anchorer=Signer("rotation-anchor")
        self.reviewer=Signer("rotation-reviewer")
        self.new_id=str(uuid4())
        self.new_options=dict(master_key=os.urandom(32),key_id="rotation-fixture-key",
                              sensor_keys=self.sensor.trust,operator_keys=self.operator.trust)
        root=self.a.fixture.root
        custody=root/"rotation-custody"
        custody.mkdir(mode=0o700)
        self.successor=AnchorCustody(custody,ledger_id=self.new_id,trust=self.anchorer.trust,
                          requester_id="fixture-worker",clock=lambda:self.f.now,create=True)
        self.directory=self.a.fixture.restore_dir/"rotation"
        self.options=dict(predecessor=self.a.custody,successor=self.successor,old_options=self.a.options,
            new_options=self.new_options,archive_review_keys=self.a.reviewer.trust,
            reserve_revisions=MAX_HISTORY-3)

    def stage(self,**overrides):
        return stage_rotation(self.f.path,self.a.directory,self.directory,**{**self.options,**overrides})

    def ledger(self):
        return SecurityLedger(self.directory/"successor.sqlite3",ledger_id=self.new_id,
            requester_id="fixture-worker",clock=lambda:self.f.now,**self.new_options)

    def anchor(self):
        report=self.ledger().report()
        b=anchor_bindings(self.new_id,report["revision"],report["state_sha256"])
        self.successor.retain({"bindings":b,"attestation":self.f.sign(self.anchorer,ANCHOR_CLAIM,b,
                                self.f.now,"independent-reproduction")})

    def signature(self,staged,signer=None):
        return self.f.sign(signer or self.reviewer,CLAIM,staged["review_bindings"],self.f.now,
                           "independent-reproduction")

    def seal(self,staged,**overrides):
        return seal_rotation(self.f.path,self.a.directory,self.directory,**{**self.options,
            "rotation_review_keys":self.reviewer.trust,"review_attestation":self.signature(staged),**overrides})

    def inspect(self):
        return inspect_rotation(self.f.path,self.a.directory,self.directory,**self.options,
                                rotation_review_keys=self.reviewer.trust)

    def test_continuity_preserves_full_predecessor_and_pending_alerts(self):
        original=self.f.path.read_bytes()
        archive=(self.a.directory/"history.sqlite3").read_bytes()
        staged=self.stage()
        self.assertEqual(staged["predecessor_unresolved_alerts"],{"integrity_failure":1})
        self.assertFalse(staged["activation_authorized"])
        self.assertEqual(self.ledger().history()["entries"],[])
        self.anchor()
        reviewed=self.seal(staged)
        self.assertEqual(self.inspect(),reviewed)
        self.assertEqual(reviewed["predecessor_events"],2)
        self.assertEqual(reviewed["predecessor_unresolved_alerts"],{"integrity_failure":1})
        self.assertFalse(reviewed["predecessor_alerts_resolved"])
        self.assertFalse(reviewed["activation_authorized"])
        self.assertFalse(reviewed["deletion_authorized"])
        self.assertEqual(self.f.path.read_bytes(),original)
        self.assertEqual((self.a.directory/"history.sqlite3").read_bytes(),archive)
        self.assertNotIn("integrity_failure",(self.directory/"continuity.json").read_text())
        with self.assertRaises(ValueError):
            self.seal(staged)

    def test_explicit_reserve_and_distinct_key_required(self):
        with self.assertRaises(PermissionError):
            self.stage(reserve_revisions=64)
        with self.assertRaises(PermissionError):
            self.stage(new_options=dict(self.new_options,master_key=self.a.options["master_key"]))
        self.assertFalse(self.directory.exists())

    def test_separate_fresh_review_and_genesis_anchor_required(self):
        staged=self.stage()
        with self.assertRaises(PermissionError):
            self.seal(staged)
        self.anchor()
        with self.assertRaises(PermissionError):
            self.seal(staged,rotation_review_keys=self.a.reviewer.trust)
        with self.assertRaises(ValueError):
            self.seal(staged,review_attestation=self.signature(staged,self.sensor))
        self.assertFalse((self.directory/"review.json").exists())

    def test_predecessor_changes_invalidate_staged_archive(self):
        staged=self.stage()
        self.anchor()
        self.f.observe("tool_denied")
        with self.assertRaises(PermissionError):
            self.seal(staged)
        self.assertFalse((self.directory/"review.json").exists())

    def test_successor_changes_and_modified_link_rejected(self):
        staged=self.stage()
        self.anchor()
        link=self.directory/"continuity.json"
        before=link.read_bytes()
        link.write_bytes(b"{}")
        with self.assertRaises((ValueError,PermissionError)):
            self.seal(staged)
        link.write_bytes(before)
        self.ledger().observe_local(SecurityEvent("auth_failure","demo","synthetic"),
                      lambda b,now:self.f.sign(self.sensor,EVENT_CLAIM,b,now,"artifact-integrity"))
        with self.assertRaises(PermissionError):
            self.seal(staged)
