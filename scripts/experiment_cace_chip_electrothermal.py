#!/usr/bin/env python3
"""2D nine-node chip-sheet electrothermal research model with exact equations.

Electrical problem: div(sigma * grad V)=0 on a resistive planar network,
  V(left)=0.1 V, V(right)=0 V, g_e=sigma_harmonic * film_t * width / length.
Joule heating: Q_e=g_e*(V_i-V_j)^2, split equally over its two nodes.
Thermal problem: div(k * grad T) + heat_sink*(T-Tambient)=Joule power.

This is a coarse physical finite-volume NETWORK, not an actual transistor,
drift-diffusion TCAD, FEM PDE certificate, foundry-calibrated thermal model,
3D silicon simulation or fabrication qualification.
"""
from __future__ import annotations
import argparse
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import subprocess
import sys

SIZE=3
GRID_SPACING_M=F(1,10000)        # 100 micrometers
FILM_THICKNESS_M=F(1,1000000)   # 1 micrometer
THERMAL_THICKNESS_M=F(1,10000)  # effective 100 micrometers
SILICON_K_W_PER_MK=F(130)
AMBIENT_SINK_W_PER_K=F(1,1000) # illustrative per-node heat sink
BIAS_V=F(1,10)
NODES=tuple((x,y) for y in range(SIZE) for x in range(SIZE))
INDEX={v:i for i,v in enumerate(NODES)}


def gaussian(matrix, rhs):
    n=len(rhs)
    if len(matrix)!=n or any(len(row)!=n for row in matrix):
        raise ValueError("matrix dimension")
    m=[[F(z) for z in row]+[F(rhs[i])] for i,row in enumerate(matrix)]
    for k in range(n):
        pivot=next((i for i in range(k,n) if m[i][k]),None)
        if pivot is None:
            raise ValueError("singular model")
        m[k],m[pivot]=m[pivot],m[k]
        factor=m[k][k]
        m[k]=[v/factor for v in m[k]]
        for i in range(n):
            if i!=k:
                scale=m[i][k]
                m[i]=[m[i][j]-scale*m[k][j] for j in range(n+1)]
    return tuple(row[-1] for row in m)


def edges():
    out=[]
    for x,y in NODES:
        for xy in ((x+1,y),(x,y+1)):
            if xy not in INDEX:
                continue
            a=F(20000 if (x,y)==(1,1) else 100000)
            b=F(20000 if xy==(1,1) else 100000)
            # Toy effective film conductivity, NOT a calibrated silicon MOSFET.
            conductivity=2*a*b/(a+b)
            conductance=conductivity*FILM_THICKNESS_M
            out.append((INDEX[(x,y)],INDEX[xy],conductance))
    return tuple(out)


def laplacian(network,n=len(NODES)):
    a=[[F(0) for _ in range(n)] for _ in range(n)]
    for u,v,g in network:
        if u==v or not (0<=u<n and 0<=v<n) or g<=0:
            raise ValueError("invalid passive conductance")
        a[u][u]+=g; a[v][v]+=g
        a[u][v]-=g; a[v][u]-=g
    return a


def independent_kcl(network,volts):
    currents=[F(0)]*len(volts)
    for u,v,g in network:
        flow=g*(volts[u]-volts[v])
        currents[u]+=flow;currents[v]-=flow
    return currents


def model():
    network=edges()
    electrical=laplacian(network)
    fixed={INDEX[(x,y)]:(BIAS_V if x==0 else F(0))
           for x,y in NODES if x in (0,SIZE-1)}
    free=[i for i in range(len(NODES)) if i not in fixed]
    rhs=[-sum(electrical[i][j]*v for j,v in fixed.items()) for i in free]
    solved=gaussian([[electrical[i][j] for j in free] for i in free],rhs)
    voltage=[F(0)]*len(NODES)
    for i,v in fixed.items():voltage[i]=v
    for i,v in zip(free,solved):voltage[i]=v
    current=independent_kcl(network,voltage)
    if any(current[i] for i in free):
        raise AssertionError("electrical free-node KCL failure")
    supply=sum(current[i] for i in fixed if NODES[i][0]==0)
    if supply<=0 or sum(current)!=0:
        raise AssertionError("current return or supply mismatch")
    heat=[F(0)]*len(NODES)
    for u,v,g in network:
        dissipation=g*(voltage[u]-voltage[v])**2
        heat[u]+=dissipation/2;heat[v]+=dissipation/2
    power=sum(heat)
    if power != BIAS_V*supply:
        raise AssertionError("electrical power budget mismatch")
    thermal_edges=tuple((u,v,SILICON_K_W_PER_MK*THERMAL_THICKNESS_M)
                        for u,v,_ in network)
    thermal=laplacian(thermal_edges)
    for i in range(len(NODES)):
        thermal[i][i]+=AMBIENT_SINK_W_PER_K
    temp_rise=gaussian(thermal,heat)
    if any(t<0 for t in temp_rise):
        raise AssertionError("unphysical negative rise for positive heat")
    # Independent local physical flux oracle, not thermal matrix multiplication.
    conduction=independent_kcl(thermal_edges,temp_rise)
    residual=[conduction[i]+AMBIENT_SINK_W_PER_K*temp_rise[i]-heat[i]
              for i in range(len(NODES))]
    if any(residual) or AMBIENT_SINK_W_PER_K*sum(temp_rise)!=power:
        raise AssertionError("thermal heat balance failed")
    # Manufacturing deviations must invalidate the baseline qualification.
    removed=tuple(e for e in network if
                  set(e[:2])!={INDEX[(0,1)],INDEX[(1,1)]})
    open_trace_detected=any(independent_kcl(removed,voltage)[i] for i in free)
    changed=tuple((u,v,g*2 if
                   set((u,v))=={INDEX[(0,1)],INDEX[(1,1)]} else g)
                  for u,v,g in network)
    conductivity_mutation_detected=any(independent_kcl(changed,voltage)[i] for i in free)
    if not (open_trace_detected and conductivity_mutation_detected):
        raise AssertionError("layout material mutation escaped detection")
    return {
        "schema_version":1, "model":"nine-node-electrothermal-film-v1",
        "geometry_nodes_xy_um":[[x*100,y*100] for x,y in NODES],
        "approximation":"steady state 2D lumped conductance graph; vertical substrate approximated by local heat sink",
        "electrical_film_thickness_m":str(FILM_THICKNESS_M),
        "thermal_effective_thickness_m":str(THERMAL_THICKNESS_M),
        "source_bias_volts":str(BIAS_V),
        "electrical_conductance_S":[[u,v,str(g)] for u,v,g in network],
        "voltages_V":[str(v) for v in voltage],
        "total_supply_current_A":str(supply),
        "electrical_power_W":str(power),
        "thermal_k_W_per_mK":str(SILICON_K_W_PER_MK),
        "thermal_ambient_sink_W_per_K":str(AMBIENT_SINK_W_PER_K),
        "temperature_rise_K":[str(v) for v in temp_rise],
        "maximum_temperature_rise_K":float(max(temp_rise)),
        "electrical_matrix":[[str(v) for v in row] for row in electrical],
        "thermal_matrix":[[str(v) for v in row] for row in thermal],
        "exact_free_node_kcl_residuals":[str(current[i]) for i in free],
        "exact_thermal_residuals":[str(v) for v in residual],
        "open_trace_mutant_detected":open_trace_detected,
        "conductivity_mutant_detected":conductivity_mutation_detected,
        "physical_material_parameters_calibrated":False,
        "transistor_carriers_or_quantum_modeled":False,
        "physical_chip_fabricated_or_tested":False,
        "cace_pde_solver_executed":False,
        "lean_kernel_checked":False,
        "cace_certificate":False,
        "rsi_promotion_authorized":False,
    }


def verify_cace_codec(report,root,pin_file):
    """Use the ACTUAL exact-pinned CACE CSR adapter, not a fake CACE proof."""
    import numpy as np
    pin=json.loads(pin_file.read_text(encoding="utf-8"))
    expected=pin["commit"]
    actual=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
    if actual!=expected or pin.get("repository")!="morganaspim/Cace-app":
        raise ValueError("CACE source is not exact pinned checkout")
    if not (root/"cace_studio/modules/fem.py").is_file():
        raise ValueError("missing pinned CACE FEM codec")
    sys.path.insert(0,str(root))
    from cace_studio.modules.fem import _csr_from_dense,_dense_from_csr
    for name in ("electrical_matrix","thermal_matrix"):
        dense=np.array([[float(F(x)) for x in row] for row in report[name]],dtype=float)
        cace=_csr_from_dense(dense,tol=0.0)
        recovered=np.asarray(_dense_from_csr(cace),dtype=float)
        if recovered.shape!=dense.shape or not np.array_equal(recovered,dense):
            raise AssertionError("pinned CACE CSR lost chip operator entries")
    report["cace_repository"]="morganaspim/Cace-app"
    report["cace_commit_sha"]=expected
    report["actual_cace_csr_codec_executed"]=True
    report["cace_pde_solver_executed"]=False
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cace-repo",type=Path)
    p.add_argument("--pin",type=Path,default=Path("config/cace_fem_nd_contract_pin.json"))
    p.add_argument("-o","--output",type=Path)
    args=p.parse_args()
    result=model()
    result["actual_cace_csr_codec_executed"]=False
    if args.cace_repo is not None:
        result=verify_cace_codec(result,args.cace_repo.resolve(),args.pin)
    canonical=json.dumps(result,sort_keys=True,separators=(",",":"))
    result["result_sha256"]=hashlib.sha256(canonical.encode()).hexdigest()
    output=json.dumps(result,sort_keys=True,indent=2)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(output,encoding="utf-8")
    print(json.dumps({k:result[k] for k in (
        "maximum_temperature_rise_K","electrical_power_W",
        "actual_cace_csr_codec_executed","cace_pde_solver_executed",
        "result_sha256")},sort_keys=True))


if __name__=="__main__":
    main()
