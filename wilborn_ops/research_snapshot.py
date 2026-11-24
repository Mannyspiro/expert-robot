"""Replayable research input. Integrity is not authenticity or real-world provenance."""
import base64
import hashlib
from .research_ingest import DATA_CLASS, ingest_public_text, MAX_BYTES
from .research_html import extract_html

SCHEMA = "research-input-snapshot-v2"

def snapshot(url, body):
    evidence = ingest_public_text(url, body)
    page = extract_html(evidence)
    return {"schema":SCHEMA,
            "url":url,"sha256":evidence.sha256,
            "body_base64":base64.b64encode(body).decode("ascii"),
            "extracted_sha256":hashlib.sha256(page.text.encode()).hexdigest(),
            "data_class":DATA_CLASS,"untrusted_content":True,
            "source_authenticity_verified":False,"claims_verified":0}

def replay(record):
    if not isinstance(record,dict) or record.get("schema") != SCHEMA:
        raise ValueError("current snapshot schema required; legacy inputs must be re-ingested")
    if not isinstance(record.get("url"),str):
        raise ValueError("source URL required")
    encoded=record.get("body_base64")
    if not isinstance(encoded,str) or len(encoded)>4*((MAX_BYTES+2)//3):
        raise ValueError("snapshot exceeds limit")
    body=base64.b64decode(encoded,validate=True)
    expected=snapshot(record["url"],body)
    if record.keys()!=expected.keys() or any(type(record[k]) is not type(v) or record[k]!=v for k,v in expected.items()):
        raise ValueError("snapshot mismatch")
    return extract_html(ingest_public_text(record["url"],body))
