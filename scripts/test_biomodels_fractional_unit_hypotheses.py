#!/usr/bin/env python3
"""Pinned SBML dimensional-normalization experiment for two benign kinetics.

Only in-memory XML strings are modified. The source is never overwritten.
SBML L2 units cannot use fractional exponents in declared Unit definitions;
this trial adds explicit 1 mM reference concentrations to normalize powered
bases, and marks additive constants dimensionless. Kinetics are screened by
numerical *samples*, not claimed biologically correct or universally proved.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import xml.etree.ElementTree as ET

import libsbml

PINNED_SHA256="28deec2bf55de027f116b46a8b1a75a820b05bdc9c5cd72dcf260bfacba75302"
MATH="{http://www.w3.org/1998/Math/MathML}"
TARGETS={
 "vDAHPS":{
   "reference":"KrefDAHPS_mM",
   "powers":(("ce4p","nDAHPSe4p"),("cpep","nDAHPSpep")),
   "constants":("KDAHPSe4p","KDAHPSpep"),
   "samples":({"ce4p":0.001,"cpep":0.005},
              {"ce4p":0.035,"cpep":0.01},
              {"ce4p":0.7,"cpep":0.2},
              {"ce4p":4.,"cpep":3.})},
 "vPDH":{
   "reference":"KrefPDH_mM",
   "powers":(("cpyr","nPDH"),),
   "constants":("KPDHpyr",),
   "samples":({"cpyr":0.001},{"cpyr":0.1},
              {"cpyr":3.},{"cpyr":1500.})},
}
EXPECTED_POWER_OCCURRENCES={"vDAHPS":4,"vPDH":2}

def segment(xml,reaction):
    pattern=r'<reaction id="'+re.escape(reaction)+r'"\b[\s\S]*?</reaction>'
    # Full regex uses simple \b and DOTALL; do not match across neighboring reactions.
    match=re.search(r'<reaction id="'+re.escape(reaction)+r'"\b.*?</reaction>',
                    xml,re.DOTALL)
    if match is None: raise ValueError("missing pinned reaction "+reaction)
    return match

def kinetic_xml(reaction_xml):
    root=ET.fromstring(reaction_xml)
    math_node=root.find(".//"+MATH+"math")
    if math_node is None or len(math_node)!=1:
        raise ValueError("unrecognized kinetic MathML")
    scope={}
    for p in root.findall(".//parameter"):
        scope[p.attrib["id"]]=float(p.attrib["value"])
    scope["cytosol"]=1.
    return math_node[0],scope

def math_value(node,values):
    tag=node.tag.split("}")[-1]
    if tag=="ci":
        name=(node.text or "").strip()
        if name not in values:raise ValueError("unknown kinetic name "+name)
        return float(values[name])
    if tag=="cn":return float((node.text or "").strip())
    if tag!="apply" or len(node)<2:raise ValueError("unrecognized kinetic math")
    operator=node[0].tag.split("}")[-1]
    inputs=[math_value(x,values) for x in list(node)[1:]]
    if operator=="plus":return sum(inputs)
    if operator=="times":return math.prod(inputs)
    if operator=="divide" and len(inputs)==2:return inputs[0]/inputs[1]
    if operator=="power" and len(inputs)==2:return inputs[0]**inputs[1]
    if operator=="minus" and len(inputs)==2:return inputs[0]-inputs[1]
    if operator=="minus" and len(inputs)==1:return -inputs[0]
    raise ValueError("unexpected MathML operator "+operator)

def replace_kinetic(xml,reaction):
    spec=TARGETS[reaction]
    match=segment(xml,reaction)
    raw=match.group(0)
    changed=raw
    for c in spec["constants"]:
        patt=r'(<parameter id="'+re.escape(c)+r'"[^>]*\bunits=")mM(")'
        changed,n=re.subn(patt,r'\g<1>dimensionless\g<2>',changed)
        if n!=1:raise ValueError("expected exactly one original mM constant "+c)
    count=0
    for species,exponent in spec["powers"]:
        patt=(r'(<power\s*/>\s*)<ci>\s*'+re.escape(species)+
              r'\s*</ci>(\s*<ci>\s*'+re.escape(exponent)+r'\s*</ci>)')
        def patch(m):
            return (m.group(1)+"<apply><divide/><ci> "+species+
                    " </ci><ci> "+spec["reference"]+" </ci></apply>"+m.group(2))
        changed,n=re.subn(patt,patch,changed)
        if n!=2:raise ValueError("not exactly two matching source powers "+species)
        count+=n
    if count!=EXPECTED_POWER_OCCURRENCES[reaction]:
        raise ValueError("incorrect number of modified powers")
    if changed.count("</listOfParameters>")!=1:
        raise ValueError("ambiguous kinetic parameter scope")
    insert=('<parameter id="'+spec["reference"]+
             '" value="1" units="mM"/>')
    changed=changed.replace("</listOfParameters>",
                            insert+"</listOfParameters>")
    if len(changed)==len(raw):raise AssertionError("trial made no modifications")
    return xml[:match.start()]+changed+xml[match.end():],{
      "reaction_id":reaction,"reference_id":spec["reference"],
      "powers_normalized":count,
      "constants_units_changed":len(spec["constants"])}

def severe(doc):
    doc.checkConsistency()
    return [doc.getError(i).getMessage()
            for i in range(doc.getNumErrors())
            if doc.getError(i).getSeverity()>=libsbml.LIBSBML_SEV_ERROR]

def issue_counts(issues):
    return {k:sum("id '"+k+"'" in m for m in issues)
            for k in ("vENO","vDAHPS","vPDH")}

def experiment(source):
    raw=source.read_bytes()
    if (len(raw)>2_000_000 or hashlib.sha256(raw).hexdigest()!=PINNED_SHA256
        or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper()):
        raise ValueError("source digest, size or entity policy mismatch")
    text=raw.decode("utf-8")
    original=libsbml.readSBMLFromString(text)
    if original.getModel() is None:raise ValueError("pinned model unreadable")
    serious_before=severe(original)
    before_counts=issue_counts(serious_before)
    if before_counts!={"vENO":1,"vDAHPS":1,"vPDH":1}:
        raise ValueError("original model error map drift")
    result=[]
    for selection in (("vDAHPS",),("vPDH",),("vDAHPS","vPDH")):
        altered=text; edits=[]
        for name in selection:
            altered,metadata=replace_kinetic(altered,name)
            edits.append(metadata)
        if len(altered)<=len(text):raise AssertionError("reference not inserted")
        trial=libsbml.readSBMLFromString(altered)
        if trial.getModel() is None:raise ValueError("altered SBML unreadable")
        if (trial.getModel().getNumReactions()!=original.getModel().getNumReactions()
            or trial.getModel().getNumSpecies()!=original.getModel().getNumSpecies()):
            raise ValueError("model topology changed")
        errors=severe(trial)
        comparisons=[]
        for name in selection:
            before_m,before_k=kinetic_xml(segment(text,name).group(0))
            after_m,after_k=kinetic_xml(segment(altered,name).group(0))
            for sample in TARGETS[name]["samples"]:
                a=math_value(before_m,{**before_k,**sample})
                b=math_value(after_m,{**after_k,**sample})
                if not math.isfinite(a) or not math.isfinite(b):
                    raise ValueError("nonfinite kinetic trial")
                if abs(a-b)>1e-11*max(1.,abs(a),abs(b)):
                    raise ValueError("kinetic numerical mutation")
                comparisons.append({"reaction":name,"relative_error":abs(a-b)/max(1.,abs(a),abs(b))})
            # Deliberate negative control: if the new 1 mM ref is mistakenly
            # 2 mM the formula must diverge at least at one test input.
            altered_ref={**after_k,TARGETS[name]["reference"]:2.0}
            if not any(abs(math_value(after_m,{**after_k,**sample})-
                           math_value(after_m,{**altered_ref,**sample}))>1e-6
                       for sample in TARGETS[name]["samples"]):
                raise AssertionError("reference-concentration mutant survived")
        result.append({
          "selection":list(selection),"edits":edits,
          "candidate_sha256":hashlib.sha256(altered.encode()).hexdigest(),
          "severe_issue_count":len(errors),"target_issue_counts":issue_counts(errors),
          "numeric_holdouts":len(comparisons),
          "max_relative_kinetic_difference":max(x["relative_error"] for x in comparisons),
          "reference_molarity_mutant_detected":True,
          "candidate_satisfies_10541_for_selected":all(
            issue_counts(errors)[name]==0 for name in selection),
          "remaining_serious_diagnostics":errors[:5],
          "biochemical_truth_qualified":False,"formal_equivalence_proved":False,
          "production_model_replaced":False,"promotion_authorized":False})
    return {
      "schema_version":1,"experiment":"biomodels-fractional-powers-normalization-v1",
      "original_source_sha256":PINNED_SHA256,"original_severe":len(serious_before),
      "original_10541":before_counts,"candidates":result,
      "upstream_source_modified":False,"independent_solver_executed":False,
      "empirical_parameters_verified":False,"promotion_authorized":False}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--sbml",type=Path,required=True)
    parser.add_argument("-o",type=Path,required=True)
    args=parser.parse_args()
    out=experiment(args.sbml)
    args.o.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"original_severe":out["original_severe"],
      "trials":[{"selection":x["selection"],
                 "severe":x["severe_issue_count"],
                 "numeric_holdouts":x["numeric_holdouts"]}
                for x in out["candidates"]],
      "biochemical_truth_qualified":False}))

if __name__=="__main__":main()
