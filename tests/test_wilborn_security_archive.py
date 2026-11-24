"""Reviewed archival is historical evidence, not active recovery permission."""
import os
import unittest
from pathlib import Path

import test_wilborn_security_recovery as recovery
from test_wilborn_attested_integration import Signer
from wilborn_ops.security_archive import (
    ARCHIVE_CLAIM,retention_status,stage_archive,seal_archive,inspect_archive)
from wilborn_ops.security_ledger import MAX_HISTORY

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.fixture=recovery.RecoveryTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.f=self.fixture.f
        self.reviewer=Signer("fixture-archive-reviewer")
        self.custody=self.fixture.custody
        self.options=self.fixture.options
        self.directory=self.fixture.restore_dir/"archive"
        self.f.observe("auth_failure")
        self.f.observe("integrity_failure")
        self.custody.retain(self.f.anchor())

    def stage(self):
        return stage_archive(self.f.path,self.directory,custody=self.custody,options=self.options)

    def signature(self,binding,signer=None):
        return self.f.sign(signer or self.reviewer,ARCHIVE_CLAIM,binding,self.f.now,"independent-reproduction")

    def seal(self,staged,**kw):
        return seal_archive(self.directory,custody=self.custody,options=self.options,**{
            "reviewer_keys":self.reviewer.trust,
            "review_attestation":self.signature(staged["review_bindings"]),**kw})

    def inspect(self,**kw):
        return inspect_archive(self.directory,custody=self.custody,
            options=self.options,**{"reviewer_keys":self.reviewer.trust,**kw})

    def test_reviewed_archive_stays_inspectable_after_expiration(self):
        original=self.f.path.read_bytes()
        staged=self.stage()
        with self.assertRaises(ValueError):
            self.inspect()
        result=self.seal(staged)
        saved=(self.directory/"history.sqlite3").read_bytes()
        self.assertTrue(result["encrypted_history_verified"])
        self.assertFalse(result["current_recovery_authorized"])
        self.assertFalse(result["deletion_authorized"])
        self.assertFalse(result["activation_authorized"])
        self.assertEqual(self.f.path.read_bytes(),original)
        self.assertNotIn(b"integrity_failure",saved)
        self.f.now+=86401
        with self.assertRaises(PermissionError):
            self.custody.latest()
        self.assertEqual(self.inspect(),result)
        self.assertEqual((self.directory/"history.sqlite3").read_bytes(),saved)
        self.assertEqual(self.f.path.read_bytes(),original)
        with self.assertRaises(PermissionError):
            self.custody.open_ledger(self.directory/"history.sqlite3",**self.options)

    def test_review_is_independent_and_no_clobber(self):
        staged=self.stage()
        with self.assertRaises(PermissionError):
            self.seal(staged,reviewer_keys=self.f.sensor.trust)
        with self.assertRaises(ValueError):
            self.seal(staged,review_attestation=self.signature(staged["review_bindings"],self.f.sensor))
        self.assertFalse((self.directory/"review.json").exists())
        result=self.seal(staged)
        with self.assertRaises(ValueError):
            self.seal(staged)
        with self.assertRaises(FileExistsError):
            self.stage()
        self.assertEqual(self.inspect(),result)

    def test_changed_archive_and_receipts_rejected(self):
        staged=self.stage()
        self.seal(staged)
        for name in ("anchor.json","review.json"):
            p=self.directory/name
            before=p.read_bytes()
            p.write_bytes(b"{}")
            with self.assertRaises((ValueError,PermissionError,KeyError)):
                self.inspect()
            p.write_bytes(before)
        with (self.directory/"history.sqlite3").open("ab") as stream:
            stream.write(b"fixture archive byte change")
        with self.assertRaises((ValueError,PermissionError)):
            self.inspect()

    def test_fresh_tip_required_for_review(self):
        staged=self.stage()
        self.f.observe("tool_denied")
        self.custody.retain(self.f.anchor())
        with self.assertRaises(PermissionError):
            self.seal(staged)
        self.assertFalse((self.directory/"review.json").exists())

    def test_explicit_retention_reserve_only_advisory(self):
        r=retention_status(self.f.ledger,reserve_revisions=64)
        self.assertEqual(r["remaining_revisions"],MAX_HISTORY-3)
        self.assertFalse(r["archive_review_due"])
        self.assertFalse(r["deletion_authorized"])
        self.assertTrue(retention_status(self.f.ledger,reserve_revisions=MAX_HISTORY-3)["archive_review_due"])
        for reserve in (0,True,MAX_HISTORY):
            with self.assertRaises(ValueError):
                retention_status(self.f.ledger,reserve_revisions=reserve)
