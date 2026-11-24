"""Exact pinned producer-to-packaged-Studio synthetic acceptance experiment.

Runs only local fixture code and a loopback Studio server in disposable folders.
No actual host secrets, customer records, model inference, or ARTEX execution.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

PINNED_PRODUCER="e6546076a78ddf95ed73f1097e063f06b7a5b3b7"
ROOT=Path(__file__).resolve().parents[2]

PRODUCE=r"""
import json,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
sys.path[:0]=[str(root),str(root/"tests")]
from test_wilborn_security_recovery import RecoveryTests
from wilborn_ops.security_ledger import review_bindings, REVIEW_CLAIM
from wilborn_ops.security_dashboard import studio_snapshot
fixture=RecoveryTests()
try:
    fixture.setUp()
    h=fixture.f
    for _ in range(3):
        h.observe("auth_failure")
    report=h.observe("integrity_failure")
    b=review_bindings(report["ledger_id"],report["revision"],report["state_sha256"])
    h.ledger.acknowledge(b,h.sign(h.operator,REVIEW_CLAIM,b,h.now,"independent-reproduction"))
    h.observe("provenance_rejected")
    fixture.custody.retain(h.anchor())
    original=h.ledger.history()
    result=fixture.copy()
    recovered=fixture.open_custody().open_ledger(fixture.target,**fixture.options)
    if not result["encrypted_copy_verified"] or not result["anchor_verified"]:
        raise RuntimeError("verified recovery copy required")
    if recovered.history()!=original:
        raise RuntimeError("restored history differs from original")
    print(json.dumps(studio_snapshot(recovered),sort_keys=True,separators=(",",":")))
finally:
    fixture.doCleanups()
"""

CONSUME=r"""
import http.client,json,sys,threading
from pathlib import Path
root,summary,data=map(Path,sys.argv[1:])
sys.path.insert(0,str(root))
from server import create_server
server=create_server(data_dir=data,start_bundled=False,security_report=summary)
thread=threading.Thread(target=server.serve_forever,daemon=True)
thread.start()
try:
    def get(path,headers=None):
        connection=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=5)
        try:
            connection.request("GET",path,headers=headers or {})
            response=connection.getresponse()
            raw=response.read(262145)
            assert len(raw)<=262144
            return response.status,raw.decode("utf-8"),response.getheader("Cache-Control")
        finally:
            connection.close()
    code,html,cache=get("/studio/security")
    assert code==200 and cache=="no-store"
    for expected in ("SYNTHETIC DEMO","Revision 7","Events 5","Reviews 1",
                     "authentication_denial_burst","provenance_rejected",
                     "operator_review","Host reports signed anchor revision 7"):
        assert expected in html,expected
    assert "<script" not in html and "<form" not in html
    assert 'href="/studio/security"' in get("/studio/")[1]
    assert get("/studio/security",{"Origin":"https://example.invalid"})[0]==403
    # The page is a startup snapshot, not a live file reader or mutation API.
    summary.write_text("{}",encoding="utf-8")
    assert get("/studio/security")[1]==html
    print(json.dumps({"route_verified":True,"startup_snapshot_verified":True,
                      "cross_origin_rejected":True,"rendered_bytes":len(html.encode("utf-8"))}))
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
"""

def bounded_run(command,*,cwd,home,timeout=30):
    env={"PATH":os.environ.get("PATH","/usr/bin:/bin"),"HOME":str(home),
         "LANG":"C.UTF-8","PYTHONDONTWRITEBYTECODE":"1"}
    result=subprocess.run(command,cwd=cwd,env=env,stdin=subprocess.DEVNULL,
                          capture_output=True,timeout=timeout,check=False)
    if result.returncode!=0:
        raise RuntimeError("acceptance child failed: "+str(result.returncode)+"; "+result.stderr[-2000:].decode("utf-8","replace"))
    if len(result.stdout)>32768 or len(result.stderr)>32768:
        raise ValueError("acceptance output exceeded bound")
    return result.stdout

def run(producer,package):
    producer=Path(producer).resolve()
    package=Path(package).resolve()
    if not producer.is_dir() or not package.is_file():
        raise ValueError("pinned producer and verified package required")
    with tempfile.TemporaryDirectory(prefix="merlin-security-handoff-") as directory:
        root=Path(directory)
        revision=bounded_run(["git","rev-parse","HEAD"],cwd=producer,home=root).decode().strip()
        if revision!=PINNED_PRODUCER:
            raise ValueError("producer revision differs from accepted pin")
        bounded_run([sys.executable,str(ROOT/"scripts/verify_portable.py"),str(package)],cwd=ROOT,home=root)
        with zipfile.ZipFile(package) as archive:
            # The repository verifier has checked exact manifest inventory,
            # paths, regular files, size, and bytes before extraction.
            if not all(n.startswith("Merlin_Studio/") for n in archive.namelist()):
                raise ValueError("unexpected package root")
            archive.extractall(root/"package")
        snapshot=bounded_run([sys.executable,"-I","-B","-c",PRODUCE,str(producer)],
                             cwd=root,home=root)
        value=json.loads(snapshot)
        expected={"schema":"merlin-studio-security-summary/1","environment":"demo",
            "data_class":"synthetic","execution_authorized":False,"production_qualified":False,
            "revision":7,"accepted_events":5,"operator_reviews":1,
            "counts":{"auth_failure":3,"integrity_failure":1,"provenance_rejected":1},
            "pending_alerts":{"provenance_rejected":1},
            "active_correlations":["authentication_denial_burst"],
            "external_anchor_revision":7,"external_anchor_verified":True,
            "recent_incidents":[{"revision":2,"type":"event","kind":"auth_failure"},
                {"revision":3,"type":"event","kind":"auth_failure"},
                {"revision":4,"type":"event","kind":"auth_failure"},
                {"revision":5,"type":"event","kind":"integrity_failure"},
                {"revision":6,"type":"operator_review"},
                {"revision":7,"type":"event","kind":"provenance_rejected"}]}
        if value!=expected:
            raise ValueError("actual producer summary differs from independent scenario expectations")
        summary=root/"synthetic-summary.json"
        summary.write_bytes(snapshot)
        result=json.loads(bounded_run([sys.executable,"-I","-B","-c",CONSUME,
                    str(root/"package"/"Merlin_Studio"),str(summary),str(root/"studio-data")],
                    cwd=root,home=root))
        if any(result.get(k) is not True for k in ("route_verified","startup_snapshot_verified","cross_origin_rejected")):
            raise ValueError("package display acceptance failed")
        return {"schema":"merlin-security-handoff-evidence/1","data_class":"synthetic",
                "producer_revision":revision,"package_sha256":hashlib.sha256(package.read_bytes()).hexdigest(),
                "snapshot_sha256":hashlib.sha256(snapshot).hexdigest(),"scenario_events":5,
                "operator_reviews":1,"external_anchor_revision":7,"package_integrity_verified":True,
                "verified_encrypted_backup_handoff":True,
                **result,"production_qualified":False,"execution_authorized":False}

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer",type=Path,required=True)
    parser.add_argument("--package",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.producer,args.package),sort_keys=True))
