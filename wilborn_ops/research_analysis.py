"""Deterministic evidence coverage analysis; not semantic truth verification."""
from collections import Counter
from .research_ingest import Evidence

def analyze_evidence(evidence):
    if not isinstance(evidence,list) or any(not isinstance(item,Evidence) for item in evidence):
        raise TypeError("typed public evidence required")
    hashes=[item.sha256 for item in evidence]
    if len(hashes)!=len(set(hashes)):
        raise ValueError("duplicate evidence identity")
    if any(item.data_class!="public_research" for item in evidence):
        raise PermissionError("non-public research prohibited")
    hosts=Counter()
    total=0
    for item in evidence:
        from urllib.parse import urlsplit
        hosts[urlsplit(item.url).hostname]+=1
        total+=item.bytes
    return {
        "data_class":"public_research",
        "document_count":len(evidence),
        "total_bytes":total,
        "source_hosts":dict(sorted(hosts.items())),
        "evidence_hashes":sorted(hashes),
        "claims_verified":0,
        "warning":"Counts and hashes are not evidence of factual accuracy.",
    }
