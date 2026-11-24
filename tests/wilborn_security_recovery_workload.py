"""Fixed synthetic workload; report measured timings, not production claims."""
from collections import Counter
from statistics import median
import json
import os
from uuid import uuid4
import platform
import sqlite3
from time import perf_counter
import cryptography
import test_wilborn_security_recovery as fixtures
from test_wilborn_attested_integration import Signer
from wilborn_ops.security_ledger import MAX_HISTORY, REVIEW_CLAIM, review_bindings, SecurityLedger, ANCHOR_CLAIM, anchor_bindings
from wilborn_ops.security_recovery import AnchorCustody
from wilborn_ops.security_rotation import CLAIM as ROTATION_CLAIM, stage_rotation, seal_rotation
from wilborn_ops.security_archive import ARCHIVE_CLAIM, retention_status, stage_archive, seal_archive, inspect_archive

SIZES=(16,64,128,256,512,1023)
assert SIZES[-1]+1==MAX_HISTORY
EVENTS=("auth_failure","tool_denied","integrity_failure","provenance_rejected")
MAX_DB_BYTES=64*1024*1024

def run():
    fixture=fixtures.RecoveryTests()
    try:
        fixture.setUp()
        f=fixture.f
        counts=Counter()
        records=[]
        previous=0
        started=perf_counter()
        for size in SIZES:
            stage_start=perf_counter()
            for index in range(previous,size):
                if perf_counter()-started>210:
                    raise TimeoutError("fixed synthetic workload exceeded time budget")
                kind=EVENTS[index%len(EVENTS)]
                f.observe(kind)
                counts[kind]+=1
            ingest_seconds=perf_counter()-stage_start
            # Paired reads of the same immutable revision; alternate order
            # to reduce warm-cache/order bias. No cached verification state.
            separate=[]
            combined=[]
            for trial in range(5):
                for mode in (("separate","combined") if trial%2==0 else ("combined","separate")):
                    start=perf_counter()
                    if mode=="separate":
                        reference=(f.ledger.report(),f.ledger.history())
                        separate.append(perf_counter()-start)
                    else:
                        actual=f.ledger.review_snapshot()
                        combined.append(perf_counter()-start)
                if reference!=actual:
                    raise RuntimeError("combined snapshot differs from separate verified reads")
            report,history=actual
            verify_seconds=median(separate)
            combined_seconds=median(combined)
            if report["counts"]!=dict(counts) or report["revision"]!=size+1 or len(history["entries"])!=size:
                raise RuntimeError("workload invariant failed")
            if [entry["kind"] for entry in history["entries"]]!=[EVENTS[i%len(EVENTS)] for i in range(size)]:
                raise RuntimeError("history differs from fixed event order")
            db_bytes=f.path.stat().st_size
            if not 0<db_bytes<=MAX_DB_BYTES:
                raise ValueError("database size budget exceeded")
            records.append({"events":size,"revision":size+1,"stage_events":size-previous,
                            "stage_ingest_seconds":round(ingest_seconds,6),
                            "mean_ingest_ms":round(1000*ingest_seconds/(size-previous),3),
                            "verify_report_and_history_ms":round(1000*verify_seconds,3),
                            "combined_snapshot_ms":round(1000*combined_seconds,3),
                            "combined_snapshot_speedup":round(verify_seconds/combined_seconds,3),
                            "paired_trials":5,
                            "database_bytes":db_bytes})
            previous=size
        # Exercise the actual capacity boundary through the signed APIs.
        # No direct SQL fixture or shortened chain can satisfy this experiment.
        before=f.ledger.report()
        for operation in (
            lambda:f.observe("tool_denied"),
            lambda:f.ledger.acknowledge(
                review_bindings(before["ledger_id"],before["revision"],before["state_sha256"]),
                f.sign(f.operator,REVIEW_CLAIM,
                    review_bindings(before["ledger_id"],before["revision"],before["state_sha256"]),
                    f.now,"independent-reproduction"))):
            try:
                operation()
            except OverflowError:
                pass
            else:
                raise RuntimeError("write accepted beyond fixed revision cap")
        if f.ledger.report()!=before or f.ledger.history()!=history:
            raise RuntimeError("capacity rejection changed the protected history")
        advisory=retention_status(f.ledger,reserve_revisions=64)
        if not advisory["capacity_exhausted"] or not advisory["archive_review_due"]:
            raise RuntimeError("retention advisory differs from actual revision cap")
        # Verify actual encrypted recovery against an independently signed
        # retained fixture anchor; do not export the receipt or private key.
        fixture.custody.retain(f.anchor())
        start=perf_counter()
        copied=fixture.copy()
        copy_seconds=perf_counter()-start
        start=perf_counter()
        restored=fixture.open_custody().open_ledger(fixture.target,**fixture.options)
        restored_history=restored.history()
        reopen_seconds=perf_counter()-start
        if restored_history!=history or copied["state_sha256"]!=report["state_sha256"]:
            raise RuntimeError("recovery history differs from pre-copy reference")
        # Independently review a second retained archive, then confirm it
        # remains inspectable after the live anchor's freshness expires.
        reviewer=Signer("fixture-archive-reviewer")
        directory=fixture.restore_dir/"reviewed-archive"
        start=perf_counter()
        staged=stage_archive(f.path,directory,custody=fixture.custody,options=fixture.options)
        signed=f.sign(reviewer,ARCHIVE_CLAIM,staged["review_bindings"],f.now,"independent-reproduction")
        reviewed=seal_archive(directory,custody=fixture.custody,options=fixture.options,
                             reviewer_keys=reviewer.trust,review_attestation=signed)
        archive_seconds=perf_counter()-start
        f.now+=86401
        start=perf_counter()
        inspected=inspect_archive(directory,custody=fixture.custody,options=fixture.options,
                                  reviewer_keys=reviewer.trust)
        inspect_seconds=perf_counter()-start
        if reviewed!=inspected or inspected["current_recovery_authorized"] or inspected["deletion_authorized"]:
            raise RuntimeError("historical archive evidence was not preserved or became authorizing")
        # A separately reviewed historical archive can remain valid after
        # expiry. Rotation, in contrast, requires freshly retained live tips.
        fixture.custody.retain(f.anchor())
        successor_id=str(uuid4())
        successor_sensor=Signer("fixture-rotation-sensor")
        successor_operator=Signer("fixture-rotation-operator")
        successor_anchor=Signer("fixture-rotation-anchor")
        rotation_reviewer=Signer("fixture-rotation-reviewer")
        successor_directory=fixture.root/"rotation-custody"
        successor_directory.mkdir(mode=0o700)
        successor=AnchorCustody(successor_directory,ledger_id=successor_id,
            trust=successor_anchor.trust,requester_id="fixture-worker",
            clock=lambda:f.now,create=True)
        successor_options=dict(master_key=os.urandom(32),key_id="fixture-rotation-key",
            sensor_keys=successor_sensor.trust,operator_keys=successor_operator.trust)
        rotation_directory=fixture.restore_dir/"rotation"
        rotation_options=dict(predecessor=fixture.custody,successor=successor,
            old_options=fixture.options,new_options=successor_options,
            archive_review_keys=reviewer.trust,reserve_revisions=64)
        old_bytes=f.path.read_bytes()
        archive_bytes=(directory/"history.sqlite3").read_bytes()
        start=perf_counter()
        rotation=stage_rotation(f.path,directory,rotation_directory,**rotation_options)
        candidate=SecurityLedger(rotation_directory/"successor.sqlite3",
            ledger_id=successor_id,requester_id="fixture-worker",clock=lambda:f.now,**successor_options)
        genesis=candidate.report()
        anchor=anchor_bindings(successor_id,genesis["revision"],genesis["state_sha256"])
        successor.retain({"bindings":anchor,"attestation":f.sign(successor_anchor,ANCHOR_CLAIM,
            anchor,f.now,"independent-reproduction")})
        signed_rotation=f.sign(rotation_reviewer,ROTATION_CLAIM,rotation["review_bindings"],
                               f.now,"independent-reproduction")
        rotated=seal_rotation(f.path,directory,rotation_directory,**rotation_options,
            rotation_review_keys=rotation_reviewer.trust,review_attestation=signed_rotation)
        rotation_seconds=perf_counter()-start
        if (rotated["predecessor_events"]!=SIZES[-1] or
                rotated["predecessor_unresolved_alerts"]!=before["pending_alerts"] or
                rotated["predecessor_alerts_resolved"] or rotated["activation_authorized"] or
                rotated["deletion_authorized"] or not rotated["successor_genesis_verified"] or
                candidate.history()["entries"]!=[] or f.path.read_bytes()!=old_bytes or
                (directory/"history.sqlite3").read_bytes()!=archive_bytes):
            raise RuntimeError("reviewed rotation did not preserve exact predecessor or untouched genesis")
        if perf_counter()-started>230:
            raise TimeoutError("workload, archival and rotation exceeded budget")
        return {"schema":"wilborn-security-recovery-workload/1","data_class":"synthetic",
                "environment":{"python":platform.python_version(),"system":platform.system(),
                               "machine":platform.machine(),"sqlite":sqlite3.sqlite_version,
                               "cryptography":cryptography.__version__},
                "measurements":records,"recovery":{"events":SIZES[-1],
                   "copy_seconds":round(copy_seconds,6),"reopen_history_seconds":round(reopen_seconds,6),
                   "encrypted_history_exact":True,"anchor_verified":True},
                "capacity":{"revision_limit":MAX_HISTORY,"event_and_review_overflow_rejected":True,
                            "history_preserved":True,"archive_review_due":True},
                "archive":{"review_seconds":round(archive_seconds,6),
                           "historical_inspection_seconds":round(inspect_seconds,6),
                           "encrypted_history_verified":True,"expired_anchor_inspectable":True,
                           "current_recovery_authorized":False,"deletion_authorized":False},
                "rotation":{"review_seconds":round(rotation_seconds,6),
                            "predecessor_events":rotated["predecessor_events"],
                            "unresolved_alerts_preserved":True,"archive_bytes_preserved":True,
                            "successor_revision":genesis["revision"],"activation_authorized":False},
                "measurement_scope":"single CI host, one fixed workload, no production latency SLA",
                "production_qualified":False,"execution_authorized":False}
    finally:
        fixture.doCleanups()

if __name__=="__main__":
    print(json.dumps(run(),sort_keys=True))
