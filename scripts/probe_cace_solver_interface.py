#!/usr/bin/env python3
"""Read-only extract of pinned CACE FEM solver/residual API contracts.

This is a static API inventory, NOT solver qualification.
Only collect declared methods of explicitly allowlisted FEM classes.
Never read runtime secrets, environment variables, or other repo files.
"""
import argparse,ast,hashlib,json
from pathlib import Path

CACE_PIN="66b22a71ff52b3110269f5994a5fd0716a2054c1"
ALLOWED=("ArbitraryMesh1D","P1ShapeFunctions","PoissonAssembly1D",
         "LinearPDESolver","AlgebraicResidual","AposterioriEstimator1D",
         "PipelineCertificate")
METHODS=("__init__","validate","execute","verify")
def run(path):
    source=path.read_text(encoding="utf-8")
    tree=ast.parse(source,filename=str(path))
    classes={}
    for cls in tree.body:
        if not isinstance(cls,ast.ClassDef) or cls.name not in ALLOWED:
            continue
        funcs=[]
        for node in cls.body:
            if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) or node.name not in METHODS:
                continue
            decl=source.splitlines()
            fragment="\n".join(decl[node.lineno-1:node.end_lineno])
            if len(fragment)>10000:
                raise ValueError("unexpected huge method")
            funcs.append({"name":node.name,"lineno":node.lineno,"source":fragment})
        classes[cls.name]={"base_classes":[ast.unparse(x) for x in cls.bases],
                           "methods":funcs}
    missing=set(ALLOWED)-set(classes)
    if missing:
        raise ValueError("required CACE classes missing: "+repr(sorted(missing)))
    return {"schema_version":1,"experiment":"cace-fem-solver-api-audit",
            "pinned_cace_revision":CACE_PIN,
            "fem_sha256":hashlib.sha256(source.encode()).hexdigest(),
            "classes":classes,"source_audit_only":True,
            "solver_executed":False,"authority_expanded":False}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--cace-repo",type=Path,required=True)
    p.add_argument("-o","--output",type=Path,required=True)
    args=p.parse_args()
    result=run(args.cace_repo/"cace_studio/modules/fem.py")
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"classes":{name:[x["name"] for x in value["methods"]]
      for name,value in result["classes"].items()},
      "revision":CACE_PIN,"solver_executed":False}))
