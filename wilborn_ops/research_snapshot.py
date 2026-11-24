"""Offline snapshot serialization and replay; no business storage access."""
import base64
import hashlib
from .research_ingest import ingest_public_text, MAX_BYTES
from .research_html import extract_html

def snapshot(url, body):
    evidence = ingest_public_text(url, body)
    page = extract_html(evidence)
    return {"schema":"public-research-snapshot-v1",
            "url":url,"sha256":evidence.sha256,
            "body_base64":base64.b64encode(body).decode("ascii"),
            "extracted_sha256":hashlib.sha256(page.text.encode()).hexdigest(),
            "data_class":"public_research","untrusted_content":True,
            "claims_verified":0}

def replay(record):
    if not isinstance(record,dict):
        raise ValueError("snapshot required")
    encoded=record.get("body_base64")
    if not isinstance(encoded,str) or len(encoded)>4*((MAX_BYTES+2)//3):
        raise ValueError("snapshot exceeds limit")
    body=base64.b64decode(encoded,validate=True)
    expected=snapshot(record["url"],body)
    if record!=expected:
        raise ValueError("snapshot mismatch")
    return extract_html(ingest_public_text(record["url"],body))
