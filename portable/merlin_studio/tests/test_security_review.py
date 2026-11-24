"""Portable Studio synthetic-only security-summary route regression."""
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from copy import deepcopy

STUDIO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STUDIO))
from security_review import validate_snapshot,load_snapshot,render_snapshot
from server import create_server

def fixture():
    return {"schema":"merlin-studio-security-summary/1","environment":"demo","data_class":"synthetic",
        "execution_authorized":False,"production_qualified":False,"revision":3,"accepted_events":1,
        "operator_reviews":1,"counts":{"integrity_failure":1},"pending_alerts":{},
        "active_correlations":[],"external_anchor_revision":2,"external_anchor_verified":True,
        "recent_incidents":[{"revision":2,"type":"event","kind":"integrity_failure"},
                            {"revision":3,"type":"operator_review"}]}

def rotation_fixture():
    predecessor={"segment_index":0,"role":"predecessor_archive","revision":5,
        "accepted_events":3,"operator_reviews":1,"counts":{"auth_failure":2,"tool_denied":1},
        "pending_alerts":{"auth_failure":1},"active_correlations":[],
        "external_anchor_revision":5,"external_anchor_verified":True}
    successor={"segment_index":1,"role":"successor_genesis","revision":1,
        "accepted_events":0,"operator_reviews":0,"counts":{},"pending_alerts":{},
        "active_correlations":[],"external_anchor_revision":1,"external_anchor_verified":True}
    return {"schema":"merlin-studio-security-summary/2","environment":"demo","data_class":"synthetic",
        "execution_authorized":False,"production_qualified":False,"activation_authorized":False,
        "writer_handover_verified":False,"review_scope":"staged_rotation","accepted_events":3,
        "operator_reviews":1,"counts":dict(predecessor["counts"]),"pending_alerts":{"auth_failure":1},
        "segments":[predecessor,successor],"recent_incidents":[
            {"segment_index":0,"revision":2,"type":"event","kind":"auth_failure"},
            {"segment_index":0,"revision":3,"type":"event","kind":"tool_denied"},
            {"segment_index":0,"revision":4,"type":"operator_review"},
            {"segment_index":0,"revision":5,"type":"event","kind":"auth_failure"}]}

class SecurityReviewTests(unittest.TestCase):
    def test_validate_and_render(self):
        html=render_snapshot(fixture())
        for phrase in ("SYNTHETIC DEMO","integrity_failure","operator_review","Host reports signed anchor revision 2"):
            self.assertIn(phrase,html)
        self.assertNotIn("<script",html)
        self.assertNotIn("<form",html)
        self.assertIn("No host security summary configured",render_snapshot(None))

    def test_rotation_preserves_segments_pending_alerts_and_authority_labels(self):
        snapshot=rotation_fixture()
        before=deepcopy(snapshot)
        self.assertEqual(validate_snapshot(snapshot),before)
        html=render_snapshot(snapshot)
        for phrase in ("SYNTHETIC DEMO","Staged rotation review","Predecessor archive · Segment 0",
                       "Successor genesis · Segment 1","Pending predecessor alerts",
                       "auth_failure","tool_denied","operator_review","Segment revision 5",
                       "Segment revision 1","Host reports signed anchor revision 5 for this segment",
                       "Host reports signed anchor revision 1 for this segment",
                       "Writer handover not verified","Successor not activated",
                       "Host-reported continuity","does not independently verify",
                       "Each revision belongs to its segment"):
            self.assertIn(phrase,html)
        self.assertNotIn("<script",html)
        self.assertNotIn("<form",html)
        self.assertNotIn("Global revision",html)
        self.assertEqual(snapshot,before)

    def test_rotation_requires_exact_scope_and_non_authorizing_fields(self):
        for change in ({"schema":"merlin-studio-security-summary/3"},{"environment":"production"},
                       {"data_class":"real"},{"execution_authorized":True},{"production_qualified":True},
                       {"activation_authorized":True},{"writer_handover_verified":True},
                       {"execution_authorized":0},{"activation_authorized":0},
                       {"writer_handover_verified":0},{"review_scope":"active_rotation"},
                       {"accepted_events":True},{"operator_reviews":1.0},
                       {"revision":6},{"external_anchor_verified":True}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_snapshot(dict(rotation_fixture(),**change))
        for field in rotation_fixture():
            with self.subTest(missing=field),self.assertRaises(ValueError):
                value=rotation_fixture()
                del value[field]
                validate_snapshot(value)

    def test_rotation_rejects_segment_reordering_bad_counts_and_stale_anchors(self):
        changes=(
            ("segments",[]),("segments",rotation_fixture()["segments"]*2),
            ("segments",list(reversed(rotation_fixture()["segments"]))),
            ("accepted_events",2),("operator_reviews",2),
            ("counts",{"auth_failure":3}),("pending_alerts",{}),
            ("counts",{"auth_failure":True,"tool_denied":2}),
            ("pending_alerts",{"auth_failure":True}),
        )
        for field,replacement in changes:
            with self.subTest(field=field,replacement=replacement),self.assertRaises(ValueError):
                value=rotation_fixture()
                value[field]=replacement
                validate_snapshot(value)
        segment_changes=(
            (0,"segment_index",False),(1,"segment_index",True),
            (0,"role","successor_genesis"),(0,"revision",1025),
            (0,"accepted_events",3.0),(0,"operator_reviews",True),
            (0,"counts",{"auth_failure":2,"tool_denied":2}),
            (0,"pending_alerts",{"auth_failure":4}),
            (0,"active_correlations",["tool_policy_denial_burst","authentication_denial_burst"]),
            (0,"active_correlations",["tool_policy_denial_burst","tool_policy_denial_burst"]),
            (0,"external_anchor_revision",4),(0,"external_anchor_verified",False),
            (0,"external_anchor_verified",1),(1,"external_anchor_revision",0),
            (1,"active_correlations",["authentication_denial_burst"]),
        )
        for index,field,replacement in segment_changes:
            with self.subTest(segment=index,field=field,replacement=replacement),self.assertRaises(ValueError):
                value=rotation_fixture()
                value["segments"][index][field]=replacement
                validate_snapshot(value)

    def test_rotation_rejects_even_consistent_successor_activity(self):
        value=rotation_fixture()
        value["segments"][1].update(revision=2,accepted_events=1,
            counts={"tool_denied":1},pending_alerts={"tool_denied":1},external_anchor_revision=2)
        value["accepted_events"]+=1
        value["counts"]["tool_denied"]+=1
        value["pending_alerts"]["tool_denied"]=1
        value["recent_incidents"].append({"segment_index":1,"revision":2,"type":"event","kind":"tool_denied"})
        with self.assertRaises(ValueError):
            validate_snapshot(value)

    def test_rotation_requires_exact_bounded_incident_suffix(self):
        value=rotation_fixture()
        value["segments"][0].update(revision=26,accepted_events=25,operator_reviews=0,
            counts={"auth_failure":25},external_anchor_revision=26)
        value.update(accepted_events=25,operator_reviews=0,counts={"auth_failure":25},
            recent_incidents=[{"segment_index":0,"revision":n,"type":"event","kind":"auth_failure"}
                              for n in range(7,27)])
        self.assertEqual(validate_snapshot(value),value)
        mutations=(
            lambda v:v["recent_incidents"].reverse(),
            lambda v:v["recent_incidents"].pop(),
            lambda v:v["recent_incidents"][0].update(revision=6),
            lambda v:v["recent_incidents"][0].update(revision=True),
            lambda v:v["recent_incidents"][0].update(segment_index=1),
            lambda v:v["recent_incidents"][0].update(segment_index=False),
            lambda v:v["recent_incidents"][0].update(kind="tool_denied"),
            lambda v:v["recent_incidents"][0].update(kind="<script>"),
            lambda v:v["recent_incidents"].__setitem__(0,{"segment_index":0,"revision":7,"type":"operator_review"}),
        )
        for index,mutate in enumerate(mutations):
            with self.subTest(mutation=index),self.assertRaises(ValueError):
                changed=deepcopy(value)
                mutate(changed)
                validate_snapshot(changed)

    def test_rotation_rejects_extra_identity_key_and_payload_fields_at_each_boundary(self):
        for boundary in ("top","segment","incident"):
            for field in ("signer_id","key","payload","receipt","ledger_id"):
                with self.subTest(boundary=boundary,field=field):
                    value=rotation_fixture()
                    target=value if boundary=="top" else value["segments"][0] if boundary=="segment" else value["recent_incidents"][0]
                    target[field]="DO_NOT_LOG"
                    with self.assertRaises(ValueError) as failure:
                        validate_snapshot(value)
                    self.assertNotIn("DO_NOT_LOG",str(failure.exception))

    def test_reject_promotion_payload_and_bad_counts(self):
        for change in ({"data_class":"real"},{"execution_authorized":True},
                       {"production_qualified":True},{"revision":True},{"counts":{"raw-secret":1}},
                       {"external_anchor_revision":4},{"external_anchor_verified":1},
                       {"recent_incidents":[{"revision":2,"type":"event","kind":"<script>"}]},
                       {"extra":"DO_NOT_LOG"}):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    validate_snapshot(dict(fixture(),**change))

    def test_file_bounds_and_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"summary.json"
            p.write_text(json.dumps(fixture()),encoding="utf-8")
            self.assertEqual(load_snapshot(p),fixture())
            p.write_text('{"schema":"a","schema":"b"}',encoding="utf-8")
            with self.assertRaises(ValueError):
                load_snapshot(p)
            p.write_bytes(b"x"*32769)
            with self.assertRaises(ValueError):
                load_snapshot(p)

    def test_rotation_file_rejects_nested_duplicate_keys_and_invalid_startup(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"summary.json"
            raw=json.dumps(rotation_fixture())
            p.write_text(raw,encoding="utf-8")
            self.assertEqual(load_snapshot(p),rotation_fixture())
            p.write_text(raw.replace('"segment_index": 0','"segment_index": 0, "segment_index": 0',1),encoding="utf-8")
            with self.assertRaises(ValueError):
                load_snapshot(p)
            invalid=rotation_fixture()
            invalid["writer_handover_verified"]=True
            p.write_text(json.dumps(invalid),encoding="utf-8")
            with self.assertRaises(ValueError):
                create_server(data_dir=Path(d)/"data",start_bundled=False,security_report=p)
            self.assertFalse((Path(d)/"data").exists())

    def _assert_actual_local_route_is_read_only(self,snapshot,phrases):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"summary.json"
            p.write_text(json.dumps(snapshot),encoding="utf-8")
            original_bytes=p.read_bytes()
            server=create_server(data_dir=Path(d)/"data",start_bundled=False,security_report=p)
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                def request(method,path,headers=None,body=None):
                    conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=5)
                    try:
                        conn.request(method,path,body=body,headers=headers or {})
                        response=conn.getresponse()
                        return response.status,response.read().decode(),response.getheader("Cache-Control")
                    finally:
                        conn.close()
                status,body,cache=request("GET","/studio/security")
                self.assertEqual(status,200)
                for phrase in phrases:
                    self.assertIn(phrase,body)
                self.assertEqual(cache,"no-store")
                self.assertIn('href="/studio/security"',request("GET","/studio/")[1])
                self.assertEqual(request("GET","/studio/security",{"Origin":"https://example.invalid"})[0],403)
                self.assertEqual(request("POST","/studio/security",{"Content-Type":"application/json"},b"{}")[0],403)
                self.assertEqual(request("POST","/studio/security",{"Content-Type":"application/json",
                    "X-Merlin-Token":server.session_token},b"{}")[0],404)
                self.assertEqual(request("GET","/studio/security")[1],body)
                self.assertEqual(p.read_bytes(),original_bytes)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_actual_local_route_is_read_only(self):
        self._assert_actual_local_route_is_read_only(fixture(),("integrity_failure","Host reports signed anchor revision 2"))

    def test_actual_local_rotation_route_is_read_only(self):
        self._assert_actual_local_route_is_read_only(rotation_fixture(),("Pending predecessor alerts",
            "auth_failure","Segment revision 5","Segment revision 1","Writer handover not verified",
            "Successor not activated","Host-reported continuity"))
