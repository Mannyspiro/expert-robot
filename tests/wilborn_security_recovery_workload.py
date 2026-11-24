"""Fixed synthetic workload; report measured timings, not production claims."""
from collections import Counter
import json
import platform
import sqlite3
from time import perf_counter
import cryptography
import test_wilborn_security_recovery as fixtures

SIZES=(16,64,128,256)
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
                if perf_counter()-started>100:
                    raise TimeoutError("fixed synthetic workload exceeded time budget")
                kind=EVENTS[index%len(EVENTS)]
                f.observe(kind)
                counts[kind]+=1
            ingest_seconds=perf_counter()-stage_start
            read_start=perf_counter()
            report=f.ledger.report()
            history=f.ledger.history()
            verify_seconds=perf_counter()-read_start
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
                            "database_bytes":db_bytes})
            previous=size
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
        if perf_counter()-started>110:
            raise TimeoutError("workload and recovery exceeded budget")
        return {"schema":"wilborn-security-recovery-workload/1","data_class":"synthetic",
                "environment":{"python":platform.python_version(),"system":platform.system(),
                               "machine":platform.machine(),"sqlite":sqlite3.sqlite_version,
                               "cryptography":cryptography.__version__},
                "measurements":records,"recovery":{"events":SIZES[-1],
                   "copy_seconds":round(copy_seconds,6),"reopen_history_seconds":round(reopen_seconds,6),
                   "encrypted_history_exact":True,"anchor_verified":True},
                "measurement_scope":"single CI host, one fixed workload, no production latency SLA",
                "production_qualified":False,"execution_authorized":False}
    finally:
        fixture.doCleanups()

if __name__=="__main__":
    print(json.dumps(run(),sort_keys=True))
