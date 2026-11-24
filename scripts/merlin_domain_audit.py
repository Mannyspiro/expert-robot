#!/usr/bin/env python3
"""Audit primary discipline ownership and explicit cross-domain relationships."""
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
    by_id={d.get("id"):d for d in domains}
    occurrences=defaultdict(list)
    for d in domains:
        if not d.get("id") or not d.get("name"): errors.append("domain missing id or name")
        if d.get("status") not in allowed: errors.append("invalid status for domain "+str(d.get("id")))
        if not isinstance(d.get("branches"),list):
            errors.append("branches must be a list for "+str(d.get("id"))); continue
        for item in d["branches"]:
            if not isinstance(item,str) or not item.strip():
                errors.append("empty/non-string branch in "+str(d.get("id"))); continue
            occurrences[norm(item)].append({"domain":d["id"],"label":item,"domain_status":d.get("status")})

    relationships=taxonomy.get("cross_domain_relationships",[])
    rel_by_label={}
    checked_relationships=[]
    for rel in relationships:
        label=norm(str(rel.get("label","")))
        primary=rel.get("primary_domain")
        secondary=rel.get("secondary_domains",[])
        if not label: errors.append("cross-domain relationship missing label"); continue
        if label in rel_by_label: errors.append("duplicate cross-domain relationship: "+label)
        rel_by_label[label]=rel
        if primary not in by_id: errors.append("unknown primary domain for "+label)
        if not isinstance(secondary,list) or not secondary: errors.append("secondary_domains must be a non-empty list for "+label); secondary=[]
        if primary in secondary: errors.append("primary domain repeated as secondary for "+label)
        if any(x not in by_id for x in secondary): errors.append("unknown secondary domain for "+label)
        if primary in by_id and label not in {norm(x) for x in by_id[primary].get("branches",[])}:
            errors.append("cross-domain label must be listed in its primary domain: "+label)
        for secondary_id in secondary:
            if secondary_id in by_id and label in {norm(x) for x in by_id[secondary_id].get("branches",[])}:
                errors.append("secondary-domain duplicate must be removed; relationship metadata carries the link: "+label)
        checked_relationships.append({"label":rel.get("label"),"primary_domain":primary,"secondary_domains":secondary,"relationship":rel.get("relationship"),"scope_rationale":rel.get("scope_rationale")})

    duplicates=[]
    for label, entries in occurrences.items():
        if len(entries)>1:
            duplicates.append({"normalized_label":label,"assignments":entries})
            errors.append("multiple primary-domain assignments: "+label)
    for label, rel in rel_by_label.items():
        if label not in occurrences:
            errors.append("cross-domain relationship has no primary branch entry: "+label)

    emerging=next((d for d in domains if d.get("id")=="emerging"),None)
    if emerging and emerging.get("status") not in ("emerging","speculative"):
        errors.append("emerging domain must remain speculative/emerging")
    historical_ids=[x.get("id") for x in taxonomy.get("historical_programs",[])]
    if len(historical_ids)!=len(set(historical_ids)): errors.append("duplicate historical program ids")
    return {
      "ok":not errors,"errors":errors,"warnings":warnings,"domain_count":len(domains),
      "branch_assignment_count":sum(len(d.get("branches",[])) for d in domains),
      "duplicate_primary_assignments":duplicates,
      "cross_domain_relationships":checked_relationships,
      "note":"Each branch has one primary home. Cross-domain participation is expressed explicitly in relationship metadata, never by duplicate primary assignments."
    }


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
