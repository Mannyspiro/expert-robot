#!/usr/bin/env python3
"""Fail-closed offline qualification of CC0 BioModels BIOMD0000000051.

This source-intake gate checks bytes/structure plus independent libSBML
consistency. It does not simulate, calibrate or claim mechanistic truth.

The legacy SBML Level 2 model contains time-dependent mathematics,
seven assignment rules and two compartments. Never silently simplify
these into a closed, constant-rate ODE.
"""
import argparse
import hashlib
import json
from pathlib import Path
import libsbml

EXPECTED_GIT_BLOB = "e447a9b0ba35ba0156b97c07caaad94631a448cf"
EXPECTED_ID = "Chassagnole2002_Carbon_Metabolism"
EXPECTED_RULE_VARS = {"catp","cadp","camp","cnadph","cnadp","cnadh","cnad"}
EXPECTED_COUNTS = dict(species=18,reactions=48,compartments=2,
                       parameters=142,assignment_rules=7)


def preflight(path):
    data=path.read_bytes()
    if len(data)>2_000_000 or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("unexpected source size or XML DTD")
    git_blob=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
    if git_blob!=EXPECTED_GIT_BLOB:
        raise ValueError("offline BioModels file differs from pinned upstream blob")
    doc=libsbml.readSBMLFromString(data.decode("utf-8"))
    if doc.getModel() is None or doc.getLevel()!=2 or doc.getVersion()!=1:
        raise ValueError("SBML level/version/model differs")
    model=doc.getModel()
    if model.getId()!=EXPECTED_ID:
        raise ValueError("model ID differs")
    rules=[model.getRule(i) for i in range(model.getNumRules())]
    rule_vars=[r.getVariable() for r in rules if r.isAssignment()]
    reaction_kinetics=sum(model.getReaction(i).isSetKineticLaw()
                          for i in range(model.getNumReactions()))
    count=dict(species=model.getNumSpecies(),reactions=model.getNumReactions(),
               compartments=model.getNumCompartments(),
               parameters=model.getNumParameters(),
               assignment_rules=len(rule_vars))
    if count!=EXPECTED_COUNTS or set(rule_vars)!=EXPECTED_RULE_VARS or (
            model.getNumRules()!=len(rule_vars)):
        raise ValueError("unexpected biological model structure")
    if reaction_kinetics!=48:
        raise ValueError("missing kinetic rate law")
    compartments=sorted(model.getCompartment(i).getId()
                        for i in range(model.getNumCompartments()))
    if compartments!=["cytosol","extracellular"]:
        raise ValueError("compartment contract changed")
    source=data.decode("utf-8")
    time_symbols=source.count("<csymbol")
    if time_symbols==0:
        raise ValueError("time dependence unexpectedly absent")
    # Legacy consistency errors must be surfaced rather than hidden.
    doc.checkConsistency()
    errors=[]
    warnings=[]
    for i in range(doc.getNumErrors()):
        error=doc.getError(i)
        info={"severity":error.getSeverity(),"error_id":error.getErrorId(),
              "category":error.getCategory(),"message":error.getMessage().strip()[:600]}
        if error.getSeverity()>=libsbml.LIBSBML_SEV_ERROR:
            errors.append(info)
        else:
            warnings.append(info)
    return {
      "schema_version":1,"experiment":"biomodels-0051-offline-intake-v2",
      "upstream":"biomodels/BIOMD0000000051",
      "upstream_commit":"92843fdc466e704445d491fb42b4142d4c70c3f6",
      "source_git_blob":git_blob,
      "source_sha256":hashlib.sha256(data).hexdigest(),
      "source_bytes":len(data),
      "sbml_level":doc.getLevel(),"sbml_version":doc.getVersion(),
      "model_id":model.getId(),"counts":count,
      "reaction_kinetic_laws":reaction_kinetics,
      "compartments":compartments,
      "assignment_rule_variables":sorted(rule_vars),
      "mathml_csymbol_occurrences":time_symbols,
      "libsbml_severe_issue_count":len(errors),
      "libsbml_warning_count":len(warnings),
      "first_severe_issues":errors[:30],
      "first_warnings":warnings[:20],
      "source_structure_ok":True,
      "time_dependent_kinetics_reproduced":False,
      "manuscript_figures_reproduced":False,
      "cace_execution":False,"lean_qualification":False,
      "authority_expanded":False,
    }


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--sbml",type=Path,required=True)
    p.add_argument("-o","--output",type=Path,required=True)
    args=p.parse_args()
    try:
        result=preflight(args.sbml)
    except Exception as e:
        args.output.write_text(json.dumps({
            "schema_version":1,"state":"preflight_exception","error":str(e),
            "qualified":False},indent=2)+"\n")
        raise
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items()
                      if k not in ("first_severe_issues","first_warnings")}))
    if result["libsbml_severe_issue_count"]!=0:
        raise SystemExit("libSBML reported severe source issues: inspect artifact")
