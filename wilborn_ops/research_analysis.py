"""Deterministic evidence coverage analysis; not semantic truth verification."""
from collections import Counter
from .research_ingest import DATA_CLASS,MAX_DOCUMENTS,validate_evidence

def analyze_evidence(evidence):
    if not isinstance(evidence,list) or len(evidence)>MAX_DOCUMENTS:
        raise ValueError("bounded evidence list required")
    evidence=[validate_evidence(item) for item in evidence]
    hashes=[item.sha256 for item in evidence]
    if len(hashes)!=len(set(hashes)):
        raise ValueError("duplicate evidence identity")
    hosts=Counter()
    total=0
    for item in evidence:
        from urllib.parse import urlsplit
        hosts[urlsplit(item.url).hostname]+=1
        total+=item.bytes
    return {
        "data_class":DATA_CLASS,
        "source_authenticity_verified":False,
        "document_count":len(evidence),
        "total_bytes":total,
        "source_hosts":dict(sorted(hosts.items())),
        "evidence_hashes":sorted(hashes),
        "claims_verified":0,
        "warning":"Counts and hashes are not evidence of factual accuracy.",
    }
