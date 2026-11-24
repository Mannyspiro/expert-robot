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

def lineage_fixture():
    value=rotation_fixture()
    value.update(schema="merlin-studio-security-summary/3",review_scope="active_lineage",
                 writer_handover_verified=True,ownership_epoch=3,active_segment_index=2,
                 accepted_events=7,operator_reviews=2,
                 counts={"auth_failure":3,"tool_denied":3,"integrity_failure":1},
                 pending_alerts={"auth_failure":1,"integrity_failure":1})
    value["segments"][0]["role"]="archived_predecessor"
    value["segments"][1].update(role="archived_predecessor",revision=3,accepted_events=2,
        counts={"integrity_failure":1,"tool_denied":1},pending_alerts={"integrity_failure":1},
        external_anchor_revision=3)
    value["segments"].append({"segment_index":2,"role":"active_successor","revision":4,
        "accepted_events":2,"operator_reviews":1,"counts":{"auth_failure":1,"tool_denied":1},
        "pending_alerts":{},"active_correlations":[],"external_anchor_revision":2,
        "external_anchor_verified":True})
    value["recent_incidents"].extend([
        {"segment_index":1,"revision":2,"type":"event","kind":"integrity_failure"},
        {"segment_index":1,"revision":3,"type":"event","kind":"tool_denied"},
        {"segment_index":2,"revision":2,"type":"event","kind":"tool_denied"},
        {"segment_index":2,"revision":3,"type":"event","kind":"auth_failure"},
        {"segment_index":2,"revision":4,"type":"operator_review"}])
    return value

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

    def test_active_lineage_preserves_pending_segments_and_host_claim_scope(self):
        value=lineage_fixture()
        before=deepcopy(value)
        self.assertEqual(validate_snapshot(value),before)
        html=render_snapshot(value)
        for phrase in ("SYNTHETIC DEMO","Active lineage review","Archived predecessor · Segment 0",
                       "Archived predecessor · Segment 1","Active successor · Segment 2",
                       "Host reports local writer handover verified","Active synthetic segment 2",
                       "Ownership epoch 3","Pending archived alerts","Pending active alerts",
                       "Pending alerts across all segments","Total events 7","Total reviews 2",
                       "Host-reported active lineage","does not independently verify",
                       "reported anchor may precede its current revision","No execution authorized",
                       "Each revision belongs to its segment"):
            self.assertIn(phrase,html)
        for phrase in ("<script","<form","Global revision","Staged rotation review","Successor not activated"):
            self.assertNotIn(phrase,html)
        self.assertEqual(value,before)

    def test_lineage_rejects_promotion_scope_and_owner_field_substitution(self):
        changes=({"environment":"production"},{"data_class":"real"},{"execution_authorized":True},
            {"production_qualified":True},{"activation_authorized":True},{"activation_authorized":0},
            {"writer_handover_verified":False},{"writer_handover_verified":1},
            {"review_scope":"staged_rotation"},{"ownership_epoch":True},{"ownership_epoch":0},
            {"ownership_epoch":1.0},{"ownership_epoch":1<<63},{"active_segment_index":True},
            {"active_segment_index":0},{"active_segment_index":3},{"active_segment_index":2.0},
            {"schema":{}},{"schema":"merlin-studio-security-summary/4"})
        for change in changes:
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_snapshot(dict(lineage_fixture(),**change))
        for field in lineage_fixture():
            with self.subTest(missing=field),self.assertRaises(ValueError):
                value=lineage_fixture()
                del value[field]
                validate_snapshot(value)

    def test_lineage_requires_dense_order_one_active_tail_and_retained_anchors(self):
        for segment,field,replacement in (
            (0,"segment_index",1),(1,"segment_index",0),(1,"segment_index",True),
            (0,"role","active_successor"),(1,"role","predecessor_archive"),
            (2,"role","archived_predecessor"),(2,"role","successor_genesis"),
            (0,"external_anchor_revision",4),(1,"external_anchor_revision",2),
            (1,"external_anchor_verified",False),(2,"external_anchor_revision",0),
            (2,"external_anchor_revision",5),(2,"external_anchor_verified",1),
            (2,"accepted_events",1),(2,"operator_reviews",True),(2,"revision",1025)):
            with self.subTest(segment=segment,field=field),self.assertRaises(ValueError):
                value=lineage_fixture()
                value["segments"][segment][field]=replacement
                validate_snapshot(value)
        for mutation in (
            lambda v:v["segments"].reverse(),
            lambda v:v["segments"].pop(1),
            lambda v:v.update(segments=[]),
            lambda v:v.update(segments=[v["segments"][-1]]),
            lambda v:v.update(segments=v["segments"]*3)):
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                value=lineage_fixture()
                mutation(value)
                validate_snapshot(value)
        value=lineage_fixture()
        value["segments"][-1]["external_anchor_revision"]=4
        self.assertEqual(validate_snapshot(value),value)

    def test_lineage_rejects_inconsistent_totals_and_extra_private_fields(self):
        for field,replacement in (("accepted_events",6),("operator_reviews",1),
                ("counts",{"auth_failure":4,"tool_denied":2,"integrity_failure":1}),
                ("pending_alerts",{"auth_failure":1}),
                ("pending_alerts",{"auth_failure":True,"integrity_failure":1})):
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate_snapshot(dict(lineage_fixture(),**{field:replacement}))
        for boundary in ("top","segment","incident"):
            for field in ("owner_id","handover_id","ledger_id","state_sha256","key","receipt","payload"):
                with self.subTest(boundary=boundary,field=field),self.assertRaises(ValueError) as rejected:
                    value=lineage_fixture()
                    target=value if boundary=="top" else value["segments"][1] if boundary=="segment" else value["recent_incidents"][0]
                    target[field]="DO_NOT_LOG"
                    validate_snapshot(value)
                self.assertNotIn("DO_NOT_LOG",str(rejected.exception))

    def test_lineage_requires_exact_cross_segment_history_suffix(self):
        for mutation in (
            lambda v:v["recent_incidents"].reverse(),
            lambda v:v["recent_incidents"].pop(),
            lambda v:v["recent_incidents"][4].update(segment_index=0),
            lambda v:v["recent_incidents"][4].update(revision=3),
            lambda v:v["recent_incidents"][4].update(kind="auth_failure"),
            lambda v:v["recent_incidents"][4].update(kind="<script>"),
            lambda v:v["recent_incidents"].__setitem__(4,{"segment_index":1,"revision":2,"type":"operator_review"})):
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                value=lineage_fixture()
                mutation(value)
                validate_snapshot(value)
        value=lineage_fixture()
        value["segments"][0].update(revision=26,accepted_events=25,operator_reviews=0,
            counts={"auth_failure":25},external_anchor_revision=26)
        value.update(accepted_events=29,operator_reviews=1,
            counts={"auth_failure":26,"tool_denied":2,"integrity_failure":1},
            recent_incidents=[{"segment_index":0,"revision":n,"type":"event","kind":"auth_failure"}
                              for n in range(12,27)]+value["recent_incidents"][4:])
        self.assertEqual(len(value["recent_incidents"]),20)
        self.assertEqual(validate_snapshot(value),value)
        for change in ({"revision":11},{"segment_index":1}):
            with self.subTest(truncated_prefix=change),self.assertRaises(ValueError):
                changed=deepcopy(value)
                changed["recent_incidents"][0].update(change)
                validate_snapshot(changed)

    def test_lineage_bounds_cover_eight_full_segments_and_twenty_incidents(self):
        value=lineage_fixture()
        value.update(ownership_epoch=(1<<63)-1,active_segment_index=7,accepted_events=8*1023,
                     operator_reviews=0,counts={"auth_failure":8*1023},pending_alerts={"auth_failure":8},
                     segments=[],recent_incidents=[])
        for index in range(8):
            value["segments"].append({"segment_index":index,
                "role":"active_successor" if index==7 else "archived_predecessor",
                "revision":1024,"accepted_events":1023,"operator_reviews":0,
                "counts":{"auth_failure":1023},"pending_alerts":{"auth_failure":1},
                "active_correlations":[],"external_anchor_revision":1024 if index<7 else 1,
                "external_anchor_verified":True})
        value["recent_incidents"]=[{"segment_index":7,"revision":n,"type":"event","kind":"auth_failure"}
                                   for n in range(1005,1025)]
        self.assertEqual(validate_snapshot(value),value)
        self.assertLess(len(json.dumps(value).encode("utf-8")),32768)
        for replacement in (value["recent_incidents"][:-1],
                            [{"segment_index":7,"revision":1004,"type":"event","kind":"auth_failure"}]+value["recent_incidents"]):
            with self.subTest(records=len(replacement)),self.assertRaises(ValueError):
                validate_snapshot(dict(value,recent_incidents=replacement))

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

    def test_actual_local_lineage_route_is_read_only(self):
        self._assert_actual_local_route_is_read_only(lineage_fixture(),("Active lineage review",
            "Archived predecessor · Segment 0","Archived predecessor · Segment 1",
            "Active successor · Segment 2","Pending archived alerts","Ownership epoch 3",
            "Host reports local writer handover verified","does not independently verify"))
