#!/usr/bin/env python3
"""Canonical local Merlin registry and read-only HTTP query API (Python stdlib)."""
from __future__ import annotations
import argparse, json, os, re, sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

SHA = re.compile(r"^[0-9a-f]{64}$")
def connect(path):
    db=sqlite3.connect(path); db.row_factory=sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db

def initialize(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    with connect(path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS intakes (
          intake_id TEXT PRIMARY KEY, archive_sha256 TEXT NOT NULL,
          archive_filename TEXT NOT NULL, archive_size_bytes INTEGER NOT NULL DEFAULT 0,
          manifest_sha256 TEXT NOT NULL, registered_at TEXT NOT NULL,
          file_count INTEGER NOT NULL, total_uncompressed_bytes INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS artifacts (
          intake_id TEXT NOT NULL REFERENCES intakes(intake_id) ON DELETE CASCADE,
          path TEXT NOT NULL, sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL,
          classification TEXT NOT NULL, PRIMARY KEY(intake_id,path));
        CREATE INDEX IF NOT EXISTS idx_artifacts_sha256 ON artifacts(sha256);
        CREATE INDEX IF NOT EXISTS idx_artifacts_classification ON artifacts(classification);
        CREATE TABLE IF NOT EXISTS projects(
          project_id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active');
        CREATE TABLE IF NOT EXISTS project_intakes(
          project_id TEXT NOT NULL REFERENCES projects(project_id),
          intake_id TEXT NOT NULL REFERENCES intakes(intake_id),
          attached_at TEXT NOT NULL, PRIMARY KEY(project_id,intake_id));
        CREATE TABLE IF NOT EXISTS github_commit_receipts(
          receipt_id TEXT PRIMARY KEY, project_id TEXT, repository TEXT NOT NULL, requested_sha TEXT NOT NULL,
          canonical_sha TEXT NOT NULL, commit_url TEXT NOT NULL, api_response_sha256 TEXT NOT NULL,
          signature_verified INTEGER NOT NULL, signature_reason TEXT, retrieved_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS verification_receipts(
          receipt_id TEXT PRIMARY KEY, artifact_sha256 TEXT NOT NULL, verifier_id TEXT NOT NULL,
          verifier_version TEXT NOT NULL, result TEXT NOT NULL, evidence_class TEXT NOT NULL,
          receipt_json TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS hermes_outbox(
          event_id TEXT PRIMARY KEY, event_json TEXT NOT NULL, state TEXT NOT NULL,
          attempts INTEGER NOT NULL DEFAULT 0, lease_owner TEXT, lease_until TEXT,
          created_at TEXT NOT NULL, acknowledged_at TEXT, acknowledgement_json TEXT);
        CREATE TABLE IF NOT EXISTS approval_records(
          approval_id TEXT PRIMARY KEY, task_contract_sha256 TEXT NOT NULL,
          approved_by TEXT NOT NULL, approval_source TEXT NOT NULL,
          approved_at TEXT NOT NULL, approval_note TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS avrea_tasks(
          task_id TEXT PRIMARY KEY, contract_sha256 TEXT NOT NULL, approval_id TEXT NOT NULL,
          state TEXT NOT NULL, task_json TEXT NOT NULL, result_json TEXT,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS graph_nodes(
          node_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
          node_type TEXT NOT NULL, node_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS graph_edges(
          edge_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
          source_id TEXT NOT NULL, relation TEXT NOT NULL, target_id TEXT NOT NULL,
          edge_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS engineering_metadata(
          artifact_sha256 TEXT NOT NULL, project_id TEXT NOT NULL REFERENCES projects(project_id),
          metadata_json TEXT NOT NULL, created_at TEXT NOT NULL,
          PRIMARY KEY(project_id,artifact_sha256));
        CREATE TABLE IF NOT EXISTS wiring_connections(
          project_id TEXT NOT NULL REFERENCES projects(project_id), connection_id TEXT NOT NULL,
          from_node TEXT NOT NULL, from_pin TEXT NOT NULL, to_node TEXT NOT NULL, to_pin TEXT NOT NULL,
          net_name TEXT NOT NULL, metadata_json TEXT NOT NULL,
          PRIMARY KEY(project_id,connection_id));
        CREATE INDEX IF NOT EXISTS idx_project_intakes_project ON project_intakes(project_id);
        CREATE INDEX IF NOT EXISTS idx_receipts_artifact ON verification_receipts(artifact_sha256);
        CREATE INDEX IF NOT EXISTS idx_graph_project ON graph_nodes(project_id,node_type);
        CREATE INDEX IF NOT EXISTS idx_wiring_net ON wiring_connections(project_id,net_name);
        """)
    with connect(path) as db:
        emcols=list(db.execute("PRAGMA table_info(engineering_metadata)"))
        pk=[row[1] for row in sorted((x for x in emcols if x[5]),key=lambda x:x[5])]
        if pk!=["project_id","artifact_sha256"]:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE engineering_metadata_v2(
              artifact_sha256 TEXT NOT NULL, project_id TEXT NOT NULL REFERENCES projects(project_id),
              metadata_json TEXT NOT NULL, created_at TEXT NOT NULL,
              PRIMARY KEY(project_id,artifact_sha256))""")
            db.execute("""INSERT OR IGNORE INTO engineering_metadata_v2
              SELECT artifact_sha256,project_id,metadata_json,created_at FROM engineering_metadata""")
            db.execute("DROP TABLE engineering_metadata")
            db.execute("ALTER TABLE engineering_metadata_v2 RENAME TO engineering_metadata")
            db.commit()
    with connect(path) as db:
        columns={row[1] for row in db.execute("PRAGMA table_info(github_commit_receipts)")}
        if "project_id" not in columns:
            db.execute("ALTER TABLE github_commit_receipts ADD COLUMN project_id TEXT")
        db.execute("CREATE INDEX IF NOT EXISTS idx_github_receipt_project ON github_commit_receipts(project_id)")
    return str(path)

def register_project(path, project_id, name, description=""):
    if not project_id or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}",project_id):
        raise ValueError("project_id must be a stable URL-safe identifier")
    from datetime import datetime, timezone
    with connect(path) as db:
        db.execute("INSERT INTO projects(project_id,name,description,created_at) VALUES(?,?,?,?)",
          (project_id,name,description,datetime.now(timezone.utc).isoformat()))
    return {"project_id":project_id,"status":"created"}

def attach_intake(path, project_id, intake_id):
    from datetime import datetime, timezone
    with connect(path) as db:
        if not db.execute("SELECT 1 FROM projects WHERE project_id=?",(project_id,)).fetchone():
            raise ValueError("unknown project")
        if not db.execute("SELECT 1 FROM intakes WHERE intake_id=?",(intake_id,)).fetchone():
            raise ValueError("unknown intake")
        db.execute("INSERT OR IGNORE INTO project_intakes VALUES(?,?,?)",
          (project_id,intake_id,datetime.now(timezone.utc).isoformat()))
    return {"project_id":project_id,"intake_id":intake_id,"status":"attached"}

def get_github_receipt(path, receipt_id, project_id):
    with connect(path) as db:
        row=db.execute("SELECT * FROM github_commit_receipts WHERE receipt_id=? AND project_id=?",
          (receipt_id,project_id)).fetchone()
        if not row: raise ValueError("verified GitHub receipt not found for this project")
        return {"receipt_id":row["receipt_id"],"repository":row["repository"],
          "canonical_sha":row["canonical_sha"],"api_response_sha256":row["api_response_sha256"],
          "signature_verified":bool(row["signature_verified"]),
          "verification_source":"github_rest_commit_endpoint"}

def query_projects(path, limit=100, offset=0):
    with connect(path) as db:
        rows=db.execute("""SELECT p.*,COUNT(DISTINCT pi.intake_id) intake_count,
          COUNT(DISTINCT a.intake_id || ':' || a.path) artifact_count FROM projects p
          LEFT JOIN project_intakes pi ON pi.project_id=p.project_id
          LEFT JOIN artifacts a ON a.intake_id=pi.intake_id
          GROUP BY p.project_id ORDER BY p.created_at DESC LIMIT ? OFFSET ?""",(limit,offset)).fetchall()
        return [dict(x) for x in rows]

def query_artifacts(path, project_id, limit=100, offset=0, classification=None):
    sql="""SELECT a.intake_id,a.path,a.sha256,a.size_bytes,a.classification
      FROM project_intakes pi JOIN artifacts a ON a.intake_id=pi.intake_id
      WHERE pi.project_id=?"""
    args=[project_id]
    if classification: sql+=" AND a.classification=?"; args.append(classification)
    sql+=" ORDER BY a.path LIMIT ? OFFSET ?"; args.extend([limit,offset])
    with connect(path) as db: return [dict(x) for x in db.execute(sql,args).fetchall()]

def query_artifact(path, digest):
    if not SHA.fullmatch(digest): raise ValueError("artifact SHA-256 required")
    with connect(path) as db:
        rows=db.execute("""SELECT pi.project_id,a.* FROM artifacts a
          JOIN project_intakes pi ON pi.intake_id=a.intake_id WHERE a.sha256=?""",(digest,)).fetchall()
        receipts=db.execute("SELECT receipt_id,verifier_id,verifier_version,result,evidence_class,created_at FROM verification_receipts WHERE artifact_sha256=? ORDER BY created_at DESC",(digest,)).fetchall()
        return {"sha256":digest,"occurrences":[dict(x) for x in rows],"verification_receipts":[dict(x) for x in receipts]}

def make_handler(db_path):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self,status,payload):
            raw=json.dumps(payload,sort_keys=True).encode()
            self.send_response(status); self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)
        def do_GET(self):
            token=os.environ.get("MERLIN_REGISTRY_READ_TOKEN")
            if token and self.headers.get("Authorization")!="Bearer "+token:
                return self.send_json(401,{"error":"unauthorized"})
            parsed=urlparse(self.path); parts=[x for x in parsed.path.split("/") if x]
            q=parse_qs(parsed.query)
            try:
                limit=min(max(int(q.get("limit",["100"])[0]),1),500)
                offset=max(int(q.get("offset",["0"])[0]),0)
                if parts==["health"]: return self.send_json(200,{"status":"ok","service":"merlin-registry-read-api","api_version":"1"})
                if parts==["v1","projects"]: return self.send_json(200,{"items":query_projects(db_path,limit,offset),"limit":limit,"offset":offset})
                if len(parts)==3 and parts[:2]==["v1","projects"]:
                    pid=parts[2]
                    with connect(db_path) as db: p=db.execute("SELECT * FROM projects WHERE project_id=?",(pid,)).fetchone()
                    if not p: return self.send_json(404,{"error":"project_not_found"})
                    if q.get("view")==["artifacts"]:
                        return self.send_json(200,{"project":dict(p),"items":query_artifacts(db_path,pid,limit,offset,q.get("classification",[None])[0])})
                    return self.send_json(200,dict(p))
                if len(parts)==3 and parts[:2]==["v1","artifacts"]:
                    result=query_artifact(db_path,parts[2])
                    if not result["occurrences"]: return self.send_json(404,{"error":"artifact_not_found"})
                    return self.send_json(200,result)
                return self.send_json(404,{"error":"route_not_found"})
            except (ValueError,sqlite3.Error) as exc: return self.send_json(400,{"error":str(exc)})
        def do_POST(self): return self.send_json(405,{"error":"read_only_api","message":"Registry mutations use approved service adapters, not HTTP routes."})
        def log_message(self,fmt,*args): pass
    return Handler

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="command",required=True)
    init=sub.add_parser("init"); init.add_argument("--database",default="data/merlin.sqlite3")
    create=sub.add_parser("create-project"); create.add_argument("project_id"); create.add_argument("name"); create.add_argument("--description",default=""); create.add_argument("--database",default="data/merlin.sqlite3")
    attach=sub.add_parser("attach-intake"); attach.add_argument("project_id"); attach.add_argument("intake_id"); attach.add_argument("--database",default="data/merlin.sqlite3")
    serve=sub.add_parser("serve"); serve.add_argument("--database",default="data/merlin.sqlite3"); serve.add_argument("--host",default="127.0.0.1"); serve.add_argument("--port",type=int,default=8765)
    a=p.parse_args()
    if a.command=="init": print(json.dumps({"database":initialize(a.database),"status":"initialized"}))
    elif a.command=="create-project": initialize(a.database); print(json.dumps(register_project(a.database,a.project_id,a.name,a.description)))
    elif a.command=="attach-intake": print(json.dumps(attach_intake(a.database,a.project_id,a.intake_id)))
    else:
        initialize(a.database)
        if a.host not in ("127.0.0.1","localhost","::1") and not os.environ.get("MERLIN_REGISTRY_READ_TOKEN"):
            raise SystemExit("non-loopback binding requires MERLIN_REGISTRY_READ_TOKEN")
        server=ThreadingHTTPServer((a.host,a.port),make_handler(a.database))
        print("Merlin read-only registry listening on %s:%s"%(a.host,a.port)); server.serve_forever()
if __name__=="__main__": main()
