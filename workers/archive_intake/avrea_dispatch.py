#!/usr/bin/env python3
"""Fail-closed Avrea dispatch gate. Provider execution is an explicit adapter, never implicit."""
from __future__ import annotations
import argparse, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from canonical_registry import connect, initialize

class DispatchRejected(Exception): pass
class AvreaProvider(Protocol):
    def submit(self, task: dict, approval: dict) -> dict: ...
    def fetch_result(self, provider_job_id: str) -> dict: ...

def canonical_sha(value):
    payload=dict(value) if isinstance(value,dict) else value
    if isinstance(payload,dict): payload.pop("task_contract_sha256",None)
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def validate_task(task,approval,policy):
    if not isinstance(task,dict) or not isinstance(approval,dict) or not isinstance(policy,dict):
        raise DispatchRejected("task, approval and policy must be JSON objects")
    if task.get("contract_version")!="1.0": raise DispatchRejected("unsupported task contract")
    digest=canonical_sha(task)
    if task.get("task_contract_sha256")!=digest: raise DispatchRejected("task_contract_sha256 does not match canonical task body")
    if approval.get("status")!="approved" or approval.get("approval_id")!=task.get("approval_id"):
        raise DispatchRejected("explicit matching approval is required")
    if approval.get("task_contract_sha256")!=digest: raise DispatchRejected("approval does not bind exact task contract")
    caps=task.get("capability_allowlist")
    allowed=policy.get("allowed_capabilities")
    if not isinstance(caps,list) or not caps or any(not isinstance(x,str) or not x for x in caps) or len(caps)!=len(set(caps)):
        raise DispatchRejected("invalid capability allowlist")
    if not isinstance(allowed,list) or any(not isinstance(x,str) or not x for x in allowed):
        raise DispatchRejected("policy allowed_capabilities must be a string array")
    if not set(caps).issubset(set(allowed)): raise DispatchRejected("capability outside policy")
    budget=task.get("resource_budget",{})
    if not isinstance(budget,dict) or not isinstance(policy.get("resource_maxima"),dict):
        raise DispatchRejected("resource budget and policy maxima must be objects")
    if set(budget)!=set(policy["resource_maxima"]): raise DispatchRejected("resource budget keys must exactly match policy")
    for key,maximum in policy["resource_maxima"].items():
        if not isinstance(budget.get(key),int) or isinstance(budget.get(key),bool) or budget[key]<1 or budget[key]>maximum:
            raise DispatchRejected("resource budget invalid or above policy: "+key)
    if task.get("network_access","none")!="none": raise DispatchRejected("network disabled unless a separately reviewed policy enables it")
    if task.get("result_manifest_required") is not True: raise DispatchRejected("result manifest is mandatory")
    if not isinstance(task.get("timeout_seconds"),int) or isinstance(task.get("timeout_seconds"),bool) or not isinstance(policy.get("max_timeout_seconds"),int) or isinstance(policy.get("max_timeout_seconds"),bool) or not 1<=task["timeout_seconds"]<=policy["max_timeout_seconds"]:
        raise DispatchRejected("timeout outside policy")
    return digest

def record_approval(database,approval):
    required=("approval_id","task_contract_sha256","approved_by","approval_source","approved_at")
    if any(not isinstance(approval.get(k),str) or not approval[k].strip() for k in required):
        raise DispatchRejected("approval record is incomplete")
    if approval.get("status")!="approved":
        raise DispatchRejected("approval status must be approved")
    if not re.fullmatch(r"[0-9a-f]{64}",approval["task_contract_sha256"]):
        raise DispatchRejected("approval must bind a lowercase SHA-256 task contract digest")
    with connect(database) as db:
        db.execute("INSERT INTO approval_records VALUES(?,?,?,?,?,?)",
          (approval["approval_id"],approval["task_contract_sha256"],approval["approved_by"],
           approval["approval_source"],approval["approved_at"],approval.get("approval_note","")))
    return {"approval_id":approval["approval_id"],"status":"recorded"}

def submit(database,task,approval,policy,provider=None):
    digest=validate_task(task,approval,policy)
    with connect(database) as db:
        stored=db.execute("SELECT * FROM approval_records WHERE approval_id=?",(approval["approval_id"],)).fetchone()
    if not stored or stored["task_contract_sha256"]!=digest:
        raise DispatchRejected("matching approval must first be recorded in canonical registry")
    task_id=task["task_id"]; now=datetime.now(timezone.utc).isoformat()
    with connect(database) as db:
        existing=db.execute("SELECT contract_sha256,approval_id,state,result_json FROM avrea_tasks WHERE task_id=?",(task_id,)).fetchone()
        if existing:
            if existing["contract_sha256"]!=digest or existing["approval_id"]!=approval["approval_id"]:
                raise DispatchRejected("task_id already exists with a different contract or approval")
            if existing["state"] in ("submitted","completed","failed","cancelled"):
                return {"task_id":task_id,"state":existing["state"],"result":existing["result_json"]}
        else:
            db.execute("INSERT INTO avrea_tasks VALUES(?,?,?,?,?,?,?,?)",
              (task_id,digest,approval["approval_id"],"approved",json.dumps(task,sort_keys=True),None,now,now))
    if provider is None:
        with connect(database) as db:
            db.execute("UPDATE avrea_tasks SET state='approved_waiting_for_provider',updated_at=? WHERE task_id=?",
              (datetime.now(timezone.utc).isoformat(),task_id))
        return {"task_id":task_id,"state":"approved_waiting_for_provider","task_contract_sha256":digest}
    response=provider.submit(task,approval)
    if not response.get("provider_job_id"): raise DispatchRejected("provider omitted job identity")
    with connect(database) as db:
        db.execute("UPDATE avrea_tasks SET state='submitted',result_json=?,updated_at=? WHERE task_id=?",
          (json.dumps({"provider_job_id":response["provider_job_id"]}),datetime.now(timezone.utc).isoformat(),task_id))
    return {"task_id":task_id,"state":"submitted","provider_job_id":response["provider_job_id"]}

def collect(database,task_id,provider):
    with connect(database) as db:
        row=db.execute("SELECT state,result_json FROM avrea_tasks WHERE task_id=?",(task_id,)).fetchone()
    if not row or row["state"]!="submitted": raise DispatchRejected("task is not submitted")
    provider_job_id=json.loads(row["result_json"])["provider_job_id"]
    result=provider.fetch_result(provider_job_id)
    manifest=result.get("result_manifest")
    if not isinstance(manifest,dict) or not isinstance(manifest.get("artifacts"),list):
        raise DispatchRejected("provider result must include artifact manifest")
    for artifact in manifest["artifacts"]:
        sha=artifact.get("sha256") if isinstance(artifact,dict) else None
        if not isinstance(sha,str) or not re.fullmatch(r"[0-9a-f]{64}",sha):
            raise DispatchRejected("result artifact is missing a valid SHA-256")
        if not isinstance(artifact.get("uri"),str) or not artifact["uri"]:
            raise DispatchRejected("result artifact is missing its retrieval URI")
    digest=canonical_sha(result)
    with connect(database) as db:
        db.execute("UPDATE avrea_tasks SET state='completed',result_json=?,updated_at=? WHERE task_id=?",
          (json.dumps({"provider_job_id":provider_job_id,"result":result,"result_sha256":digest},sort_keys=True),
           datetime.now(timezone.utc).isoformat(),task_id))
    return {"task_id":task_id,"state":"completed","result_sha256":digest,"artifact_count":len(manifest["artifacts"])}

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd",required=True)
    ap=sub.add_parser("record-approval"); ap.add_argument("approval",type=Path)
    run=sub.add_parser("submit"); run.add_argument("task",type=Path); run.add_argument("--approval",type=Path,required=True)
    run.add_argument("--policy",type=Path,required=True)
    for sp in (ap,run): sp.add_argument("--database",default="data/merlin.sqlite3")
    a=p.parse_args(); initialize(a.database)
    if a.cmd=="record-approval":
        result=record_approval(a.database,json.loads(a.approval.read_text()))
    else:
        task=json.loads(a.task.read_text()); approval=json.loads(a.approval.read_text()); policy=json.loads(a.policy.read_text())
        result=submit(a.database,task,approval,policy)
    print(json.dumps(result,indent=2))
if __name__=="__main__": main()
