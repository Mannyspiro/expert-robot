"""Loopback-only, read-only synthetic HTTP prototype. NOT a real-client API."""
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .store import CaseStore
from .provenance import response_envelope

def make_handler(db_path, token):
    if not token or len(token) < 32:
        raise ValueError("development API token must have at least 32 characters")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            supplied=self.headers.get("Authorization", "")
            if not hmac.compare_digest(supplied,"Bearer "+token):
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

def serve(db_path, token, host="127.0.0.1", port=8768):
    if host not in ("127.0.0.1","::1"):
        raise ValueError("prototype API must bind to loopback")
    ThreadingHTTPServer((host,port),make_handler(db_path,token)).serve_forever()

if __name__=="__main__":
    token=os.environ.get("WILBORN_DEMO_TOKEN","")
    if not token: raise SystemExit("WILBORN_DEMO_TOKEN required")
    serve(os.environ.get("WILBORN_DEMO_DB","wilborn-demo.sqlite3"),token)
