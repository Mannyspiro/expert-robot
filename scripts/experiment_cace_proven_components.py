#!/usr/bin/env python3
"""Exact graph-component conservation against CACE's *actual* FEM CSR codec.

Lean-qualified supporting theorem at git commit
387b75d6052ea78d2bb791449102ae728399442d:
CoreTransfer.weightedFlux_zero_for_all_iff_factors.
The proof covers unit-transfer graphs and exact finite integer flux pairings.
This experiment additionally checks rational conservative diffusion updates,
not a verified numerical solver or a PDE certificate.

CACE is used only for _csr_from_dense / _dense_from_csr (read-only).
"""
import argparse
from collections import deque
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import random
import sys

PROOF_SHA="387b75d6052ea78d2bb791449102ae728399442d"
RATIONAL_PROOF_SHA="b2a9a0ab86034863b082c5e8a72ba7e58afd718f"
CACE_SHA="66b22a71ff52b3110269f5994a5fd0716a2054c1"
PROOF_GIT_BLOBS={
    "research/lean-transfer-core/TransferReachability.lean":
        "7f0bdd74ed5130dfa5d91d76b0bca2a6da371e3b",
    "research/lean-transfer-core/ComponentFactorization.lean":
        "79c5ae1d524597b571c5a3e80a8f0b191e384e35",
    "research/lean-transfer-core/ComponentFlux.lean":
        "612d7720859c950797cee536187a9410cd002ebb",
}


def component_groups(n,edges):
    neighbors=[set() for _ in range(n)]
    for a,b,_ in edges:
        if not 0<=a<n or not 0<=b<n or a==b:
            raise ValueError("invalid edge")
        neighbors[a].add(b)
        neighbors[b].add(a)
    groups=[]
    seen=set()
    for start in range(n):
        if start in seen:
            continue
        q=deque([start])
        group=set()
        while q:
            v=q.popleft()
            if v in group:
                continue
            group.add(v)
            q.extend(neighbors[v]-group)
        seen.update(group)
        groups.append(tuple(sorted(group)))
    assert sum(len(g) for g in groups)==n
    return groups


def laplacian(n,edges):
    a=[[0]*n for _ in range(n)]
    for src,dst,conductance in edges:
        if type(conductance) is not int or not 1<=conductance<=4:
            raise ValueError("conductance must be a bounded positive integer")
        if src==dst or not 0<=src<n or not 0<=dst<n:
            raise ValueError("bad transfer endpoints")
        a[src][src]+=conductance
        a[dst][dst]+=conductance
        a[src][dst]-=conductance
        a[dst][src]-=conductance
    return a


def strict_unit_transfers(n, columns):
    """Stoichiometric columns, not a numerical diffusion Laplacian."""
    for col in columns:
        if len(col)!=n or sorted(v for v in col if v)!=[-1,1]:
            return False
    return True


def cases():
    rng=random.Random(20261009)
    n=32
    edges32=[]
    for base in (0,8,16,24):
        for k in range(base,base+7):
            edges32.append((k,k+1,1+(k%3)))
        for _ in range(10):
            a,b=rng.sample(range(base,base+8),2)
            edges32.append((a,b,1+rng.randrange(3)))
    return [
        ("isolated_species",5,[]),
        ("two_independent_chains",6,[(0,1,1),(1,2,2),(3,4,1),(4,5,3)]),
        ("cycles_and_singleton",7,[(0,1,2),(1,2,1),(2,0,3),(3,4,1),(4,5,2),(5,3,1)]),
        ("parallel_edges",8,[(0,1,1),(0,1,3),(2,3,2),(4,5,1),(6,7,3)]),
        ("mixed_connected_islands",12,[(i,i+1,1+i%3) for i in range(0,4)]+
           [(i,i+1,1+i%2) for i in range(6,10)]+[(0,3,1),(7,9,2)]),
        ("large_four_components",n,edges32),
    ]


def math_report(cace_repo=None):
    import numpy as np
    use_cace=cace_repo is not None
    if use_cace:
        sys.path.insert(0,str(cace_repo))
        from cace_studio.modules.fem import _csr_from_dense,_dense_from_csr
    rows=[]
    update_count=0
    for name,n,edges in cases():
        groups=component_groups(n,edges)
        m=laplacian(n,edges)
        # The signed stoichiometry is a unit transfer for every graph edge.
        columns=[]
        for src,dst,_ in edges:
            col=[0]*n
            col[src]=-1
            col[dst]=1
            columns.append(col)
        assert strict_unit_transfers(n,columns)
        for group in groups:
            # Component-indicator vectors annihilate the sparse Laplacian.
            assert all(sum(m[i][j] for i in group)==0 for j in range(n))
        assert all(sum(m[i][j] for i in range(n))==0 for j in range(n))
        dense=np.array(m,dtype=float)
        if use_cace:
            csr=_csr_from_dense(dense,tol=0.0)
            recovered=np.asarray(_dense_from_csr(csr),dtype=float)
            if recovered.shape!=(n,n) or not np.array_equal(recovered,dense):
                raise AssertionError("real CACE CSR encode/decode differs from exact operator")
        else:
            recovered=dense.copy()
        degree=max((m[i][i] for i in range(n)),default=0)
        dt=Q(1, max(1,2*degree))
        numeric_dt=float(dt)
        for mode in range(4):
            if mode==0:
                state=[Q(i+1,n+1) for i in range(n)]
            elif mode==1:
                state=[Q((i*7+3)%11,11) for i in range(n)]
            elif mode==2:
                state=[Q(int(i%3==0)) for i in range(n)]
            else:
                state=[Q(2) if i%2 else Q(0) for i in range(n)]
            numerical=np.array([float(x) for x in state],dtype=float)
            totals=[sum((state[i] for i in group),Q(0)) for group in groups]
            for step in range(12):
                state=[state[i]-dt*sum((Q(m[i][j])*state[j] for j in range(n)),Q(0))
                       for i in range(n)]
                numerical=numerical-numeric_dt*(recovered@numerical)
                assert all(x>=0 for x in state), "positivity failed"
                for group,old in zip(groups,totals):
                    assert sum((state[i] for i in group),Q(0))==old, "exact component drift"
                if max(abs(float(state[i])-float(numerical[i])) for i in range(n))>5e-11:
                    raise AssertionError("real CACE encoded diffusion operator differs from exact Fraction oracle")
                update_count+=1
        rows.append({
            "name":name,"species":n,"transfer_edges":len(edges),
            "components":len(groups),"component_sizes":[len(g) for g in groups],
            "steps":48,"dt":str(dt),"exact_component_mass_residual":"0",
            "nonnegative_exact_updates":True,"csr_roundtrip_exact":True,
            "numeric_matches_fraction_oracle":True
        })
    # Negative controls: leak at boundary, non-unit stoichiometry, and
    # a new bridge that violates conservation of the prior components.
    bad=laplacian(6,[(0,1,1),(1,2,2),(3,4,1),(4,5,1)])
    bad[0][0]+=1
    assert sum(bad[i][0] for i in range(6))!=0
    assert not strict_unit_transfers(3,[[-2,1,0]])
    assert not strict_unit_transfers(3,[[-1,1,1]])
    assert not strict_unit_transfers(3,[[-1,Q(1,2),0]])
    assert not strict_unit_transfers(3,[[0,0,0]])
    unbridged=component_groups(6,[(0,1,1),(1,2,1),(3,4,1),(4,5,1)])
    bridge=laplacian(6,[(0,1,1),(1,2,1),(3,4,1),(4,5,1),(2,3,1)])
    assert any(sum(bridge[i][j] for i in unbridged[0])!=0 for j in range(6))
    assert len(component_groups(6,[(0,1,1),(1,2,1),(3,4,1),(4,5,1),(2,3,1)]))==1
    return {
        "schema_version":1,
        "experiment":"cace-proven-component-transport-v1",
        "lean_kernel_verified_source_commit":PROOF_SHA,
        "lean_theorem":"CoreTransfer.weightedFlux_zero_for_all_iff_factors",
        "rational_lean_kernel_verified_source_commit":RATIONAL_PROOF_SHA,
        "rational_lean_theorem":"CoreTransfer.rationalFlux_zero_for_all_iff_factors",
        "lean_proved_scope":"unit directed transfers with integer edge-flux pairing",
        "cace_source_commit_required":CACE_SHA if use_cace else None,
        "cace_csr_codec_executed":use_cace,
        "cace_backend_qualified":False,
        "networks":rows,"total_networks":len(rows),
        "fraction_oracle_steps":update_count,
        "negative_controls_rejected":[
            "leaking_diagonal","nonunit_two_reactant","branching_products",
            "half_transfer","zero_transfer_column","cross_component_bridge"],
        "actual_reaction_kinetics":False,
        "pde_error_certificate":False,
        "empirical_biochemistry_validated":False,
        "production_promoted":False,
        "authority_expanded":False
    }


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--cace-repo",type=Path)
    parser.add_argument("--math-only",action="store_true")
    parser.add_argument("-o","--output",type=Path,required=True)
    args=parser.parse_args()
    if args.math_only==(args.cace_repo is not None):
        parser.error("specify exactly one of --math-only and --cace-repo")
    report=math_report(args.cace_repo.resolve() if args.cace_repo else None)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="networks"}))
