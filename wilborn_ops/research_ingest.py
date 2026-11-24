"""Bounded public research ingestion with deterministic evidence identity.

No network access here. The caller must supply already-fetched public content and
an approved source manifest. Never imports client data or business records.
"""
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urlsplit

MAX_BYTES=256_000
MAX_DOCUMENTS=50
DATA_CLASS="unverified_research_input"
VERIFICATION="unverified_source_content"
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
    data_class: str = DATA_CLASS
    verification: str = VERIFICATION
    source_authenticity_verified: bool = False

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

def validate_evidence(evidence):
    """Validate byte consistency and classification, never source authenticity."""
    if type(evidence) is not Evidence:
        raise TypeError("typed research input required")
    if (evidence.data_class != DATA_CLASS or evidence.verification != VERIFICATION
            or evidence.source_authenticity_verified is not False):
        raise PermissionError("unverified research classification required")
    if not isinstance(evidence.text,str) or type(evidence.bytes) is not int:
        raise ValueError("invalid evidence fields")
    canonical=ingest_public_text(evidence.url,evidence.text.encode("utf-8"))
    if evidence.sha256 != canonical.sha256 or evidence.bytes != canonical.bytes:
        raise ValueError("evidence content identity mismatch")
    return canonical

def ingest_batch(items):
    if not isinstance(items,list) or len(items)>MAX_DOCUMENTS:
        raise ValueError("invalid batch size")
    seen={}
    results=[]
    for url,content in items:
        evidence=ingest_public_text(url,content)
        previous=seen.get(evidence.sha256)
        if previous is not None and previous != evidence.url:
            raise ValueError("conflicting source URLs for identical bytes")
        if previous is None:
            seen[evidence.sha256]=evidence.url
            results.append(evidence)
    return results
