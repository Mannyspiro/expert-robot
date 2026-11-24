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

class SecurityReviewTests(unittest.TestCase):
    def test_validate_and_render(self):
        html=render_snapshot(fixture())
        for phrase in ("SYNTHETIC DEMO","integrity_failure","operator_review","Host reports signed anchor revision 2"):
            self.assertIn(phrase,html)
        self.assertNotIn("<script",html)
        self.assertNotIn("<form",html)
        self.assertIn("No host security summary configured",render_snapshot(None))

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

    def test_actual_local_route_is_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"summary.json"
            p.write_text(json.dumps(fixture()),encoding="utf-8")
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
                self.assertIn("integrity_failure",body)
                self.assertEqual(cache,"no-store")
                self.assertIn('href="/studio/security"',request("GET","/studio/")[1])
                self.assertEqual(request("GET","/studio/security",{"Origin":"https://example.invalid"})[0],403)
                self.assertEqual(request("POST","/studio/security",{"Content-Type":"application/json"},b"{}")[0],403)
                self.assertEqual(request("GET","/studio/security")[1],body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
