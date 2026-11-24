"""Synthetic-only checkpoint, signature and recovery regression tests."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4

from test_wilborn_attested_integration import Signer
from test_cace_attestation import make_attestation
from wilborn_ops.attestation_boundary import digest
from wilborn_ops.security_ledger import (
    SecurityLedger,event_bindings,review_bindings,EVENT_CLAIM,REVIEW_CLAIM)
from wilborn_ops.security_dashboard import render_operator_report

class Clock:
    def __init__(self):
        self.value=1795482000
    def __call__(self):
        return self.value

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"security.sqlite3"
        self.sensor=Signer("fixture-sensor")
        self.operator=Signer("fixture-operator")
        self.clock=Clock()
        self.options=dict(ledger_id=str(uuid4()),master_key=os.urandom(32),
                          key_id="fixture-key",sensor_keys=self.sensor.trust,
                          operator_keys=self.operator.trust,requester_id="fixture-worker")
        self.ledger=self.open(create=True)

    def open(self,**overrides):
        options={**self.options,"clock":self.clock,**overrides}
        return SecurityLedger(self.path,**options)

    def sign(self,signer,claim,bindings,purpose,offset=0):
        created=datetime.fromtimestamp(self.clock.value+offset,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        envelope,_,_=make_attestation(signer.key,claim_id=claim,bundle_sha256=digest(bindings),
            bindings=bindings,verifier_id=signer.name,purpose=purpose,created_at_utc=created)
        return envelope

    def event(self,seq,kind,signer=None,offset=0):
        b=event_bindings(self.options["ledger_id"],seq,kind)
        a=self.sign(signer or self.sensor,EVENT_CLAIM,b,"artifact-integrity",offset)
        return b,a

    def review(self,report,signer=None):
        b=review_bindings(self.options["ledger_id"],report["revision"],report["state_sha256"])
        a=self.sign(signer or self.operator,REVIEW_CLAIM,b,"independent-reproduction")
        return b,a

    def test_authenticated_sequence_retry_and_expiry(self):
        e=self.event(1,"auth_failure")
        first=self.ledger.ingest(*e)
        self.assertEqual(first["accepted_events"],1)
        self.assertFalse(first["duplicate"])
        self.assertTrue(self.open().ingest(*e)["duplicate"])
        self.assertEqual(self.ledger.report()["revision"],2)
        for bad in (self.event(1,"tool_denied"),self.event(3,"auth_failure"),
                    self.event(2,"auth_failure",self.operator),
                    self.event(2,"auth_failure",offset=-601),
                    self.event(2,"auth_failure",offset=1)):
            with self.assertRaises((ValueError,PermissionError)):
                self.ledger.ingest(*bad)
        self.ledger.ingest(*self.event(2,"auth_failure"))
        with self.assertRaises(PermissionError):
            self.ledger.ingest(*e)
        result=self.open().ingest(*self.event(3,"auth_failure"))
        self.assertEqual(result["active_correlations"],["authentication_denial_burst"])
        self.assertEqual(result["pending_alerts"],{"authentication_denial_burst":1})
        self.clock.value+=60
        report=self.open().report()
        self.assertEqual(report["active_correlations"],[])
        self.assertEqual(report["pending_alerts"],{"authentication_denial_burst":1})
        self.assertEqual(report["counts"],{"auth_failure":3})

    def test_signed_review_does_not_clear_counts_or_authorize(self):
        report=self.ledger.ingest(*self.event(1,"integrity_failure"))
        review=self.review(report)
        with self.assertRaises((ValueError,PermissionError)):
            self.ledger.acknowledge(*self.review(report,self.sensor))
        newer=self.ledger.ingest(*self.event(2,"provenance_rejected"))
        with self.assertRaises(PermissionError):
            self.ledger.acknowledge(*review)
        ack=self.open().acknowledge(*self.review(newer))
        self.assertEqual(ack["counts"],{"integrity_failure":1,"provenance_rejected":1})
        self.assertEqual(ack["pending_alerts"],{})
        self.assertEqual(ack["operator_reviews"],1)
        self.assertEqual(ack["revision"],4)
        self.assertFalse(ack["execution_authorized"])
        self.assertFalse(ack["production_qualified"])
        self.assertFalse(ack["compromise_confirmed"])
        with self.assertRaises(PermissionError):
            self.ledger.acknowledge(*self.review(newer))
        with self.assertRaises(ValueError):
            self.ledger.acknowledge(*self.review(ack))

    def test_restart_in_separate_process(self):
        for seq in range(1,4):
            self.ledger.ingest(*self.event(seq,"tool_denied"))
        # Only a generated temporary synthetic key is passed on stdin.
        args={**self.options,"master_key":self.options["master_key"].hex(),
              "path":str(self.path),"fixture_clock":self.clock.value}
        code=("import sys,json; from wilborn_ops.security_ledger import SecurityLedger;"
              "a=json.load(sys.stdin); t=a.pop('fixture_clock');"
              "a['master_key']=bytes.fromhex(a['master_key']);"
              "print(json.dumps(SecurityLedger(**a,clock=lambda:t).report(),sort_keys=True))")
        result=subprocess.run([sys.executable,"-c",code],input=json.dumps(args),
                              text=True,capture_output=True,timeout=10,check=True)
        self.assertEqual(json.loads(result.stdout),self.ledger.report())

    def test_concurrent_duplicate_is_atomic(self):
        packet=self.event(1,"artex_guard_marker")
        workers=[self.open() for _ in range(4)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda w:w.ingest(*packet),workers))
        self.assertEqual(sum(not r["duplicate"] for r in results),1)
        self.assertEqual(self.ledger.report()["counts"],{"artex_guard_marker":1})

    def test_encryption_integrity_and_context(self):
        self.ledger.ingest(*self.event(1,"provenance_rejected"))
        with sqlite3.connect(self.path) as db:
            revision,raw=db.execute("SELECT revision,envelope FROM checkpoint").fetchone()
        self.assertEqual(revision,2)
        self.assertNotIn("provenance_rejected",raw)
        self.assertNotIn("fixture-sensor",raw)
        self.assertNotIn("fixture-operator",raw)
        self.assertNotIn(self.options["master_key"].hex(),raw)
        with self.assertRaises(PermissionError):
            self.open(master_key=os.urandom(32))
        with self.assertRaises(PermissionError):
            self.open(ledger_id=str(uuid4()))
        with self.assertRaises(PermissionError):
            self.open(operator_keys=Signer("other-fixture").trust)
        with self.assertRaises(PermissionError):
            self.open(min_revision=3)
        envelope=json.loads(raw)
        tag=envelope["tag_b64"]
        envelope["tag_b64"]=("A" if tag[0]!="A" else "B")+tag[1:]
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE checkpoint SET envelope=?",(json.dumps(envelope),))
        with self.assertRaises(PermissionError):
            self.open()

    def test_fail_closed_missing_state_clock_and_scope(self):
        with self.assertRaises(FileExistsError):
            self.open(create=True)
        packet=self.event(1,"auth_failure")
        forged=dict(packet[0],data_class="real")
        with self.assertRaises(PermissionError):
            self.ledger.ingest(forged,packet[1])
        with self.assertRaises(PermissionError):
            self.open(operator_keys=self.sensor.trust)
        self.ledger.ingest(*packet)
        self.clock.value-=1
        with self.assertRaises(PermissionError):
            self.ledger.report()
        self.clock.value+=1
        self.assertEqual(self.ledger.report()["accepted_events"],1)
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM checkpoint")
        with self.assertRaises(RuntimeError):
            self.open()
        self.path.unlink()
        with self.assertRaises(FileNotFoundError):
            self.open()
        self.assertFalse(self.path.exists())

    def test_dashboard_is_static_minimized_and_read_only(self):
        self.ledger.ingest(*self.event(1,"integrity_failure"))
        before=self.ledger.report()
        html=render_operator_report(self.ledger)
        self.assertIn("SYNTHETIC DEMO",html)
        self.assertIn("integrity_failure",html)
        self.assertIn(before["state_sha256"],html)
        for value in ("<script","<form","fixture-sensor","fixture-operator",
                      self.options["master_key"].hex(),"http://","https://"):
            self.assertNotIn(value,html)
        self.assertEqual(self.ledger.report(),before)
