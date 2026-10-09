#!/usr/bin/env python3
"""Read-only provenance/consistency intake of a curated public BioModels case.

BIOMD0000000051 = Chassagnole et al. 2002 central carbon metabolism.
Pinned BioModels CC0 repository source is NOT executed or imported as Python.
SBML is parsed by independent libSBML. This is model-quality screening only,
NOT reproduction of the source publication's figures or CACE qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import libsbml

UPSTREAM_SHA = "92843fdc466e704445d491fb42b4142d4c70c3f6"
XML_BLOB = "e447a9b0ba35ba0156b97c07caaad94631a448cf"
SBML_PATH = "BIOMD0000000051/BIOMD0000000051.xml"


def inspect(path):
    data = path.read_bytes()
    if len(data) > 2_000_000 or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("unexpected external DTD or oversized SBML")
    blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if blob != XML_BLOB:
        raise ValueError("source bytes do not match pinned upstream model blob")
    document = libsbml.readSBMLFromFile(str(path))
    model = document.getModel()
    if model is None or document.getLevel()!=2:
        raise ValueError("malformed or unsupported source SBML")
    ids=[model.getSpecies(i).getId() for i in range(model.getNumSpecies())]
    if len(ids)!=len(set(ids)):
        raise ValueError("duplicate species ids")
    first_errors=[]
    document.checkConsistency()
    issues=[]
    severe=0
    for i in range(document.getNumErrors()):
        issue=document.getError(i)
        item={"id":issue.getErrorId(),"severity":issue.getSeverity(),
              "line":issue.getLine(),"column":issue.getColumn(),
              "message":issue.getMessage().strip()[:1500]}
        issues.append(item)
        if issue.getSeverity()>=libsbml.LIBSBML_SEV_ERROR:
            severe+=1
            if len(first_errors)<20:
                first_errors.append(item)
    reactions=model.getNumReactions()
    with_kinetics=sum(model.getReaction(i).isSetKineticLaw()
                      for i in range(reactions))
    missing_kinetics=[model.getReaction(i).getId() for i in range(reactions)
                      if not model.getReaction(i).isSetKineticLaw()]
    # Deliberately do NOT assert every species is a conserved molar amount;
    # source has open-system fluxes, analytical and dynamic variables.
    result={
        "schema_version":1,
        "experiment":"pinned-biomodels-carbon-metabolism-source-intake-v1",
        "repo":"biomodels/BIOMD0000000051",
        "commit":UPSTREAM_SHA,"sbml_git_blob":blob,
        "sbml_sha256":hashlib.sha256(data).hexdigest(),
        "model":model.getId(),"sbml_level":document.getLevel(),
        "sbml_version":document.getVersion(),
        "species_count":model.getNumSpecies(),"reactions":reactions,
        "reactions_with_kinetics":with_kinetics,
        "reactions_without_kinetics":missing_kinetics,
        "compartments":model.getNumCompartments(),
        "parameters":model.getNumParameters(),
        "events":model.getNumEvents(),
        "rules":model.getNumRules(),
        "function_definitions":model.getNumFunctionDefinitions(),
        "libsbml_issues":len(issues),"libsbml_severe_issues":severe,
        "libsbml_issue_counts_by_id":{
            str(code):sum(e["id"]==code for e in issues)
            for code in sorted({e["id"] for e in issues})
        },
        "qualification_state":("quarantined_serious_consistency_findings"
                               if severe else "passed_standards_intake_only"),
        "first_serious_validation_findings":first_errors,
        "curator_noted_paper_to_model_formula_adjustments":True,
        "kinetic_parameter_provenance_needs_review":True,
        "figures_reproduced":False,"biological_truth_qualified":False,
        "cace_solvers_executed":False,"permissions_expanded":False,
    }
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--sbml",type=Path,required=True)
    parser.add_argument("-o",required=True)
    args=parser.parse_args()
    report=inspect(args.sbml)
    dest=Path(args.o)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items()
                      if k not in ("first_serious_validation_findings",
                                   "reactions_without_kinetics")}))
    if report["libsbml_severe_issues"]:
        raise SystemExit("source consistency issues require explicit review")
