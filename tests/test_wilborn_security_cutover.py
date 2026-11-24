"""Staged cutover preserves legacy evidence without activating a new writer."""
import os
import unittest
from pathlib import Path
from uuid import uuid4

import test_wilborn_legacy_migration as legacy_fixture
from test_wilborn_attested_integration import Signer
from wilborn_ops.security_recovery import AnchorCustody
from wilborn_ops.security_cutover import CLAIM,stage_cutover,verify_staged_cutover
from wilborn_ops.security_ledger import SecurityLedger,ANCHOR_CLAIM,anchor_bindings

class CutoverTests(unittest.TestCase):
    def setUp(self):
        self.fixture=legacy_fixture.LegacyTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.f=self.fixture.f
        self.old=self.fixture.test.custody
        self.old.retain(self.fixture.write_legacy(self.fixture.state))
        self.old_options=self.fixture.test.options
        self.sensor=Signer("successor-sensor")
        self.operator=Signer("successor-operator")
        self.anchor=Signer("successor-custodian")
        self.reviewer=Signer("cutover-reviewer")
        self.new_options={"master_key":os.urandom(32),"key_id":"successor-fixture-key",
                          "sensor_keys":self.sensor.trust,"operator_keys":self.operator.trust}
        self.new_id=str(uuid4())
        root=self.fixture.test.root
        custody=root/"successor-custody"
        custody.mkdir(mode=0o700)
        self.new=AnchorCustody(custody,ledger_id=self.new_id,trust=self.anchor.trust,
                               requester_id="fixture-worker",clock=lambda:self.f.now,create=True)
        self.stage=root/"staged-cutover"
        self.options=dict(legacy=self.old,successor=self.new,old_options=self.old_options,
                          new_options=self.new_options)

    def prepare(self):
        return stage_cutover(self.fixture.path,self.stage,**self.options)

    def successor_ledger(self):
        return SecurityLedger(self.stage/"successor.sqlite3",ledger_id=self.new_id,
                   requester_id="fixture-worker",clock=lambda:self.f.now,**self.new_options)

    def anchor_genesis(self):
        report=self.successor_ledger().report()
        b=anchor_bindings(self.new_id,report["revision"],report["state_sha256"])
        self.new.retain({"bindings":b,"attestation":self.f.sign(self.anchor,ANCHOR_CLAIM,b,
                        self.f.now,"independent-reproduction")})

    def review(self,b,signer=None):
        return self.f.sign(signer or self.reviewer,CLAIM,b,self.f.now,"independent-reproduction")

    def verify(self,prepared,**overrides):
        binding=prepared["review_bindings"]
        return verify_staged_cutover(self.stage,**self.options,**{
              "reviewer_keys":self.reviewer.trust,"review_attestation":self.review(binding),
              **overrides})

    def test_preserve_old_bytes_and_review_new_empty_ledger(self):
        before=self.fixture.path.read_bytes()
        prepared=self.prepare()
        self.assertFalse(prepared["activation_authorized"])
        self.assertEqual((self.stage/"legacy.sqlite3").read_bytes(),before)
        self.assertEqual(self.fixture.path.read_bytes(),before)
        self.assertEqual(self.successor_ledger().history()["entries"],[])
        self.anchor_genesis()
        result=self.verify(prepared)
        self.assertTrue(result["legacy_archive_verified"])
        self.assertTrue(result["successor_genesis_verified"])
        self.assertEqual(result["historical_incidents_reconstructed"],0)
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["activation_authorized"])
        self.assertFalse(result["production_qualified"])
        self.assertNotIn("integrity_failure",(self.stage/"link.json").read_text())
        self.assertEqual(self.fixture.path.read_bytes(),before)
        with self.assertRaises(FileExistsError):
            self.prepare()

    def test_genesis_anchor_and_separate_review_required(self):
        prepared=self.prepare()
        with self.assertRaises(PermissionError):
            self.verify(prepared)
        self.anchor_genesis()
        with self.assertRaises(ValueError):
            self.verify(prepared,review_attestation=self.review(prepared["review_bindings"],self.sensor))
        with self.assertRaises(PermissionError):
            self.verify(prepared,reviewer_keys=self.anchor.trust)
        changed=dict(prepared["review_bindings"],activation_authorized=True)
        with self.assertRaises((ValueError,PermissionError)):
            self.verify(prepared,review_attestation=self.review(changed))

    def test_tampered_link_or_archive_rejected(self):
        prepared=self.prepare()
        self.anchor_genesis()
        link=self.stage/"link.json"
        saved=link.read_bytes()
        link.write_bytes(b"{}")
        with self.assertRaises((ValueError,PermissionError)):
            self.verify(prepared)
        link.write_bytes(saved)
        archive=self.stage/"legacy.sqlite3"
        # Appending bytes leaves the logical checkpoint unchanged but changes
        # the exact archived artifact identity.
        with archive.open("ab") as stream:
            stream.write(b"synthetic modification")
        with self.assertRaises((ValueError,PermissionError)):
            self.verify(prepared)

    def test_successor_non_genesis_and_reused_key_rejected(self):
        with self.assertRaises(PermissionError):
            stage_cutover(self.fixture.path,self.stage,**{**self.options,"new_options":dict(
                self.new_options,master_key=self.old_options["master_key"])})
        self.assertFalse(self.stage.exists())
        prepared=self.prepare()
        self.anchor_genesis()
        from wilborn_ops.security_monitor import SecurityEvent
        from wilborn_ops.security_ledger import EVENT_CLAIM
        self.successor_ledger().observe_local(SecurityEvent("auth_failure","demo","synthetic"),
            lambda b,now:self.f.sign(self.sensor,EVENT_CLAIM,b,now,"artifact-integrity"))
        with self.assertRaises(PermissionError):
            self.verify(prepared)
