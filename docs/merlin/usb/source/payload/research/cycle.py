"""Merlin Xenomaths research cycle and guarded physics-runtime promotion."""
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
import sys
from tempfile import NamedTemporaryFile
from threading import Lock
from time import perf_counter

import numpy as np
from physics import solve
from research import matter,workers

ROOT=Path(__file__).resolve().parent
VERSION="xenomaths-flight/1"
SHAPES=((20,20,12),(34,26,16),(32,30,15))
LOCK=Lock()


def thermal_qualification():
    rows=[]
    for shape,offset in zip(SHAPES,(0,2,-3),strict=True):
        for world in ("uniform","layered","sink"):
            times={k:[] for k in ("reference","precomputed")}
            args=dict(world=world,steps=32,shape=shape,offset=offset)
            for _ in range(8):
                for name in (tuple(times) if _%2 else tuple(reversed(times))):
                    now=perf_counter()
                    value=solve(**args,backend=name)
                    times[name].append(perf_counter()-now)
            outputs=[]
            for name in times:
                history=[]
                evidence=solve(**args,history=history,backend=name)
                outputs.append((evidence,sha256(np.stack(history).tobytes()).hexdigest()))
            exact=outputs[0]==outputs[1]
            rows.append({"world":world,"shape":shape,"offset":offset,"exact":exact,"grid_sha256":outputs[0][1],
                         "reference_ms":median(times["reference"][1:])*1000,
                         "candidate_ms":median(times["precomputed"][1:])*1000})
    accepted=all(x["exact"] and x["candidate_ms"]<=.95*x["reference_ms"] for x in rows)
    return {"candidate":"precomputed","status":"promoted" if accepted else "baseline_kept",
            "active_backend":"precomputed" if accepted else "reference","cases":rows,
            "gate":"Exact full time history and at least 5% faster on every case, including shifted holdouts"}


def chip_search(portable,round_number):
    sys.path.insert(0,str(portable/"simulator"))
    from research import sweep
    trace=json.loads((ROOT/"trace_manifest.json").read_text())
    layouts,ideonomy=sweep.choices(ROOT/"merlin_ideonomy.py")
    baseline=tuple(sweep.CONFIG["baseline"].split("/"))
    # Freeze discovery with varied heat, bank traffic, and Qwen dimensions.
    worlds={"uniform":{"tokens":3,"sink":.09,"bank_map":[0,1,2,3]},
            "layered":{"tokens":17,"sink":.13,"bank_map":[0,2,1,3]},
            "sink":{"tokens":48,"sink":.19,"bank_map":[0,1,2,3]}}
    heldout={"shifted_bank":{"tokens":37,"sink":.07,"bank_map":[1,0,3,2]},
             "long_prefill":{"tokens":143,"sink":.15,"bank_map":[0,1,2,3]}}
    if round_number%2==0:
        worlds["uniform"]["tokens"]=5
        worlds["layered"]["tokens"]=23
        worlds["layered"]["bank_map"]=[0,3,2,1]
        heldout["long_prefill"]["tokens"]=161
    keys=("byte_hops","serial_phase_lower_bound_slots","peak_excess")

    def evaluate(layout,scenarios):
        return {name:sweep.evaluate(layout,trace,config) for name,config in scenarios.items()}

    def ratio(result,base):
        out={}
        for name,r in result.items():
            assert r["logical_bytes"]==base[name]["logical_bytes"]
            assert r["integer_macs_by_tier"]==base[name]["integer_macs_by_tier"]
            out[name]={k:r[k]/base[name][k] for k in keys}
        return out

    def scores(r):
        v=[number for world in r.values() for number in world.values()]
        return max(v),sum(v)/len(v)

    base=evaluate(baseline,worlds)
    ranked={layout:ratio(evaluate(layout,worlds),base) for layout in layouts}
    selected=min(ranked,key=lambda key:(scores(ranked[key]),key))
    untouched=ratio(evaluate(selected,heldout),evaluate(baseline,heldout))
    return {"candidate":"/".join(selected),"ranked_designs":len(ranked),"ideonomy":ideonomy,
            "ranked":[{"layout":"/".join(l),"metrics":ranked[l]} for l in sorted(ranked,key=lambda k:(scores(ranked[k]),k))],
            "worlds":worlds,"held_out":untouched,"baseline":"/".join(baseline),
            "holdout_config":heldout,"scad_points":sweep.locations(selected),
            "status":"simulated_candidate" if scores(untouched)[0]<=1 else "holdout_tradeoff",
            "scope":"Equal-work placement proxy. The thermal scenarios vary sink strength; the independent physics solver also tests anisotropy. No physical or executable routing change is inferred."}


def chip_scad(out,placement):
    shapes=["host","reducer",*(f"core{i}" for i in range(4)),*(f"bank{i}" for i in range(4))]
    with out.open("w") as f:
        f.write("// Merlin nominal research mesh, 2 mm x/y and 1.5 mm z per step.\n")
        for item in shapes:
            x,y,z=placement[item]
            color="pink" if item.startswith("core") else "orchid" if item.startswith("bank") else "plum"
            f.write(f'color("{color}") translate([{x*2},{y*2},{z*1.5}]) cube([1.5,1.5,1]); // {item}\n')


def write_json(path,report):
    with NamedTemporaryFile(dir=path.parent,mode="w",delete=False) as f:
        pending=Path(f.name)
        try:
            json.dump(report,f,indent=2,allow_nan=False)
            f.flush()
            pending.replace(path)
        finally:
            pending.unlink(missing_ok=True)


def run(state,portable,fingerprint,interpret=None,fetch=None):
    if not LOCK.acquire(blocking=False):return {"status":"running"}
    try:
        dest=state/"xenomaths"
        dest.mkdir(parents=True,exist_ok=True)
        last=read(state)
        round_number=last.get("round",0)+1 if last.get("version")==VERSION else 1
        physics=thermal_qualification()
        architecture=chip_search(portable,round_number)
        printer,geometry=matter.experiment()
        chip_scad(dest/"Merlin_Chip_Candidate.scad",architecture["scad_points"])
        matter.scad(dest/"Metamaterial_Coupon.scad",geometry)
        sources=[]
        if fetch:
            ref=json.loads((ROOT/"Sources.json").read_text())["references"][1]
            try:
                result=fetch(ref["url"])
                sources.append({**ref,"result":"retrieved","sha256":result["sha256"],
                                "final_url":result["final_url"],"bytes":result["network_bytes"]})
            except (OSError,ValueError,TimeoutError) as exc:
                sources.append({**ref,"result":"unavailable","status":str(exc)})
        report={"status":"complete","version":VERSION,"finished":datetime.now(timezone.utc).isoformat(),
            "host":fingerprint,"round":round_number,"prior_run":last.get("finished"),"physics":physics,
            "chip":architecture,"matter":printer,"external_sources":sources}
        report["workers"]=[workers.create(state,kind,kind+"-report",report) for kind in workers.TOOLS]
        # Publish the evidence before requesting a bounded explanatory model turn.
        write_json(dest/"Latest.json",report)
        if interpret:
            question=(f"Merlin simulation lab. In two short sentences interpret this result. "
                      f"Thermal chip layout {architecture['candidate']} is a simulation candidate only. "
                      f"Thermal solver gate {physics['status']}. The '{printer['winner']}' "
                      f"virtual heat coupon matched two scans. State a next experiment.")
            try:report["merlin_interpretation"]=interpret(question)
            except (OSError,ValueError,TimeoutError,RuntimeError) as e:
                report["merlin_interpretation_status"]=type(e).__name__
            write_json(dest/"Latest.json",report)
        stamp=report["finished"].replace(":","-").replace("+","_")
        write_json(dest/f"Run_{stamp}.json",report)
        return report
    finally:
        LOCK.release()


def read(state):
    path=state/"xenomaths/Latest.json"
    try:return json.loads(path.read_text())
    except (OSError,ValueError):return {"status":"pending"}


def active(state,fingerprint):
    data=read(state)
    if data.get("host")==fingerprint and data.get("version")==VERSION:
        physics=data.get("physics",{})
        if physics.get("status")=="promoted" and physics.get("active_backend")=="precomputed":
            return "precomputed"
    return "reference"
