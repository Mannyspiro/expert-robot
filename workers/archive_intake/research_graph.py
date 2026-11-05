#!/usr/bin/env python3
"""Build a research graph from canonical registry artifacts and verification receipts."""
from __future__ import annotations
import argparse, hashlib, json
from canonical_registry import connect, initialize

def nid(kind,key): return "urn:merlin:"+kind+":"+hashlib.sha256((kind+"\0"+key).encode()).hexdigest()
def export_graph(database,project_id):
    nodes=[]; edges=[]
    def node(kind,key,**attrs):
        ident=nid(kind,key); nodes.append({"id":ident,"type":kind,**attrs}); return ident
    def edge(source,relation,target):
        key=source+"|"+relation+"|"+target
        edges.append({"id":nid("edge",key),"from":source,"relation":relation,"to":target})
    with connect(database) as db:
        project=db.execute("SELECT * FROM projects WHERE project_id=?",(project_id,)).fetchone()
        if not project: raise ValueError("unknown project")
        p=node("Project",project_id,project_id=project_id,name=project["name"])
        rows=db.execute("""SELECT a.intake_id,a.path,a.sha256,a.size_bytes,a.classification
          FROM project_intakes pi JOIN artifacts a ON a.intake_id=pi.intake_id WHERE pi.project_id=?""",(project_id,)).fetchall()
        for a in rows:
            artifact=node("Artifact",a["sha256"],sha256=a["sha256"])
            occurrence=node("ArtifactOccurrence",a["intake_id"]+"|"+a["path"],path=a["path"],classification=a["classification"])
            edge(p,"containsArtifact",occurrence); edge(occurrence,"hasContent",artifact)
            receipts=db.execute("SELECT * FROM verification_receipts WHERE artifact_sha256=?",(a["sha256"],)).fetchall()
            for rec in receipts:
                r=node("VerificationReceipt",rec["receipt_id"],receipt_id=rec["receipt_id"],
                  verifier_id=rec["verifier_id"],result=rec["result"],evidence_class=rec["evidence_class"])
                edge(artifact,"hasVerification",r)
                if rec["result"]=="passed": edge(r,"supports",artifact)
    unique={x["id"]:x for x in nodes}
    return {"graph_version":"1.0","project_id":project_id,"nodes":list(unique.values()),"edges":edges}
def main():
    p=argparse.ArgumentParser(); p.add_argument("project_id"); p.add_argument("--database",default="data/merlin.sqlite3"); p.add_argument("--out",required=True)
    a=p.parse_args(); initialize(a.database); g=export_graph(a.database,a.project_id)
    with open(a.out,"w") as f: json.dump(g,f,indent=2,sort_keys=True); f.write("\n")
    print(json.dumps({"status":"exported","nodes":len(g["nodes"]),"edges":len(g["edges"]),"out":a.out}))
if __name__=="__main__": main()
