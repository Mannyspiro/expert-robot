"""Read-only hypothetical decisions; replayed input is never verified market evidence."""
from .research_snapshot import replay, DATA_CLASS
from .business_decision import rank_opportunities, implementation_plan

def evaluate(candidates, snapshots):
    if not isinstance(snapshots,list) or len(snapshots)>20:
        raise ValueError("bounded snapshots required")
    evidence={}
    for record in snapshots:
        page=replay(record)
        existing=evidence.get(page.source_sha256)
        if existing is not None and existing != page.url:
            raise ValueError("ambiguous body hash across source URLs")
        evidence[page.source_sha256]=page.url
    ranked=rank_opportunities(candidates)
    for item in ranked:
        if not set(item["evidence_hashes"]).issubset(evidence):
            raise ValueError("unresolved evidence reference")
        item["source_urls"]=[evidence[h] for h in item["evidence_hashes"]]
        item["evidence_integrity_replayed"]=True
        item["evidence_data_class"]=DATA_CLASS
        item["source_authenticity_verified"]=False
        item["ranking_basis"]="hypothetical_assumptions_only"
    return {"data_class":"hypothetical_scenario","execution_authorized":False,
            "verified_real":False,"claims_verified":0,"ranked":ranked,
            "plans":[implementation_plan(item) for item in ranked]}
