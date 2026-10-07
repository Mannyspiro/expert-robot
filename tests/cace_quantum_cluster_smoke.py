#!/usr/bin/env python3
"""Networked CACE quantum aggregation: reject forged, duplicated or missing work.

No PySCF/CACE clone required for pure protocol tests; integration separately
loads two actual CACE copies and runs live quantum tasks.
"""
import copy
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "quantum_cluster",ROOT/"scripts"/"cace_quantum_cluster.py"
)
q=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(q)

token="this-is-a-test-token-of-sufficient-length-with-no-access"
graph={"matter_id":"test","nodes":[],"edges":[]}
digest=q.sha(graph)
assert q.sha(graph)==q.sha(copy.deepcopy(graph))
answers=[]
for worker,basis,energy,basis_size in [
    ("cace-1","sto-3g",-74.9,7),
    ("cace-2","6-31g",-75.9,13),
]:
    body={
        "job_id":"quantum:"+basis,
        "worker_id":worker,
        "cace_commit":q.CACE_PIN,
        "input_graph_sha256":digest,
        "basis":basis,
        "quantum":{
            "input_graph_sha256":digest,
            "scf_results":[{
                "basis":basis,"converged":True,
                "total_electronic_energy_hartree":energy,
                "basis_functions":basis_size,
                "electrons":10,
            }],
        },
    }
    answers.append({"result":body,"attestation_hmac":q.mac_of(token,body)})

out=q.merge_results(graph,answers,token,q.CACE_PIN)
assert out["worker_count"]==2
assert out["scf_results"][0]["basis"]=="sto-3g"
assert out["scf_results"][1]["basis"]=="6-31g"
assert abs(out["basis_energy_difference_hartree"]+1.0)<1e-10
assert out["distributed_single_scf"] is False
assert out["readiness"]["production_release"] is False

def reject(payload):
    try:
        q.merge_results(graph,payload,token,q.CACE_PIN)
    except (ValueError,KeyError):
        return
    raise AssertionError("invalid cluster response incorrectly accepted")

bad=copy.deepcopy(answers)
bad[1]["result"]["worker_id"]="cace-1"
bad[1]["attestation_hmac"]=q.mac_of(token,bad[1]["result"])
reject(bad)

bad=copy.deepcopy(answers)
bad[0]["result"]["quantum"]["scf_results"][0]["converged"]=False
bad[0]["attestation_hmac"]=q.mac_of(token,bad[0]["result"])
reject(bad)

bad=copy.deepcopy(answers)
bad[1]["result"]["cace_commit"]="unverified"
bad[1]["attestation_hmac"]=q.mac_of(token,bad[1]["result"])
reject(bad)

bad=copy.deepcopy(answers)
bad[1]["result"]["input_graph_sha256"]="0"*64
bad[1]["attestation_hmac"]=q.mac_of(token,bad[1]["result"])
reject(bad)

bad=copy.deepcopy(answers)
bad[0]["attestation_hmac"]="0"*64
reject(bad)

reject(answers[:1])

bad=copy.deepcopy(answers)
bad[1]["result"]["basis"]="sto-3g"
bad[1]["attestation_hmac"]=q.mac_of(token,bad[1]["result"])
reject(bad)

try:
    q.start_workers(["/tmp/identical","/tmp/identical"], token,q.CACE_PIN)
except ValueError:
    pass
else:
    raise AssertionError("duplicate CACE roots accepted")

print("networked CACE quantum result aggregation: PASS")
