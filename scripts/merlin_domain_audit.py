#!/usr/bin/env python3
"""Audit Merlin's discipline taxonomy for malformed and wrongly scoped entries."""
import argparse, json, re
from collections import defaultdict
from pathlib import Path

def norm(value):
    return re.sub(r"[^a-z0-9]+"," ",value.casefold()).strip()

def audit(taxonomy, governance):
    errors=[]; warnings=[]; domains=taxonomy.get("domains",[])
    ids=[d.get("id") for d in domains]
    if len(ids)!=len(set(ids)): errors.append("duplicate domain ids")
    allowed=set(taxonomy.get("status_vocabulary",[]))
    occurrences=defaultdict(list)
    for d in domains:
        if not d.get("id") or not d.get("name"): errors.append("domain missing id or name")
        if d.get("status") not in allowed: errors.append("invalid status for domain "+str(d.get("id")))
        if not isinstance(d.get("branches"),list): errors.append("branches must be a list for "+str(d.get("id"))); continue
        for item in d["branches"]:
            if not isinstance(item,str) or not item.strip():
                errors.append("empty/non-string branch in "+str(d.get("id"))); continue
            occurrences[norm(item)].append({"domain":d["id"],"label":item,"domain_status":d.get("status")})
    permitted={norm(x) for x in governance.get("known_cross_domain_labels",[])}
    duplicates=[]
    for label, entries in occurrences.items():
        if len(entries)>1:
            item={"normalized_label":label,"assignments":entries}
            if label in permitted: item["classification"]="declared_cross_domain"
            else: item["classification"]="scope_review_required"; warnings.append("unmapped cross-domain overlap: "+label)
            duplicates.append(item)
    emerging=next((d for d in domains if d.get("id")=="emerging"),None)
    if emerging and emerging.get("status") not in ("emerging","speculative"):
        errors.append("emerging domain must remain speculative/emerging")
    historical_ids={x.get("id") for x in taxonomy.get("historical_programs",[])}
    if len(historical_ids)!=len(taxonomy.get("historical_programs",[])): errors.append("duplicate historical program ids")
    return {"ok":not errors,"errors":errors,"warnings":warnings,"domain_count":len(domains),
            "branch_assignment_count":sum(len(d.get("branches",[])) for d in domains),
            "cross_domain_overlaps":duplicates,
            "note":"Overlaps are not automatically errors: shared disciplines require explicit cross-domain justification. No item is reassigned by name matching."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--taxonomy",type=Path,required=True); p.add_argument("--governance",type=Path,required=True)
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    result=audit(json.loads(a.taxonomy.read_text()),json.loads(a.governance.read_text()))
    rendered=json.dumps(result,indent=2,sort_keys=True)
    if a.out: a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(rendered+"\n")
    print(rendered); return 0 if result["ok"] else 2
if __name__=="__main__": raise SystemExit(main())
