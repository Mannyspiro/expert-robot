"""Loopback-only, read-only synthetic HTTP prototype. NOT a real-client API."""
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .store import CaseStore
from .provenance import response_envelope
from .security_monitor import SecurityMonitor,SecurityEvent

def make_handler(db_path, token, *, monitor=None):
    if type(token) is not str or not 32<=len(token)<=512 or not token.isascii() or not token.isprintable():
        raise ValueError("bounded ASCII development API token required")
    monitor=monitor if monitor is not None else SecurityMonitor()
    if type(monitor) is not SecurityMonitor:
        raise TypeError("trusted demo monitor required")
    expected=("Bearer "+token).encode("ascii")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            supplied=self.headers.get_all("Authorization",[])
            if len(supplied)!=1 or not hmac.compare_digest(supplied[0].encode("utf-8"),expected):
                monitor.observe(SecurityEvent("auth_failure","demo","synthetic"))
                return self.respond(401,{"error":"unauthorized"})
            path=urlsplit(self.path).path
            if path=="/health":
                return self.respond(200,{"status":"ok","mode":"synthetic_read_only",
                                         "data_class":"synthetic","environment":"demo"})
            if path=="/v1/cases":
                store=CaseStore(db_path)
                try:
                    cases=[{"id":c.id,"service":c.service,"stage":c.stage.value}
                           for c in store.list_cases()]
                    result=response_envelope({"cases":cases},store.provenance)
                finally:
                    store.close()
                return self.respond(200,result)
            return self.respond(404,{"error":"not_found"})

        def do_POST(self):
            monitor.observe(SecurityEvent("tool_denied","demo","synthetic"))
            return self.respond(405,{"error":"read_only"})

        def respond(self,status,data):
            payload=json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type","application/json")
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self,format,*args):
            pass

    return Handler

def serve(db_path, token, host="127.0.0.1", port=8768, *, monitor=None):
    if host not in ("127.0.0.1","::1"):
        raise ValueError("prototype API must bind to loopback")
    ThreadingHTTPServer((host,port),make_handler(db_path,token,monitor=monitor)).serve_forever()

if __name__=="__main__":
    token=os.environ.get("WILBORN_DEMO_TOKEN","")
    if not token: raise SystemExit("WILBORN_DEMO_TOKEN required")
    serve(os.environ.get("WILBORN_DEMO_DB","wilborn-demo.sqlite3"),token)
