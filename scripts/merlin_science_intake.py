#!/usr/bin/env python3
"""Rights-aware source intake for Merlin. Stages candidates; never promotes claims."""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path

ALLOWED_FULLTEXT={"public_domain_verified","open_license_verified"}
METADATA_ONLY={"metadata_only","preview_only","restricted","unknown"}
SAFE_ID=re.compile(r"^[a-z0-9][a-z0-9._:-]{2,127}$")

class IntakeError(ValueError): pass

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def stage(document: dict, content: bytes | None=None) -> dict:
    if not isinstance(document,dict): raise IntakeError("source record must be a JSON object")
    required=("source_id","title","creator","repository","canonical_url","rights_status","provenance")
    missing=[x for x in required if x not in document]
    if missing: raise IntakeError(f"missing required fields: {missing}")
    sid=document["source_id"]
    if not isinstance(sid,str) or not SAFE_ID.fullmatch(sid): raise IntakeError("source_id must be a safe stable identifier")
    rights=document["rights_status"]
    if rights not in ALLOWED_FULLTEXT|METADATA_ONLY: raise IntakeError("unsupported rights_status")
    if content is not None and rights not in ALLOWED_FULLTEXT:
        raise IntakeError("full text is blocked unless item-level public-domain or open-license status is verified")
    if content is not None and not document.get("license_uri") and rights=="open_license_verified":
        raise IntakeError("open-license full text requires an explicit license_uri")
    metadata_bytes=json.dumps(document,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    out={
      "schema_version":1,
      "record_type":"merlin.science.source-intake",
      "source_id":sid,
      "title":document["title"],
      "creator":document["creator"],
      "repository":document["repository"],
      "canonical_url":document["canonical_url"],
      "rights_status":rights,
      "license_uri":document.get("license_uri"),
      "metadata_sha256":sha(metadata_bytes),
      "content_sha256":sha(content) if content is not None else None,
      "content_bytes":len(content) if content is not None else 0,
      "content_ingested":content is not None,
      "provenance":document["provenance"],
      "staged_at":datetime.now(timezone.utc).isoformat(),
      "promotion_state":"pending_human_review",
      "claim_extraction_state":"not_run",
      "canonical_research_graph_write":False,
      "authority_delta":0
    }
    return out

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--record",type=Path,required=True)
    p.add_argument("--content",type=Path)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    try:
        document=json.loads(a.record.read_text(encoding="utf-8"))
        content=a.content.read_bytes() if a.content else None
        result=stage(document,content)
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print(json.dumps({"ok":True,"source_id":result["source_id"],"content_ingested":result["content_ingested"],"promotion_state":result["promotion_state"]},sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"ok":False,"error":str(exc),"error_type":type(exc).__name__},sort_keys=True),file=sys.stderr)
        return 2

if __name__=="__main__": raise SystemExit(main())
