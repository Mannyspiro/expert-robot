"""Synthetic-only signed producer, history, and independent-anchor checks."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import http.client
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4
from http.server import ThreadingHTTPServer

from test_wilborn_attested_integration import Signer
from test_cace_attestation import make_attestation
from wilborn_ops.attestation_boundary import digest
from wilborn_ops.security_ledger import (
    SecurityLedger,EVENT_CLAIM,REVIEW_CLAIM,ANCHOR_CLAIM,anchor_bindings,review_bindings)
from wilborn_ops.security_sensor import SignedSecurityMonitor
from wilborn_ops.security_monitor import KINDS,SecurityEvent
from wilborn_ops.security_dashboard import render_operator_report,studio_snapshot
from wilborn_ops.security_triage import triage
from wilborn_ops.artex_detection import ArtexObservation,observe_lead
from wilborn_ops.gateway import BusinessGateway,Identity
from wilborn_ops.llm_boundary import BusinessToolDispatcher,ToolCall
from wilborn_ops.read_api import make_handler
from wilborn_ops.store import CaseStore

class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"security.sqlite3"
        self.sensor=Signer("fixture-sensor")
        self.operator=Signer("fixture-operator")
        self.anchorer=Signer("fixture-anchor")
        self.now=1795482000
        self.options=dict(ledger_id=str(uuid4()),master_key=os.urandom(32),
            key_id="fixture-key",sensor_keys=self.sensor.trust,operator_keys=self.operator.trust,
            requester_id="fixture-worker",clock=lambda:self.now)
        self.ledger=self.open(create=True)
        self.monitor=SignedSecurityMonitor(self.ledger,self.sign_event)

    def open(self,path=None,**options):
        return SecurityLedger(path or self.path,**{**self.options,**options})

    def sign(self,signer,claim,binding,now,purpose):
        envelope,_,_=make_attestation(signer.key,claim_id=claim,bundle_sha256=digest(binding),
            bindings=binding,verifier_id=signer.name,purpose=purpose,
            created_at_utc=datetime.fromtimestamp(now,timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        return envelope

    def sign_event(self,binding,now):
        return self.sign(self.sensor,EVENT_CLAIM,binding,now,"artifact-integrity")

    def observe(self,kind):
        return self.monitor.observe(SecurityEvent(kind,"demo","synthetic"))

    def anchor(self):
        r=self.ledger.report()
        b=anchor_bindings(r["ledger_id"],r["revision"],r["state_sha256"])
        return {"bindings":b,"attestation":self.sign(self.anchorer,ANCHOR_CLAIM,b,self.now,"independent-reproduction")}

    def test_http_tool_and_passive_event_producers_share_ledger(self):
        dbpath=Path(self.temp.name)/"cases.sqlite3"
        store=CaseStore(dbpath)
        self.addCleanup(store.close)
        dispatcher=BusinessToolDispatcher(BusinessGateway(store),monitor=self.monitor)
        identity=Identity("fixture","wilborn-demo",frozenset({"cases:read"}))
        with self.assertRaises(PermissionError):
            dispatcher.dispatch(identity,ToolCall("list_cases",{}))
        server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(dbpath,"x"*40,monitor=self.monitor))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=3)
            conn.request("GET","/health")
            res=conn.getresponse()
            self.assertEqual(res.status,401)
            res.read()
            conn.close()
            conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=3)
            conn.request("GET","/health",headers={"Authorization":"Bearer "+"x"*40})
            res=conn.getresponse()
            self.assertEqual(res.status,200)
            res.read()
            conn.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        lead=observe_lead(self.monitor,ArtexObservation("inbound_user_agent","artex-enrich/1.0"))
        self.assertFalse(lead["framework_execution_verified"])
        r=self.open().report()
        self.assertEqual(r["counts"],{"tool_denied":1,"auth_failure":1,"artex_inbound_indicator":1})
        self.assertEqual(r["revision"],4)
        self.assertFalse(r["execution_authorized"])

    def test_concurrent_signed_producers_allocate_unique_sequences(self):
        bridges=[SignedSecurityMonitor(self.open(),self.sign_event) for _ in range(8)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda b:b.observe(SecurityEvent("tool_denied","demo","synthetic")),bridges))
        self.assertEqual(sorted(r["accepted_events"] for r in results),list(range(1,9)))
        h=self.open().history()
        self.assertEqual([e["sequence"] for e in h["entries"]],list(range(1,9)))
        self.assertEqual(self.ledger.report()["counts"],{"tool_denied":8})

    def test_signer_failure_and_wrong_role_are_atomic(self):
        def broken(binding,now):
            raise RuntimeError("fixture signer unavailable")
        def wrong(binding,now):
            return self.sign(self.operator,EVENT_CLAIM,binding,now,"artifact-integrity")
        for signer in (broken,wrong):
            with self.assertRaises((RuntimeError,PermissionError,ValueError)):
                SignedSecurityMonitor(self.open(),signer).observe(SecurityEvent("auth_failure","demo","synthetic"))
        self.assertEqual(self.ledger.report()["revision"],1)
        self.assertEqual(self.ledger.history()["entries"],[])
        self.assertEqual(self.observe("auth_failure")["accepted_events"],1)

    def test_history_survives_signed_review_and_is_encrypted(self):
        r=self.observe("integrity_failure")
        b=review_bindings(r["ledger_id"],r["revision"],r["state_sha256"])
        a=self.sign(self.operator,REVIEW_CLAIM,b,self.now,"independent-reproduction")
        self.ledger.acknowledge(b,a)
        h=self.open().history()
        self.assertEqual([x["type"] for x in h["entries"]],["event","operator_review"])
        self.assertEqual(h["entries"][1]["acknowledged"],{"integrity_failure":1})
        self.assertEqual(self.open().report()["pending_alerts"],{})
        with sqlite3.connect(self.path) as db:
            raw=db.execute("SELECT envelope FROM history").fetchall()
        self.assertEqual(len(raw),3)
        for row in raw:
            self.assertNotIn("integrity_failure",row[0])
            self.assertNotIn(self.options["master_key"].hex(),row[0])
        html=render_operator_report(self.open())
        self.assertIn("Recent incident history",html)
        self.assertIn("operator_review",html)
        self.assertNotIn("fixture-operator",html)

    def test_deleted_history_and_divergent_checkpoint_rejected(self):
        self.observe("auth_failure")
        self.observe("tool_denied")
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM history WHERE revision=2")
        with self.assertRaises(PermissionError):
            self.open()

    def test_independent_anchor_rejects_restored_old_database(self):
        self.observe("auth_failure")
        old=Path(self.temp.name)/"older.sqlite3"
        with sqlite3.connect(self.path) as src,sqlite3.connect(old) as dst:
            src.backup(dst)
        self.observe("tool_denied")
        anchor=self.anchor()
        self.assertEqual(self.open(anchor=anchor,anchor_keys=self.anchorer.trust).report()["external_anchor_revision"],3)
        self.assertIn("Signed revision 3",render_operator_report(self.open(anchor=anchor,anchor_keys=self.anchorer.trust)))
        self.observe("integrity_failure")
        self.assertTrue(self.open(anchor=anchor,anchor_keys=self.anchorer.trust).report()["external_anchor_verified"])
        with self.assertRaises(PermissionError):
            self.open(old,anchor=anchor,anchor_keys=self.anchorer.trust)
        self.assertEqual(self.open(old).report()["revision"],2)
        with self.assertRaises(PermissionError):
            self.open(anchor=anchor,anchor_keys=self.sensor.trust)
        altered=json.loads(json.dumps(anchor))
        altered["bindings"]["state_sha256"]="0"*64
        with self.assertRaises(PermissionError):
            self.open(anchor=altered,anchor_keys=self.anchorer.trust)

    def test_all_new_event_types_have_triage_recommendations(self):
        for kind in KINDS:
            findings=triage({"environment":"demo","data_class":"synthetic","counts":{kind:1}})
            self.assertEqual(len(findings),1)
            self.assertEqual(findings[0].kind,kind)

    def test_studio_export_excludes_keys_identity_and_payload(self):
        self.observe("integrity_failure")
        r=studio_snapshot(self.ledger)
        self.assertEqual(r["schema"],"merlin-studio-security-summary/1")
        self.assertEqual(r["recent_incidents"],[{"revision":2,"type":"event","kind":"integrity_failure"}])
        self.assertFalse(r["execution_authorized"])
        self.assertFalse(r["production_qualified"])
        self.assertEqual(r["data_class"],"synthetic")
        raw=json.dumps(r)
        for forbidden in ("fixture-sensor","fixture-operator","state_sha256",
                          self.options["ledger_id"],self.options["master_key"].hex()):
            self.assertNotIn(forbidden,raw)

    def test_one_fully_verified_coherent_review_snapshot(self):
        for kind in ("auth_failure","integrity_failure","tool_denied"):
            self.observe(kind)
        expected_report=self.ledger.report()
        expected_history=self.ledger.history()
        with patch.object(self.ledger,"_verified_history",wraps=self.ledger._verified_history) as scan:
            report,history=self.ledger.review_snapshot()
            self.assertEqual(scan.call_count,1)
        self.assertEqual(report,expected_report)
        self.assertEqual(history,expected_history)
        with patch.object(self.ledger,"_verified_history",wraps=self.ledger._verified_history) as scan:
            self.assertEqual(studio_snapshot(self.ledger)["revision"],report["revision"])
            self.assertEqual(scan.call_count,1)
        with patch.object(self.ledger,"_verified_history",wraps=self.ledger._verified_history) as scan:
            self.assertIn("Recent incident history",render_operator_report(self.ledger))
            self.assertEqual(scan.call_count,1)

    def test_review_snapshot_rechecks_history_after_storage_change(self):
        self.observe("auth_failure")
        self.observe("integrity_failure")
        self.ledger.review_snapshot()
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM history WHERE revision=2")
        for read in (self.ledger.review_snapshot,self.ledger.history,
                     lambda:studio_snapshot(self.ledger),lambda:render_operator_report(self.ledger)):
            with self.assertRaises(PermissionError):
                read()

    def test_review_snapshot_serializes_with_event_writers(self):
        self.observe("auth_failure")
        def read(_):
            report,history=self.ledger.review_snapshot()
            self.assertEqual(report["revision"],history["revision"])
            self.assertEqual(report["accepted_events"],len(history["entries"]))
            self.assertEqual(report["counts"]["auth_failure"],len(history["entries"]))
            return report["revision"]
        def write(_):
            return self.observe("auth_failure")["revision"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            tasks=[pool.submit(fn,i) for i in range(8) for fn in (read,write)]
            for task in tasks:
                task.result()
        self.assertEqual(self.ledger.report()["accepted_events"],9)
