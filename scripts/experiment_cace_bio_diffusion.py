#!/usr/bin/env python3
"""CACE-backed 1D toy diffusion/sparse-operator invariant experiment.

Requires a read-only checkout of the user's authorized CACE repository.
Uses the actual CACE FEM CSR encode/decode utilities, with an independent
Fraction oracle. This is not a reaction kinetics solver or a PDE certificate.
"""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import sys

def run(root):
    import numpy as np
    sys.path.insert(0,str(root))
    from cace_studio.modules.fem import _csr_from_dense, _dense_from_csr
    lap=np.array([[1.,-1.,0.],[-1.,2.,-1.],[0.,-1.,1.]])
    sparse=_csr_from_dense(lap,tol=0.)
    recovered=np.asarray(_dense_from_csr(sparse),dtype=float)
    if not np.array_equal(lap,recovered):
        raise AssertionError("CACE CSR roundtrip failed")
    if not np.array_equal(lap.sum(axis=0),np.zeros(3)):
        raise AssertionError("zero-flux conservation assumption failed")
    exact=[[F(int(x)) for x in row] for row in lap]
    dt=F(1,10)
    trials=[]
    for init in ((1,0,0),(1,2,4),(3,3,3)):
        rational=[F(x) for x in init]
        numeric=np.array(init,dtype=float)
        before=sum(rational)
        for _ in range(8):
            rhs=[sum(exact[i][j]*rational[j] for j in range(3)) for i in range(3)]
            rational=[rational[i]-dt*rhs[i] for i in range(3)]
            numeric=numeric-0.1*(recovered@numeric)
            if sum(rational)!=before:
                raise AssertionError("exact conservation failed")
            if max(abs(float(q)-v) for q,v in zip(rational,numeric))>1e-12:
                raise AssertionError("CACE operator deviates from oracle")
            if any(x<0 for x in rational):
                raise AssertionError("toy positivity failed")
        trials.append({"initial":init,"steps":8,"exact_mass_residual":0,
                       "matches_independent_Fraction_oracle":True})
    bad=lap.copy()
    bad[0,0]+=1.
    assert any(abs(x)>0 for x in bad.sum(axis=0))
    return {
        "schema_version":1,"experiment":"cace-bio-toy-diffusion-sparse-v1",
        "cace_utility":"cace_studio.modules.fem CSR codec",
        "operator":"three-cell no-flux symmetric graph Laplacian",
        "csr_roundtrip_exact":True,"numeric_oracle_matches":True,
        "cases":trials,"steps":24,"wrong_boundary_flux_mutation_detected":True,
        "external_biological_measurements":0,
        "pde_certification_performed":False,"reaction_kinetics_integrated":False,
        "user_runtime_modified":False,"promotion_or_authority_expanded":False,
    }

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cace-repo",type=Path,required=True)
    p.add_argument("-o",required=True)
    args=p.parse_args()
    report=run(args.cace_repo.resolve())
    Path(args.o).write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report))
