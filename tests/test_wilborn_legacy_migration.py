"""Legacy checkpoints have aggregate evidence only, not reconstructed incidents."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import sqlite3
import unittest
from contextlib import closing

import test_wilborn_security_recovery as recovery
from python.merlin.artifact_ref import ArtifactRef
from wilborn_ops.attestation_boundary import canonical,digest
from wilborn_ops.security_ledger import LEGACY_SCHEMA,ANCHOR_CLAIM,anchor_bindings
from wilborn_ops.security_recovery import inspect_legacy_checkpoint
from wilborn_ops.titan_envelope import seal_demo

class LegacyTests(unittest.TestCase):
    def setUp(self):
        self.test=recovery.RecoveryTests()
        self.addCleanup(self.test.doCleanups)
        self.test.setUp()
        self.f=self.test.f
        self.path=self.test.root/"legacy.sqlite3"
        self.f.observe("auth_failure")
        self.f.observe("integrity_failure")
        # Build the exact historical v1 aggregate from a known synthetic state.
        # The test deliberately discards the incident history before sealing.
        with self.f.ledger._transaction() as db:
            self.state=self.f.ledger._load(db)
        self.state.pop("previous_sha256")
        self.state["schema"]=LEGACY_SCHEMA
        self.write_legacy(self.state)

    def write_legacy(self,state):
        plain=canonical(state)
        revision=state["revision"]
        sha=hashlib.sha256(plain).hexdigest()
        ref=ArtifactRef("wilborn-demo","security/wilborn/synthetic_fixture/"+self.f.options["ledger_id"],
                        revision,sha).to_dict()
        sealed=seal_demo(plain,artifact_ref=ref,key_id=self.f.options["key_id"],
                         master_key=self.f.options["master_key"])
        if not self.path.exists():
            fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            os.close(fd)
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute("CREATE TABLE IF NOT EXISTS checkpoint (slot INTEGER PRIMARY KEY,revision INTEGER NOT NULL,envelope TEXT NOT NULL)")
            db.execute("INSERT OR REPLACE INTO checkpoint VALUES(1,?,?)",(revision,canonical(sealed).decode()))
        b=anchor_bindings(self.f.options["ledger_id"],revision,sha)
        return {"bindings":b,"attestation":self.f.sign(self.f.anchorer,ANCHOR_CLAIM,b,self.f.now,"independent-reproduction")}

    def inspect(self,**overrides):
        return inspect_legacy_checkpoint(self.path,custody=self.test.open_custody(),
                                        **{**self.test.options,**overrides})

    def test_exact_legacy_summary_not_a_migration(self):
        self.test.custody.retain(self.write_legacy(self.state))
        original=self.path.read_bytes()
        result=self.inspect()
        self.assertEqual(result["aggregate_counts"],{"auth_failure":1,"integrity_failure":1})
        self.assertEqual(result["accepted_events"],2)
        self.assertEqual(result["pending_alerts"],{"integrity_failure":1})
        self.assertFalse(result["historical_incident_detail_available"])
        self.assertEqual(result["historical_incidents_reconstructed"],0)
        self.assertFalse(result["migration_authorized"])
        self.assertFalse(result["execution_authorized"])
        self.assertEqual(self.path.read_bytes(),original)
        with self.assertRaises(ValueError):
            self.test.open_custody().open_ledger(self.path,**self.test.options)
        self.assertEqual(self.path.read_bytes(),original)

    def test_missing_wrong_anchor_and_key(self):
        with self.assertRaises(PermissionError):
            self.inspect()
        self.test.custody.retain(self.write_legacy(self.state))
        with self.assertRaises(PermissionError):
            self.inspect(master_key=os.urandom(32))
        self.f.observe("tool_denied")
        self.test.custody.retain(self.f.anchor())
        with self.assertRaises(PermissionError):
            self.inspect()

    def test_signed_malformed_legacy_state_rejected(self):
        invalid=deepcopy(self.state)
        invalid["counts"]["auth_failure"]=9
        self.test.custody.retain(self.write_legacy(invalid))
        with self.assertRaises(ValueError):
            self.inspect()

    def test_legacy_report_refuses_history_or_other_schema(self):
        self.test.custody.retain(self.write_legacy(self.state))
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute("CREATE TABLE history (revision INTEGER PRIMARY KEY)")
        with self.assertRaises(ValueError):
            self.inspect()
