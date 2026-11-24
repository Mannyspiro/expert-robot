"""Exact pinned producer-to-packaged-Studio synthetic acceptance experiment.

Runs only local fixture code and a loopback Studio server in disposable folders.
No actual host secrets, customer records, model inference, or ARTEX execution.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import zipfile

PINNED_PRODUCER="33303d5947024d10155a66a6dc6d46221088276a"
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

PRODUCE_SEGMENTS=r"""
import json,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
sys.path[:0]=[str(root),str(root/"tests")]
from test_wilborn_security_rotation import RotationTests
from wilborn_ops.security_dashboard import studio_segment_snapshot
fixture=RotationTests()
try:
    fixture.setUp()
    staged=fixture.stage()
    fixture.anchor()
    fixture.seal(staged)
    paths=[fixture.f.path,fixture.a.directory/"history.sqlite3",
           fixture.directory/"successor.sqlite3"]
    before=[p.read_bytes() for p in paths]
    result=studio_segment_snapshot(fixture.f.path,fixture.a.directory,fixture.directory,
        **fixture.options,rotation_review_keys=fixture.reviewer.trust)
    if before!=[p.read_bytes() for p in paths]:
        raise RuntimeError("segment view changed source or encrypted archive")
    print(json.dumps(result,sort_keys=True,separators=(",",":")))
finally:
    fixture.doCleanups()
"""

PRODUCE_LINEAGE=r"""
import json,os,sys
from pathlib import Path
from uuid import uuid4
root=Path(sys.argv[1]).resolve()
sys.path[:0]=[str(root),str(root/"tests")]
from test_wilborn_security_handover import HandoverTests
from test_wilborn_attested_integration import Signer
from wilborn_ops.security_archive import ARCHIVE_CLAIM,stage_archive,seal_archive
from wilborn_ops.security_rotation import CLAIM as ROTATION_CLAIM,stage_rotation,seal_rotation
from wilborn_ops.security_handover import CLAIM as HANDOVER_CLAIM,WriterHandover
from wilborn_ops.security_recovery import AnchorCustody
from wilborn_ops.security_ledger import SecurityLedger,MAX_HISTORY,ANCHOR_CLAIM,EVENT_CLAIM,anchor_bindings
from wilborn_ops.security_monitor import SecurityEvent
from wilborn_ops.security_dashboard import studio_lineage_snapshot
fixture=HandoverTests()
try:
    fixture.setUp()
    f,r=fixture.f,fixture.r
    first=fixture.control
    middle=first.open_writer(fixture.activate())
    fixture.observe(middle,"tool_denied")
    fixture.observe(middle,"integrity_failure")
    r.anchor()
    workspace=r.a.fixture.root
    archive_reviewer=Signer("lineage-package-archive-reviewer")
    archive=workspace/"lineage-archive"
    staged_archive=stage_archive(middle._path,archive,custody=r.successor,options=r.new_options)
    seal_archive(archive,custody=r.successor,options=r.new_options,
        reviewer_keys=archive_reviewer.trust,review_attestation=f.sign(archive_reviewer,ARCHIVE_CLAIM,
            staged_archive["review_bindings"],f.now,"independent-reproduction"))
    sensor=Signer("lineage-package-sensor")
    operator=Signer("lineage-package-operator")
    anchorer=Signer("lineage-package-anchor")
    rotation_reviewer=Signer("lineage-package-rotation-reviewer")
    handover_reviewer=Signer("lineage-package-handover-reviewer")
    custody_directory=workspace/"lineage-custody"
    custody_directory.mkdir(mode=0o700)
    custody=AnchorCustody(custody_directory,ledger_id=str(uuid4()),trust=anchorer.trust,
        requester_id="fixture-worker",clock=lambda:f.now,create=True)
    options=dict(master_key=os.urandom(32),key_id="lineage-package-fixture-key",
        sensor_keys=sensor.trust,operator_keys=operator.trust)
    rotation_options=dict(predecessor=r.successor,successor=custody,old_options=r.new_options,
        new_options=options,archive_review_keys=archive_reviewer.trust,reserve_revisions=MAX_HISTORY-3)
    stage=r.a.fixture.restore_dir/"lineage-stage"
    staged=stage_rotation(middle._path,archive,stage,**rotation_options)
    candidate=SecurityLedger(stage/"successor.sqlite3",ledger_id=custody._id,
        requester_id="fixture-worker",clock=lambda:f.now,**options)
    report=candidate.report()
    bindings=anchor_bindings(custody._id,report["revision"],report["state_sha256"])
    custody.retain({"bindings":bindings,"attestation":f.sign(anchorer,ANCHOR_CLAIM,bindings,
                                                            f.now,"independent-reproduction")})
    seal_rotation(middle._path,archive,stage,**rotation_options,
        rotation_review_keys=rotation_reviewer.trust,review_attestation=f.sign(rotation_reviewer,
            ROTATION_CLAIM,staged["review_bindings"],f.now,"independent-reproduction"))
    directory=workspace/"lineage-control"
    directory.mkdir(mode=0o700)
    latest=WriterHandover(directory,handover_id=str(uuid4()),source=middle._path,archive=archive,
        stage=stage,**rotation_options,rotation_review_keys=rotation_reviewer.trust,
        handover_review_keys=handover_reviewer.trust,previous=first,create=True,owner_id=str(uuid4()))
    bindings=latest.prepare()
    lease=latest.activate(f.sign(handover_reviewer,HANDOVER_CLAIM,bindings,f.now,"independent-reproduction"))
    writer=latest.open_writer(lease)
    writer.observe_local(SecurityEvent("auth_failure","demo","synthetic"),
        lambda b,now:f.sign(sensor,EVENT_CLAIM,b,now,"artifact-integrity"))
    for stale in (f.ledger,middle):
        try:
            stale.observe_local(SecurityEvent("tool_denied","demo","synthetic"),
                lambda *_:(_ for _ in ()).throw(RuntimeError("retired writer signer reached")))
        except PermissionError:
            pass
        else:
            raise RuntimeError("retired generation accepted a write")
    paths=[f.path,middle._path,writer._path,r.a.directory/"history.sqlite3",archive/"history.sqlite3",
           first._path,latest._path]
    before=[p.read_bytes() for p in paths]
    result=studio_lineage_snapshot(latest)
    if before!=[p.read_bytes() for p in paths]:
        raise RuntimeError("active lineage view changed source, ownership or archive")
    print(json.dumps(result,sort_keys=True,separators=(",",":")))
finally:
    fixture.doCleanups()
"""

CONSUME=r"""
import http.client,json,sys,threading
from pathlib import Path
root,summary,data=map(Path,sys.argv[1:])
sys.path.insert(0,str(root))
from server import create_server
schema=json.loads(summary.read_text(encoding="utf-8"))["schema"]
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
    phrases=("SYNTHETIC DEMO","Revision 7","Events 5","Reviews 1",
                     "authentication_denial_burst","provenance_rejected",
                     "operator_review","Host reports signed anchor revision 7") if schema.endswith("/1") else (
                     "SYNTHETIC DEMO","Staged rotation review","Predecessor archive",
                     "Successor genesis","Segment revision 3","Segment revision 1",
                     "Total events 2","Total reviews 0","integrity_failure",
                     "Pending predecessor alerts","Writer handover not verified",
                     "Successor not activated","Host reports signed anchor revision 3") if schema.endswith("/2") else (
                     "SYNTHETIC DEMO","Active lineage review","Archived predecessor · Segment 0",
                     "Archived predecessor · Segment 1","Active successor · Segment 2",
                     "Segment revision 3","Segment revision 2","Total events 5","Total reviews 0",
                     "integrity_failure","Pending archived alerts","Pending active alerts",
                     "Host reports local writer handover verified","Active synthetic segment 2",
                     "Ownership epoch 1","Host-reported active lineage","does not independently verify",
                     "reported anchor may precede its current revision","No execution authorized")
    for expected in phrases:
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


def _repository_module(relative):
    """Load a trusted repository module without consulting the package or cwd."""
    path=ROOT/relative
    spec=importlib.util.spec_from_file_location("merlin_handoff_"+path.stem,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_package_source(package):
    """Require a valid source-only ZIP whose payload matches this checkout."""
    builder=_repository_module("portable/build_portable.py")
    verifier=_repository_module("scripts/verify_portable.py")
    verifier.verify(package)
    payload,origins=builder.collect_sources()
    prefix=builder.ARCHIVE_ROOT+"/"
    with zipfile.ZipFile(package) as archive:
        expected={prefix+name for name in payload}|{prefix+"PACKAGE_MANIFEST.json"}
        if set(archive.namelist())!=expected:
            raise ValueError("package inventory differs from current Studio source")
        manifest=json.loads(archive.read(prefix+"PACKAGE_MANIFEST.json"))
        native=manifest.get("native_protocol")
        if (manifest.get("archive_root")!=builder.ARCHIVE_ROOT
                or native!={"included":False,"scope":"protocol_source_only","platform":None}
                or native.get("included") is not False
                or any(manifest.get(name) is not False for name in
                       ("contains_model_weights","contains_python_runtime",
                        "contains_inference_engine","contains_user_state"))):
            raise ValueError("source-only package contract required")
        records={entry["path"]:entry for entry in manifest["files"]}
        for name,data in payload.items():
            if archive.read(prefix+name)!=data:
                raise ValueError("package payload differs from current Studio source: "+name)
            # Origin annotations are compared with the builder's fixed mapping;
            # manifest-provided paths are never opened on the host.
            if records[name].get("source")!=origins[name]:
                raise ValueError("package origin differs from current Studio source: "+name)
        for name in (*payload,"PACKAGE_MANIFEST.json"):
            mode=0o755 if name in builder.EXECUTABLES else 0o644
            if archive.getinfo(prefix+name).external_attr>>16!=stat.S_IFREG|mode:
                raise ValueError("package mode differs from current Studio source: "+name)
    return True


def run(producer,package):
    producer=Path(producer).resolve()
    package=Path(package).resolve()
    if not producer.is_dir() or not package.is_file():
        raise ValueError("pinned producer and verified package required")
    source_verified=verify_package_source(package)
    with tempfile.TemporaryDirectory(prefix="merlin-security-handoff-") as directory:
        root=Path(directory)
        revision=bounded_run(["git","rev-parse","HEAD"],cwd=producer,home=root).decode().strip()
        if revision!=PINNED_PRODUCER:
            raise ValueError("producer revision differs from accepted pin")
        if bounded_run(["git","status","--porcelain","--untracked-files=all"],cwd=producer,home=root).strip():
            raise ValueError("producer worktree differs from pinned commit")
        with zipfile.ZipFile(package) as archive:
            # Both manifest integrity and the fixed current-source inventory,
            # payload bytes, origins and modes were checked before producer use.
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
        segmented=bounded_run([sys.executable,"-I","-B","-c",PRODUCE_SEGMENTS,str(producer)],
                              cwd=root,home=root)
        value=json.loads(segmented)
        expected_segments={"schema":"merlin-studio-security-summary/2","environment":"demo",
            "data_class":"synthetic","execution_authorized":False,"production_qualified":False,
            "activation_authorized":False,"writer_handover_verified":False,"review_scope":"staged_rotation",
            "accepted_events":2,"operator_reviews":0,
            "counts":{"auth_failure":1,"integrity_failure":1},"pending_alerts":{"integrity_failure":1},
            "segments":[{"segment_index":0,"role":"predecessor_archive","revision":3,
                "accepted_events":2,"operator_reviews":0,"counts":{"auth_failure":1,"integrity_failure":1},
                "pending_alerts":{"integrity_failure":1},"active_correlations":[],
                "external_anchor_revision":3,"external_anchor_verified":True},
                {"segment_index":1,"role":"successor_genesis","revision":1,
                "accepted_events":0,"operator_reviews":0,"counts":{},"pending_alerts":{},
                "active_correlations":[],"external_anchor_revision":1,"external_anchor_verified":True}],
            "recent_incidents":[{"segment_index":0,"revision":2,"type":"event","kind":"auth_failure"},
                                {"segment_index":0,"revision":3,"type":"event","kind":"integrity_failure"}]}
        if value!=expected_segments:
            raise ValueError("actual segment export differs from independent scenario expectations")
        summary=root/"synthetic-segments.json"
        summary.write_bytes(segmented)
        segment_result=json.loads(bounded_run([sys.executable,"-I","-B","-c",CONSUME,
                    str(root/"package"/"Merlin_Studio"),str(summary),str(root/"segments-studio-data")],
                    cwd=root,home=root))
        if any(segment_result.get(k) is not True for k in ("route_verified","startup_snapshot_verified","cross_origin_rejected")):
            raise ValueError("segmented package display acceptance failed")
        lineage=bounded_run([sys.executable,"-I","-B","-c",PRODUCE_LINEAGE,str(producer)],
                            cwd=root,home=root)
        value=json.loads(lineage)
        expected_lineage={"schema":"merlin-studio-security-summary/3","environment":"demo",
            "data_class":"synthetic","execution_authorized":False,"production_qualified":False,
            "activation_authorized":False,"writer_handover_verified":True,"review_scope":"active_lineage",
            "active_segment_index":2,"ownership_epoch":1,"accepted_events":5,"operator_reviews":0,
            "counts":{"auth_failure":2,"integrity_failure":2,"tool_denied":1},
            "pending_alerts":{"integrity_failure":2},
            "segments":[{"segment_index":0,"role":"archived_predecessor","revision":3,
                "accepted_events":2,"operator_reviews":0,"counts":{"auth_failure":1,"integrity_failure":1},
                "pending_alerts":{"integrity_failure":1},"active_correlations":[],
                "external_anchor_revision":3,"external_anchor_verified":True},
                {"segment_index":1,"role":"archived_predecessor","revision":3,
                "accepted_events":2,"operator_reviews":0,"counts":{"tool_denied":1,"integrity_failure":1},
                "pending_alerts":{"integrity_failure":1},"active_correlations":[],
                "external_anchor_revision":3,"external_anchor_verified":True},
                {"segment_index":2,"role":"active_successor","revision":2,
                "accepted_events":1,"operator_reviews":0,"counts":{"auth_failure":1},
                "pending_alerts":{},"active_correlations":[],
                "external_anchor_revision":1,"external_anchor_verified":True}],
            "recent_incidents":[{"segment_index":0,"revision":2,"type":"event","kind":"auth_failure"},
                {"segment_index":0,"revision":3,"type":"event","kind":"integrity_failure"},
                {"segment_index":1,"revision":2,"type":"event","kind":"tool_denied"},
                {"segment_index":1,"revision":3,"type":"event","kind":"integrity_failure"},
                {"segment_index":2,"revision":2,"type":"event","kind":"auth_failure"}]}
        if value!=expected_lineage:
            raise ValueError("actual lineage export differs from independent scenario expectations")
        summary=root/"synthetic-lineage.json"
        summary.write_bytes(lineage)
        lineage_result=json.loads(bounded_run([sys.executable,"-I","-B","-c",CONSUME,
                    str(root/"package"/"Merlin_Studio"),str(summary),str(root/"lineage-studio-data")],
                    cwd=root,home=root))
        if any(lineage_result.get(k) is not True for k in ("route_verified","startup_snapshot_verified","cross_origin_rejected")):
            raise ValueError("active lineage package display acceptance failed")
        if bounded_run(["git","status","--porcelain","--untracked-files=all"],cwd=producer,home=root).strip():
            raise ValueError("producer changed during package acceptance")
        return {"schema":"merlin-security-handoff-evidence/3","data_class":"synthetic",
                "producer_revision":revision,"package_sha256":hashlib.sha256(package.read_bytes()).hexdigest(),
                "snapshot_sha256":hashlib.sha256(snapshot).hexdigest(),"scenario_events":5,
                "operator_reviews":1,"external_anchor_revision":7,"package_integrity_verified":True,
                "package_source_verified":source_verified,
                "verified_encrypted_backup_handoff":True,
                "staged_segment_review":{"snapshot_sha256":hashlib.sha256(segmented).hexdigest(),
                    "segments":2,"scenario_events":2,"pending_predecessor_alerts":1,
                    "source_and_archive_preserved":True,"writer_handover_verified":False,
                    "activation_authorized":False,**segment_result},
                "active_lineage_review":{"snapshot_sha256":hashlib.sha256(lineage).hexdigest(),
                    "segments":3,"scenario_events":5,"pending_archived_alerts":2,
                    "active_segment_index":2,"ownership_epoch":1,"stale_writers_rejected":2,
                    "source_and_archive_preserved":True,"writer_handover_verified":True,
                    "activation_authorized":False,**lineage_result},
                **result,"production_qualified":False,"execution_authorized":False}

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer",type=Path,required=True)
    parser.add_argument("--package",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.producer,args.package),sort_keys=True))
