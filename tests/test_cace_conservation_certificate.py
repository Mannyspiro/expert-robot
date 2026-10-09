#!/usr/bin/env python3
"""Independent certificate replay: fixed/random networks and hostile mutations."""
import copy,hashlib,importlib.util,json,random
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,str(ROOT/path))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod
p=load("producer","scripts/generate_cace_conservation_certificate.py")
v=load("verifier","scripts/verify_cace_conservation_certificate.py")
def network(names,columns):
    return {"species":names,"reactions":["r"+str(i) for i in range(len(columns))],
            "stoichiometry":[[str(col[i]) for col in columns] for i in range(len(names))]}
def redigest(c):
    body={k:x for k,x in c.items() if k!="certificate_sha256"}
    c["certificate_sha256"]=hashlib.sha256(v.canonical(body)).hexdigest()
def reject(c,reason):
    try:v.verify(c)
    except (ValueError,TypeError,ZeroDivisionError):return
    raise AssertionError("malformed certificate accepted: "+reason)

def run():
    examples=[
      network(["E","S","ES","P"],[[-1,-1,1,0],[1,1,-1,0],[1,0,-1,1]]),
      network(["A","B","C","D"],[[-1,1,0,0],[1,-1,0,0],[0,0,-1,1]]),
      network(["A","B","C"],[[-2,1,0],[0,-1,1]]),
      network(["A","B","C","D","E"],[[-1,1,0,0,0],[0,0,-1,1,0]]),
      network(["A","B","C"],[[-1,0,0],[0,-1,0],[0,0,-1]]),
      network(["A","B"],[[-1,"3/2"]])
    ]
    expected=["rational_rref","component_graph","rational_rref",
              "component_graph","rational_rref","rational_rref"]
    for spec,method in zip(examples,expected):
        c=p.generate(spec)
        assert v.verify(c)["method"]==method
    rng=random.Random(20261009)
    randoms=0
    for n in range(2,12):
        for k in range(9):
            cols=[]
            for _ in range(max(1,n-2)):
                a,b=rng.sample(range(n),2)
                col=[0]*n;col[a]=-1;col[b]=1;cols.append(col)
            if k%3==1:cols[0][0]+=2
            if k%3==2:cols[0][0]+=1
            spec=network(["S"+str(i) for i in range(n)],cols)
            assert v.verify(p.generate(spec))["valid"]
            randoms+=1
    orig=p.generate(examples[0])
    mutations=[
      ("wrong_rank",lambda c:c.update(rank=c["rank"]+1)),
      ("missing_law_count",lambda c:c.update(candidate_conservation_laws=1)),
      ("broken_basis",lambda c:c["left_nullspace_basis"][0].__setitem__(0,"3")),
      ("dependent_basis",lambda c:c["left_nullspace_basis"].__setitem__(1,c["left_nullspace_basis"][0])),
      ("fake_lean",lambda c:c.update(lean_kernel_checked=True)),
      ("fake_cace",lambda c:c.update(cace_runtime_checked=True)),
      ("fake_biology",lambda c:c.update(biological_mechanism_validated=True)),
      ("authority_expanded",lambda c:c.update(authority_expanded=True)),
      ("method_forgery",lambda c:c.update(method="component_graph")),
      ("altered_stoichiometry",lambda c:c["stoichiometry"][0].__setitem__(0,"-2")),
      ("noncanonical",lambda c:c["stoichiometry"][0].__setitem__(0,"-1.0")),
      ("unknown_schema",lambda c:c.update(schema="unknown")),
      ("digest_forgery",lambda c:c.update(certificate_sha256="0"*64)),
      ("source_hash_forgery",lambda c:c.update(source_sha256="0"*64)),
      ("missing_basis",lambda c:c["left_nullspace_basis"].pop())
    ]
    for name,change in mutations:
        forged=copy.deepcopy(orig);change(forged)
        if name!="digest_forgery":redigest(forged)
        reject(forged,name)
    raw=copy.deepcopy(examples[0]);raw["stoichiometry"][0][0]="-2/2"
    assert v.verify(p.generate(raw))["valid"]
    result={"fixed_examples":len(examples),"random_examples":randoms,
            "certificates_independently_verified":len(examples)+randoms+1,
            "forgeries_rejected":len(mutations),"graph_and_general_methods":True,
            "lean_kernel_checked":False,"cace_runtime_checked":False,
            "production_authority_expanded":False}
    print(json.dumps(result))
    return result

if __name__=="__main__":run()
