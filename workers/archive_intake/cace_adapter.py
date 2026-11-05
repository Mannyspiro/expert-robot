#!/usr/bin/env python3
"""CACE CLI bridge. Records run evidence; never upgrades mathematical proof qualification."""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
from canonical_registry import connect, initialize

def sha256_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def _statuses(value):
    found=[]
    if isinstance(value,dict):
        for k,v in value.items():
            if k.lower() in ("status","result") and isinstance(v,str) and v.upper() in ("PASS","FAIL","NOT_RUN","INCONCLUSIVE"):
                found.append(v.upper())
            else: found.extend(_statuses(v))
    elif isinstance(value,list):
        for item in value: found.extend(_statuses(item))
    return found

def run_cace(cace_root, experiment, timeout=300, seed=0):
    root=Path(cace_root).resolve(strict=True); source=Path(experiment).resolve(strict=True)
    if not source.is_file() or source.suffix.lower()!=".cace": raise ValueError("experiment must be an existing .cace file")
    with tempfile.TemporaryDirectory(prefix="merlin-cace-") as tmp:
        report=Path(tmp)/"report.json"
        command=[sys.executable,"-m","cace_studio.cli","run",str(source),"--seed",str(seed),"--output",str(report)]
        env={"PATH":os.environ.get("PATH",""),"HOME":tmp,"PYTHONPATH":str(root),
             "PYTHONNOUSERSITE":"1","LANG":"C.UTF-8"}
        proc=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,timeout=timeout,
                            check=False)
        data=json.loads(report.read_text()) if report.exists() else {}
        statuses=_statuses(data)
        result="passed" if proc.returncode==0 and statuses and all(x=="PASS" for x in statuses) else (
          "failed" if "FAIL" in statuses or proc.returncode==1 else "inconclusive")
        return {"result":result,"exit_code":proc.returncode,"statuses":statuses,
          "report":data,"stdout_tail":proc.stdout[-4000:],"stderr_tail":proc.stderr[-4000:],
          "experiment_sha256":sha256_file(source),"report_sha256":hashlib.sha256(
          json.dumps(data,sort_keys=True,separators=(",",":")).encode()).hexdigest()}

def persist_receipt(database, artifact_sha256, run, verifier_version):
    receipt={"receipt_version":"1.0","subject_sha256":artifact_sha256,"verifier_id":"CACE Studio CLI",
      "verifier_version":verifier_version,"result":run["result"],"evidence_class":"cace_executed_verification",
      "assumptions":[],"axioms":[],"assumptions_complete":False,"axioms_complete":False,
      "log_sha256":hashlib.sha256(
      (run["stdout_tail"]+run["stderr_tail"]).encode()).hexdigest(),
      "report_sha256":run["report_sha256"],"experiment_sha256":run["experiment_sha256"],
      "completed_at":datetime.now(timezone.utc).isoformat(),
      "formal_qualification":"not_asserted","authority_effect":"none"}
    rid="sha256:"+hashlib.sha256(json.dumps(receipt,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    with connect(database) as db:
        db.execute("INSERT OR IGNORE INTO verification_receipts VALUES(?,?,?,?,?,?,?,?)",
          (rid,artifact_sha256,receipt["verifier_id"],verifier_version,receipt["result"],
           receipt["evidence_class"],json.dumps(receipt,sort_keys=True),receipt["completed_at"]))
    return {"receipt_id":rid,**receipt}

def main():
    p=argparse.ArgumentParser(); p.add_argument("artifact_sha256"); p.add_argument("experiment",type=Path)
    p.add_argument("--cace-root",required=True); p.add_argument("--database",default="data/merlin.sqlite3")
    p.add_argument("--timeout",type=int,default=300); p.add_argument("--seed",type=int,default=0)
    p.add_argument("--version",default="unreported"); a=p.parse_args()
    if len(a.artifact_sha256)!=64: raise SystemExit("artifact SHA-256 required")
    initialize(a.database); run=run_cace(a.cace_root,a.experiment,a.timeout,a.seed)
    if a.artifact_sha256!=run["experiment_sha256"]:
        raise SystemExit("subject artifact SHA must equal the exact CACE experiment file hash; no indirect binding is assumed")
    print(json.dumps(persist_receipt(a.database,a.artifact_sha256,run,a.version),indent=2))
    if run["result"]!="passed": raise SystemExit(1)
if __name__=="__main__": main()
