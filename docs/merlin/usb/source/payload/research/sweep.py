"""Replay an Ideonomy floorplan grid on real checkpoint tensor dimensions."""
from collections import Counter, defaultdict
from hashlib import file_digest, sha1, sha256
from importlib.util import spec_from_file_location, module_from_spec
from itertools import combinations, product
import json
from pathlib import Path
import sys

import numpy as np

from gguf import GGUF


ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT/"protocol.json").read_text())
AXES = [CONFIG[k] for k in ("layouts","vram","reduction")]
SIZE = tuple(CONFIG["mesh_xyz"])
HOST = (6,1,0)
# These are nominal macro locations, not overlaps of actual die footprints.
DIES = {
    "stacked": [(6,6),(6,6),(6,6),(6,6)],
    "checker_staggered": [(4,4),(8,8),(8,4),(4,8)],
    "edge_staggered": [(3,5),(7,3),(9,7),(5,9)],
    "column_split": [(4,6),(8,6),(4,6),(8,6)],
}
FIXED_BANKS = {
    "board_edge": [(2,2,0),(10,2,0),(2,10,0),(10,10,0)],
    "paired_edges": [(6,2,0),(6,10,0),(2,6,0),(10,6,0)],
    "top_ring": [(4,4,5),(8,8,5),(8,4,5),(4,8,5)],
}
REDUCTION = {"base_center":(6,6,0),"mid_stack":(7,6,2),"side_exit":(11,6,1)}


def choices(source):
    data = source.read_bytes()
    blob = sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
    assert blob == "43a69eb8891f96d65a815e0f091c2df505fa64e6"
    spec=spec_from_file_location("merlin_scientific_loop",source)
    native=module_from_spec(spec)
    sys.modules[spec.name]=native
    spec.loader.exec_module(native)
    primitives=[{"id":v,"domain":str(i),"estimated_cost":1,"status":"candidate"}
                for i,axis in enumerate(AXES) for v in axis]
    pairs={frozenset((a["id"],b["id"])) for a,b in combinations(primitives,2) if a["domain"]!=b["domain"]}
    receipt=native.enumerate_combination_report(
        primitives,pairs,trigger="Compare architectural placement against a real Qwen trace",
        problem="Reduce congestion, routed payload and heat under equal compute and bank budgets",
        max_size=3,max_cost=3,limit=88,work_budget=220)
    designs=[tuple(r["primitive_ids"]) for r in receipt["candidates"] if len(r["primitive_ids"])==3]
    assert set(designs)==set(product(*AXES))
    return designs,{"source_blob":blob,"coverage":receipt["coverage"]}


def locations(layout):
    die,bank,reducer=layout
    cores=[(x,y,z) for z,(x,y) in enumerate(DIES[die],1)]
    banks=FIXED_BANKS.get(bank) if bank!="interleaved" else [
        (x+(2 if x<=6 else -2),y,z) for x,y,z in cores]
    result={"host":HOST,"reducer":REDUCTION[reducer]}
    result.update({f"core{i}":p for i,p in enumerate(cores)})
    result.update({f"bank{i}":p for i,p in enumerate(banks)})
    assert len(result)==len(set(result.values()))
    assert all(0<=component<bound for p in result.values() for component,bound in zip(p,SIZE))
    return result


def extract(checkpoint):
    with checkpoint.open("rb") as f:
        digest=file_digest(f,"sha256").hexdigest()
    assert digest=="7671c0c304e6ce5a7fc577bcb12aba01e2c155cc2efd29b2213c95b18edaf6ed"
    sample=GGUF(checkpoint)
    tensors=[{"name":t.name,"shape":list(t.shape),"kind":t.kind,"bytes":t.nbytes}
             for t in sample.tensors.values() if len(t.shape)==2 and t.name!="token_embd.weight"]
    assert len(tensors)==169
    return {"checkpoint_sha256":digest,"projection_tensors":sorted(tensors,key=lambda t:t["name"])}


def traffic(trace, scenario):
    messages=defaultdict(int)
    macs=[0]*4
    for tensor in trace["projection_tensors"]:
        count=1 if tensor["name"]=="output.weight" else scenario["tokens"]
        tile_batch=(count+11)//12
        rows,width=tensor["shape"]
        assert width%32==0
        blocks=width//32
        binary_block=18 if tensor["kind"]==2 else 34
        assert tensor["bytes"]==rows*blocks*binary_block
        outputs=(rows+11)//12
        for i in range(4):
            active=len(range(i,blocks,4))
            messages["input",f"bank{scenario['bank_map'][i]}",f"core{i}"]+=rows*active*binary_block*tile_batch
            messages["input","host",f"core{i}"]+=count*active*36*outputs
            messages["reduce",f"core{i}","reducer"]+=count*rows*8
            macs[i]+=count*rows*active*32
        messages["return","reducer","host"]+=count*rows*4
    return dict(messages),macs


def route(a,b,order):
    cursor=list(a)
    origins=[]
    for axis in order:
        while cursor[axis]!=b[axis]:
            start=tuple(cursor)
            cursor[axis]+=1 if b[axis]>cursor[axis] else -1
            origins.append((start,tuple(cursor),axis))
    assert tuple(cursor)==b and len(origins)==sum(abs(i-j) for i,j in zip(a,b))
    return origins


def network(points,messages):
    cfg=CONFIG["routing"]
    loads={p:Counter() for p in cfg["phases"]}
    chargeto=Counter()
    expected_bytehops=0
    for (phase,source,dest),amount in messages.items():
        a,b=points[source],points[dest]
        expected_bytehops+=amount*sum(abs(i-j) for i,j in zip(a,b))
        for left,right,axis in route(a,b,cfg["order"]):
            loads[phase][left,right,axis]+=amount
            chargeto[left]+=amount/2
            chargeto[right]+=amount/2
    total=sum(sum(i.values()) for i in loads.values())
    assert expected_bytehops==total and sum(chargeto.values())==total
    stages={}
    for phase,value in loads.items():
        hot=max(value,key=lambda link: value[link]/cfg["z_payload_per_slot" if link[2]==2 else "xy_payload_per_slot"])
        stages[phase]={"bytes":value[hot],"link":hot,
                       "lower_bound_slots":value[hot]/cfg["z_payload_per_slot" if hot[2]==2 else "xy_payload_per_slot"]}
    return {"byte_hops":total,"serial_phase_lower_bound_slots":sum(x["lower_bound_slots"] for x in stages.values()),
            "phase_bottlenecks":stages},chargeto


def thermal(points, chg, macs, sink):
    cfg=CONFIG["thermal"]
    power=np.zeros(SIZE)
    for site, amount in chg.items():
        power[site]+=amount*cfg["link_heat_per_byte_hop"]
    for lane,n in enumerate(macs):
        p=points[f"core{lane}"]
        energy=n*cfg["mac_heat_per_unit"]
        for dx,dy in product((-1,0,1),repeat=2):
            power[p[0]+dx,p[1]+dy,p[2]]+=energy/9
    u=np.zeros(SIZE)
    loss,injected,error,peak = 0.,0.,0.,0.
    temp_steps=[]
    for step in range(cfg["heating_steps"]+cfg["cooldown_steps"]):
        nxt=u.copy()
        for i,coeff in enumerate(cfg["diffusion"]):
            lo,hi=[slice(None)]*3,[slice(None)]*3
            lo[i],hi[i]=slice(None,-1),slice(1,None)
            a,b=tuple(lo),tuple(hi)
            flow=coeff*(u[a]-u[b])
            nxt[a]-=flow
            nxt[b]+=flow
        out=sink*u[:,:,-1]
        nxt[:,:,-1]-=out
        loss+=float(out.sum())
        assert float(nxt.min())>=-1e-12 and float(nxt.max())<=float(u.max())+1e-12
        if step<cfg["heating_steps"]:
            nxt+=power/cfg["heating_steps"]
            injected+=float(power.sum())/cfg["heating_steps"]
        error=max(error,abs(float(nxt.sum())+loss-injected))
        u=nxt
        peak=max(peak,float(u.max()))
        temp_steps.append(float(u.max()))
    assert error<1e-8
    return {"peak_excess":peak,"post_cooldown_excess":temp_steps[-1],"heat_input":injected,
            "removed_heat":loss,"balance_residual":error,"peak_curve":temp_steps}


def evaluate(layout,trace,scenario):
    points=locations(layout)
    messages,macs=traffic(trace,scenario)
    route_stats,chg=network(points,messages)
    return {**route_stats,**thermal(points,chg,macs,scenario["sink"]),
            "logical_bytes":sum(messages.values()),"integer_macs_by_tier":macs}


def main(source,tracefile,output):
    trace=json.loads(tracefile.read_text())
    native = []
    for tokens in (225,1):
        messages, macs=traffic(trace,{"tokens":tokens,"bank_map":[0,1,2,3]})
        native.append((sum(macs),sum(v for (p,a,b),v in messages.items() if a.startswith("bank"))))
    native_mac=sum(x[0] for x in native)
    native_weight=sum(x[1] for x in native)
    assert (native_mac,native_weight)==(81141071872,4314834944)
    layouts,native=choices(source)
    definitions={"/".join(l):l for l in layouts}
    scenarios=CONFIG["discovery"]
    results={label:{s:evaluate(d,trace,scenario) for s,scenario in scenarios.items()}
             for label,d in definitions.items()}
    baseline=CONFIG["baseline"]
    for scenario in scenarios:
        assert len({r[scenario]["logical_bytes"] for r in results.values()})==1
        assert len({tuple(r[scenario]["integer_macs_by_tier"]) for r in results.values()})==1
    metrics=("byte_hops","serial_phase_lower_bound_slots","peak_excess")
    def ratios(label, selected=metrics):
        return [results[label][s][m]/results[baseline][s][m] for s in scenarios for m in selected]
    def key(label, selected=metrics):
        items=ratios(label,selected)
        return max(items),float(np.mean(items)),label
    winning=min(definitions,key=key)
    traffic_min=min(definitions,key=lambda name:key(name,metrics[:2]))
    joined=[winning,baseline,traffic_min]
    pareto=[]
    for candidate in definitions:
        value=ratios(candidate)
        if not any(all(a<=b for a,b in zip(ratios(x),value)) and
                   any(a<b for a,b in zip(ratios(x),value)) for x in definitions if x!=candidate):
            pareto.append(candidate)
    for label in set(joined):
        for s,scenario in CONFIG["held_out"].items():
            results[label][s]=evaluate(definitions[label],trace,scenario)
    evidence={"baseline":baseline,"selected":winning,"traffic_only":traffic_min,"pareto":sorted(pareto),
              "ranked":sorted(definitions,key=key),"merlin":native,
              "protocol_sha256":sha256((ROOT/"protocol.json").read_bytes()).hexdigest(),
              "checkpoint_sha256":trace["checkpoint_sha256"],
              "matched_prior_studio_workload":{"integer_macs":native_mac,"tile_weight_payload_bytes":native_weight},
              "locations":{label:locations(layout) for label,layout in definitions.items()},
              "results":results}
    output.write_text(json.dumps(evidence,indent=2)+"\n")
    print(winning, traffic_min, len(pareto))
    for s in results[baseline]:
        print(s,{m:round(results[winning][s][m]/results[baseline][s][m],5) for m in metrics})


if __name__=="__main__":
    if sys.argv[1]=="extract":
        Path(sys.argv[3]).write_text(json.dumps(extract(Path(sys.argv[2])),indent=2)+"\n")
    else:
        main(*map(Path,sys.argv[1:4]))
