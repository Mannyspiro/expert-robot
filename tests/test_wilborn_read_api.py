import http.client
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from wilborn_ops.read_api import make_handler, serve
from wilborn_ops.store import CaseStore
from wilborn_ops.workflow import Case
from wilborn_ops.security_monitor import SecurityMonitor

class ReadAPITests(unittest.TestCase):
    def test_auth_read_only_and_synthetic(self):
        with tempfile.TemporaryDirectory() as folder:
            dbpath=Path(folder)/"demo.db"
            store=CaseStore(dbpath)
            store.save(Case.open("workshop"))
            store.close()
            monitor=SecurityMonitor()
            server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(dbpath,"x"*40,monitor=monitor))
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                def request(method,path,token=None):
                    conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=3)
                    headers={"Authorization":"Bearer "+token} if token else {}
                    conn.request(method,path,headers=headers)
                    response=conn.getresponse()
                    body=response.read().decode()
                    conn.close()
                    return response.status,body
                self.assertEqual(request("GET","/v1/cases")[0],401)
                self.assertEqual(request("GET","/v1/cases","wrong")[0],401)
                self.assertEqual(request("GET","/v1/cases","\u00e9"*40)[0],401)
                self.assertEqual(monitor.summary()["counts"]["auth_failure"],3)
                self.assertEqual(monitor.summary()["active_correlations"],["authentication_denial_burst"])
                code,body=request("GET","/v1/cases","x"*40)
                self.assertEqual(code,200)
                self.assertIn('"workshop"',body)
                self.assertEqual(request("POST","/v1/cases","x"*40)[0],405)
                self.assertEqual(request("GET","/unknown","x"*40)[0],404)
                self.assertEqual(monitor.summary()["counts"]["tool_denied"],1)
                self.assertNotIn("x"*40,str(monitor.summary()))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_no_public_bind_and_short_token(self):
        with self.assertRaises(ValueError):
            make_handler(":memory:","short")
        with self.assertRaises(ValueError):
            serve(":memory:","x"*40,host="0.0.0.0")
