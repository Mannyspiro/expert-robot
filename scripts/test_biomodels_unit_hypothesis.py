#!/usr/bin/env python3
"""One isolated in-memory unit-annotation trial on pinned BioModels source.

No original file modifications, approved model, biochemical calibration,
simulation result, or CACE qualification arise from this exploratory test.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import libsbml

LOCKED_SHA256="28deec2bf55de027f116b46a8b1a75a820b05bdc9c5cd72dcf260bfacba75302"

def problems(document):
    document.checkConsistency()
    return [{"id":document.getError(i).getErrorId(),
             "message":document.getError(i).getMessage()[:1500]}
            for i in range(document.getNumErrors())
            if document.getError(i).getSeverity()>=libsbml.LIBSBML_SEV_ERROR]

def eno_mismatch(rows):
    return sum(item["id"]==10541 and "id 'vENO'" in item["message"]
               for item in rows)

def experiment(source):
    data=source.read_bytes()
    if len(data)>2_000_000 or hashlib.sha256(data).hexdigest()!=LOCKED_SHA256:
        raise ValueError("source bytes do not match expected pinned model")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("external entity syntax forbidden")
    original=data.decode("utf-8")
    before=libsbml.readSBMLFromString(original)
    if before.getModel() is None:raise ValueError("source SBML unreadable")
    severe_before=problems(before)
    if eno_mismatch(severe_before)!=1:
        raise ValueError("expected pinned vENO mismatch unavailable")
    # Only a dimensional annotation trial, not a proposed kinetics repair.
    pattern=r'(<parameter id="KENOeq"[^>]*\bunits=")mM(")'
    changed,count=re.subn(pattern,r'\g<1>dimensionless\g<2>',original)
    if count!=1:raise ValueError("unexpected KENOeq annotation count")
    after=libsbml.readSBMLFromString(changed)
    if after.getModel() is None:raise ValueError("trial XML unreadable")
    if (after.getModel().getNumReactions()!=before.getModel().getNumReactions()
        or after.getModel().getNumSpecies()!=before.getModel().getNumSpecies()):
        raise ValueError("trial changed model topology")
    severe_after=problems(after)
    return {
      "schema_version":1,"experiment":"biomodels-vENO-unit-hypothesis-v1",
      "original_source_sha256":LOCKED_SHA256,
      "derived_ephemeral_sha256":hashlib.sha256(changed.encode()).hexdigest(),
      "trial":"vENO KENOeq unit annotation mM -> dimensionless",
      "annotation_edits":count,
      "original_severe_count":len(severe_before),
      "trial_severe_count":len(severe_after),
      "original_vENO_10541":eno_mismatch(severe_before),
      "trial_vENO_10541":eno_mismatch(severe_after),
      "remaining_severe_findings":severe_after,
      "unit_hypothesis_supported":(eno_mismatch(severe_after)==0 and
                                   len(severe_after)<len(severe_before)),
      "original_source_modified":False,
      "simulations_reproduced":False,"biological_model_qualified":False,
      "cace_backend_executed":False,"promotion_authorized":False
    }

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--sbml",type=Path,required=True)
    p.add_argument("-o",type=Path,required=True)
    args=p.parse_args()
    report=experiment(args.sbml)
    args.o.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in (
       "trial","original_severe_count","trial_severe_count",
       "unit_hypothesis_supported","biological_model_qualified")}))
