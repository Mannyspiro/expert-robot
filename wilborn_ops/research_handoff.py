"""Deterministic, synthetic-only research handoff; never executes tasks."""
import json
from hashlib import sha256
from .research_queue import build_research_queue

def export_handoff(summary, *, source_commit, ci_run, max_tasks=3):
    if not isinstance(source_commit,str) or len(source_commit)!=40 or any(c not in "0123456789abcdef" for c in source_commit):
        raise ValueError("full lowercase commit SHA required")
    if type(ci_run) is not int or ci_run <= 0:
        raise ValueError("positive CI run ID required")
    tasks=build_research_queue(summary,max_tasks=max_tasks)
    records=[{
        "id": task.task_id,
        "finding_kind": task.finding_kind,
        "priority": task.priority,
        "hypothesis": task.hypothesis,
        "falsification_test": task.falsification_test,
        "environment": task.environment,
        "data_class": task.data_class,
        "requires_independent_review": task.requires_independent_review,
        "execution_authorized": False,
        "production_change_authorized": False,
    } for task in tasks]
    payload={"schema":"wilborn.synthetic.research_handoff.v1",
             "source_commit":source_commit,"ci_run":ci_run,
             "environment":"demo","data_class":"synthetic","tasks":records}
    canonical=json.dumps(payload,sort_keys=True,separators=(",",":"))
    return {"payload":payload,"sha256":sha256(canonical.encode("utf-8")).hexdigest()}

def verify_handoff(handoff):
    if not isinstance(handoff,dict) or set(handoff)!={"payload","sha256"}:
        raise ValueError("invalid handoff envelope")
    payload=handoff["payload"]
    if not isinstance(payload,dict) or set(payload)!={"schema","source_commit","ci_run","environment","data_class","tasks"}:
        raise ValueError("invalid handoff schema")
    if payload["schema"]!="wilborn.synthetic.research_handoff.v1" or payload["environment"]!="demo" or payload["data_class"]!="synthetic":
        raise PermissionError("non-demo handoff rejected")
    if not isinstance(payload["tasks"],list) or len(payload["tasks"])>6:
        raise ValueError("invalid task count")
    expected=export_handoff(
        {"environment":"demo","data_class":"synthetic",
         "counts":{t["finding_kind"]:1 for t in payload["tasks"]}},
        source_commit=payload["source_commit"],ci_run=payload["ci_run"],
        max_tasks=6 if payload["tasks"] else 1)
    # Compare each field against a freshly generated, approved task definition.
    approved={t["id"]:t for t in expected["payload"]["tasks"]}
    if len({t.get("id") for t in payload["tasks"]})!=len(payload["tasks"]):
        raise ValueError("duplicate task IDs")
    if any(t.get("id") not in approved or t!=approved[t["id"]] for t in payload["tasks"]):
        raise PermissionError("task payload altered")
    canonical=json.dumps(payload,sort_keys=True,separators=(",",":"))
    if sha256(canonical.encode("utf-8")).hexdigest()!=handoff["sha256"]:
        raise ValueError("handoff checksum mismatch")
    return True
