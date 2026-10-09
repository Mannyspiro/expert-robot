#!/usr/bin/env python3
"""OCI-only research scheduler. No GitHub Actions, no Docker socket in jobs.

This trusted host-side wrapper fetches only an explicitly selected protected
branch, creates a disposable detached worktree and runs one registered
research experiment inside a read-only, networkless container.

The host wrapper requires Docker access; NEVER run it from untrusted PR code.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

SHA40=re.compile(r"[0-9a-f]{40}\Z")
SHA64=re.compile(r"[0-9a-f]{64}\Z")
BRANCH=re.compile(r"refs/heads/[A-Za-z0-9][A-Za-z0-9._/-]{0,120}\Z")
REPO_NAME="Mannyspiro/expert-robot"
# Explicit no-mutation CI. Repo and experiment container cannot request writes.
ALLOWED_KEYS={
  "schema_version","experiment","repository","source_commit","date_utc",
  "policy_sha256","episode_id","selected_route","prior_receipt_used",
  "research_evidence","result_sha256","candidate",
  "next_route_recommendation","conclusion","external_network_used",
  "avrea_credits_reserved","scientific_truth_or_formal_verification_claimed",
  "promotion_authorized","authority_expanded"
}
MAX_REPORT=65536
MAX_EXPERIMENT_SECONDS=240

def run(argv,*,timeout=90,env=None):
    p=subprocess.run(argv,check=False,capture_output=True,text=True,
                     timeout=timeout,env=env)
    if p.returncode:
        # A failed Git command can mention remote URLs and credentials.
        raise RuntimeError("host operation failed: "+argv[0]+
                           " (status "+str(p.returncode)+")")
    return p.stdout.strip()

def require_sha(x):
    if not isinstance(x,str) or SHA40.fullmatch(x) is None:
        raise ValueError("invalid full source commit SHA")
    return x

def approved_ref(value):
    if not isinstance(value,str) or BRANCH.fullmatch(value) is None:
        raise ValueError("only a literal refs/heads/ branch is allowed")
    if ".." in value or "//" in value or value.endswith(".lock"):
        raise ValueError("unsafe Git ref")
    return value

def require_directory(path):
    p=Path(path)
    if p.is_symlink() or not p.is_dir():
        raise ValueError("missing or symlinked directory")
    return p.resolve()

def assert_remote(repository, expected_url):
    actual=run(["git","-C",str(repository),"remote","get-url","origin"])
    if actual!=expected_url or not expected_url.startswith(
       "ssh://git@127.0.0.1:2222/"
    ) or not expected_url.endswith("/expert-robot.git"):
        raise ValueError("origin not approved local private Forgejo SSH mirror")

def validate_receipt(receipt,sha,utc_day):
    require_sha(sha)
    if not isinstance(receipt,dict) or set(receipt)!=ALLOWED_KEYS:
        raise ValueError("unexpected or absent receipt keys")
    if (receipt["schema_version"]!=1 or receipt["repository"]!=REPO_NAME or
        receipt["source_commit"]!=sha or receipt["date_utc"]!=utc_day or
        receipt["conclusion"]!="bounded_offline_experiment_only" or
        receipt["external_network_used"] is not False or
        receipt["avrea_credits_reserved"]!=0 or
        receipt["promotion_authorized"] is not False or
        receipt["authority_expanded"] is not False or
        receipt["scientific_truth_or_formal_verification_claimed"] is not False or
        receipt["candidate"].get("promotion_authorized") is not False):
        raise ValueError("receipt claims forbidden execution, scope or authority")
    if any(SHA64.fullmatch(str(receipt.get(k,"")))==None for k in
           ("policy_sha256","result_sha256","episode_id")):
        raise ValueError("invalid source-independent evidence digest")
    if receipt["selected_route"] not in (
        "reaction-conservation","crnt-assumption-search",
        "enzyme-equilibrium-search","parser-contract-search"):
        raise ValueError("unregistered research route")
    if receipt["candidate"].get("lean_gate")!="requires_exact_kernel_axiom_audit":
        raise ValueError("candidate improperly bypassed proof checks")
    return True

def sealed_report(path,sha,day):
    path=Path(path)
    if path.is_symlink() or path.stat().st_size>MAX_REPORT:
        raise ValueError("missing/unbounded report")
    data=path.read_bytes()
    r=json.loads(data)
    validate_receipt(r,sha,day)
    return r,hashlib.sha256(data).hexdigest()

def acquire_lock(path):
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    return fd

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--repo",required=True,type=Path,
                   help="Approved local checkout, pulled from private Forgejo")
    a.add_argument("--origin",required=True,
                   help="Exact ssh://git@127.0.0.1:2222/owner/expert-robot.git")
    a.add_argument("--ref",default="refs/heads/main")
    a.add_argument("--state",type=Path,default=Path("/var/lib/oci-research"))
    a.add_argument("--image",default="docker.io/library/python:3.12-alpine")
    a.add_argument("--date",help="UTC YYYY-MM-DD, ordinarily omitted")
    ns=a.parse_args()
    if os.geteuid()!=0:
        raise SystemExit("trusted OCI host worker must run as root for Docker; guest is nobody")
    branch=approved_ref(ns.ref)
    if not ns.image.startswith("docker.io/library/python:3.12-alpine"):
        raise ValueError("refusing unknown execution image")
    # Pin an OCI image digest before production qualification.
    repo=require_directory(ns.repo)
    state=ns.state
    if state.is_symlink():raise ValueError("state cannot be a symlink")
    state.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.chmod(state,0o700)
    lock=acquire_lock(state/"oci-worker.lock")
    try:
        today=dt.date.fromisoformat(ns.date) if ns.date else dt.datetime.now(dt.timezone.utc).date()
        day=today.isoformat()
        final=state/"receipts"/(day+".json")
        if final.exists():
            # Do not use duplicate daily episodes to inflate evidence counts.
            print(json.dumps({"status":"already_observed_today","path":str(final)}))
            return
        assert_remote(repo,ns.origin)
        disk=shutil.disk_usage(state)
        if disk.free<2*1024**3:raise RuntimeError("less than 2 GiB free: fail closed")
        # Host-only trusted fetch, no repo credentials given to Docker.
        run(["git","-c","core.hooksPath=/dev/null","-C",str(repo),
             "fetch","--no-tags","--depth","1","origin",branch],timeout=120)
        sha=require_sha(run(["git","-C",str(repo),"rev-parse","FETCH_HEAD"]))
        with tempfile.TemporaryDirectory(prefix="oci-research-",
                                         dir=str(state)) as tmp:
            tmp=Path(tmp)
            checkout=tmp/"checkout"
            output=tmp/"result"
            # Local detached working tree, never executes repo hooks on host.
            run(["git","-c","core.hooksPath=/dev/null","-C",str(repo),
                 "worktree","add","--detach",str(checkout),sha],timeout=60)
            try:
                output.mkdir(mode=0o700)
                os.chown(output,65534,65534)
                # The sandbox user must read checked-out files, never git keys.
                os.chmod(checkout,0o755)
                image=ns.image
                job=[
                  "docker","run","--rm","--network","none","--read-only",
                  "--cap-drop","ALL","--security-opt","no-new-privileges",
                  "--pids-limit","96","--memory","768m","--cpus","1",
                  "--user","65534:65534",
                  "--tmpfs","/tmp:rw,nosuid,noexec,size=64m",
                  "--mount","type=bind,src="+str(checkout)+",dst=/workspace,readonly",
                  "--mount","type=bind,src="+str(output)+",dst=/evidence",
                  "--workdir","/workspace",image,
                  "python3","-B","/workspace/scripts/run_autonomous_research_cycle.py",
                  "--source-commit",sha,"--date",day,"-o","/evidence/research-episode.json"]
                started=time.monotonic()
                run(job,timeout=MAX_EXPERIMENT_SECONDS)
                elapsed=time.monotonic()-started
                receipt,payload_sha=sealed_report(output/"research-episode.json",sha,day)
                evidence=state/"receipts"
                evidence.mkdir(mode=0o700,exist_ok=True)
                # Host manifests are independent of the container report.
                manifest={
                  "schema_version":1,"runner":"cace-oci-a1",
                  "source_commit":sha,"source_ref":branch,"date_utc":day,
                  "experiment":"offline-autonomous-research-episode-v1",
                  "episode":receipt,"episode_file_sha256":payload_sha,
                  "duration_seconds":round(elapsed,3),
                  "runtime":"isolated-docker-no-network-no-credentials",
                  "verified_lean_proof":False,"cace_certified":False,
                  "production_promotion_authorized":False}
                encoded=(json.dumps(manifest,sort_keys=True,indent=2)+"\n").encode()
                with open(final,"xb") as f:
                    os.chmod(final,0o600)
                    f.write(encoded)
                print(json.dumps({"status":"receipt_written","source_commit":sha,
                       "date_utc":day,"route":receipt["selected_route"],
                       "manifest_sha256":hashlib.sha256(encoded).hexdigest(),
                       "path":str(final),"promotion_authorized":False}))
            finally:
                run(["git","-C",str(repo),"worktree","remove","--force",
                     str(checkout)],timeout=40)
    finally:
        os.close(lock)

if __name__=="__main__":main()
