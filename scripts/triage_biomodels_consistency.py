#!/usr/bin/env python3
"""Quarantine-first reaction-unit triage for pinned published BioModels source."""
import argparse
import hashlib
import json
from pathlib import Path

REPO="biomodels/BIOMD0000000051"
COMMIT="92843fdc466e704445d491fb42b4142d4c70c3f6"
BLOB="e447a9b0ba35ba0156b97c07caaad94631a448cf"

def triage(report):
    if not isinstance(report,dict) or any(report.get(k)!=v for k,v in (
       ("repo",REPO),("commit",COMMIT),("sbml_git_blob",BLOB))):
        raise ValueError("source identity mismatch")
    counts=report.get("libsbml_issue_counts_by_id")
    if not isinstance(counts,dict) or not all(
       isinstance(k,str) and k.isdigit() and type(v) is int and v>=0
       for k,v in counts.items()):
        raise ValueError("malformed diagnostic counts")
    severe=report.get("libsbml_severe_issues")
    if type(severe) is not int or not 0<=severe<=sum(counts.values()):
        raise ValueError("invalid severe count")
    details=report.get("first_serious_validation_findings")
    if not isinstance(details,list) or any(
       not isinstance(item,dict) or not {"id","severity","message"}<=set(item)
       for item in details):
        raise ValueError("missing serious findings")
    dimension_count=counts.get("10541",0)
    examples=[{"line":x.get("line"),"column":x.get("column"),
               "message":x["message"][:1500]} for x in details
              if x["id"]==10541]
    if dimension_count and (not examples or dimension_count>severe):
        raise ValueError("missing kinetic-dimensional evidence")
    return {
      "schema_version":1,"experiment":"pinned-biomodels-unit-triage-v1",
      "repo":REPO,"source_commit":COMMIT,"xml_git_blob":BLOB,
      "source_receipt_sha256":hashlib.sha256(json.dumps(
          report,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
      "total_diagnostics":sum(counts.values()),"severe_issues":severe,
      "dimension_mismatch_10541_count":dimension_count,
      "known_issue_examples":examples,
      "quarantined":severe>0,
      "required_reviews":["identify kinetic-law MathML at reported source line",
        "check species/compartment amount-concentration conversions",
        "audit derived parameter and per-time units",
        "propose versioned correction outside pinned source",
        "independently replay corrected ODE and sealed holdouts"],
      "original_source_modified":False,"upstream_fix_claimed":False,
      "published_model_reproduced":False,"cace_qualified":False,
      "promotion_authorized":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--intake",type=Path,required=True)
    p.add_argument("-o",type=Path,required=True)
    a=p.parse_args()
    result=triage(json.loads(a.intake.read_text()))
    a.o.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in (
       "quarantined","severe_issues","dimension_mismatch_10541_count")}))

if __name__=="__main__":main()
