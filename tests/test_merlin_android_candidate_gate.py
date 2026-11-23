#!/usr/bin/env python3
"""Independent release gate regression using explicit generated fixtures, not model-quality evidence."""
import importlib.util
from pathlib import Path
import tempfile
import json

source=Path(__file__).resolve().parents[1]/"scripts/merlin/qualify_android_model.py"
spec=importlib.util.spec_from_file_location("gate",source)
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)

def cases(passes):
    out=[]
    for i in range(14):
        kind="tool" if i<9 else ("answer" if i<12 else "no_tool")
        out.append({"id":f"holdout-{i}","kind":kind,"pass":i in passes,"expected":None})
    return out

def bundled(rows):
    kinds={}
    for kind in ("tool","answer","no_tool"):
        subset=[r for r in rows if r["kind"]==kind]
        kinds[kind]={"total":len(subset),"correct":sum(x["pass"] for x in subset)}
    return {"metrics":{"total":len(rows),"passed":sum(r["pass"] for r in rows),"by_kind":kinds},"cases":rows}

a=bundled(cases(set(range(1,8))|{9,10,11,12,13}))
b=bundled(cases(set(range(0,8))|{9,10,11,12,13}))
report={"schema":"merlin-local-model-training-report/1","status":"completed","weights_created":True,
        "results":{"baseline":a,"trained":b}}
assert gate.evaluate(report)["gate"]=="exploratory_capability_pass"
assert not gate.evaluate(report)["apk_release_qualified"]
report["results"]["trained"]["cases"][0]["expected"]="changed"
assert gate.evaluate(report)["gate"]=="blocked"
report["results"]["trained"]=bundled(cases(set(range(0,8))|{9,10,11,12,13}))
report["results"]["trained"]["cases"][0]["pass"]="true"
assert gate.evaluate(report)["gate"]=="blocked"
report["results"]["trained"]=bundled(cases(set(range(0,8))|{9,10,11,12}))
assert gate.evaluate(report)["gate"]=="blocked"
report["results"]["trained"]=b
report["status"]="failed"
assert gate.evaluate(report)["gate"]=="blocked"
assert gate.evaluate({"schema":"merlin-heretic-capability-ab/1","baseline":a})["gate"]=="blocked"
assert gate.evaluate({"schema":"unknown"})["gate"]=="blocked"
print("PASS: 7 promotion negative/positive tests; APK cannot be qualified by this gate")
