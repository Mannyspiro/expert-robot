"""Bounded public research ingestion with deterministic evidence identity.

No network access here. The caller must supply already-fetched public content and
an approved source manifest. Never imports client data or business records.
"""
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urlsplit

MAX_BYTES=256_000
MAX_DOCUMENTS=50
APPROVED_HOSTS=frozenset({
    "www.census.gov", "data.census.gov", "www.sba.gov",
    "www.irs.gov", "www.nist.gov", "www.arxiv.org", "arxiv.org",
})

@dataclass(frozen=True)
class Evidence:
    url: str
    sha256: str
    bytes: int
    text: str
    data_class: str = "public_research"
    verification: str = "unverified_source_content"

def validate_url(url):
    if not isinstance(url,str) or len(url)>2048:
        raise ValueError("invalid URL")
    parsed=urlsplit(url)
    if (parsed.scheme!="https" or parsed.hostname not in APPROVED_HOSTS or
        parsed.username is not None or parsed.password is not None or
        parsed.port not in (None,443) or parsed.fragment):
        raise PermissionError("unapproved source URL")
    return url

def ingest_public_text(url, content):
    validate_url(url)
    if not isinstance(content,bytes) or not content or len(content)>MAX_BYTES:
        raise ValueError("invalid document bytes")
    text=content.decode("utf-8",errors="strict")
    if "\x00" in text:
        raise ValueError("binary content prohibited")
    return Evidence(url,sha256(content).hexdigest(),len(content),text)

def ingest_batch(items):
    if not isinstance(items,list) or len(items)>MAX_DOCUMENTS:
        raise ValueError("invalid batch size")
    seen=set()
    results=[]
    for url,content in items:
        evidence=ingest_public_text(url,content)
        if evidence.sha256 not in seen:
            seen.add(evidence.sha256)
            results.append(evidence)
    return results
