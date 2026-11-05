#!/usr/bin/env python3
"""Rights-aware, compressed, quota-bounded source intake for Merlin."""
from __future__ import annotations
import argparse, gzip, hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from merlin_storage_guard import check as storage_check

ALLOWED_FULLTEXT={"public_domain_verified","open_license_verified"}
METADATA_ONLY={"metadata_only","preview_only","restricted","unknown"}
SAFE_ID=re.compile(r"^[a-z0-9][a-z0-9._:-]{2,127}$")
MAX_SOURCE_BYTES=10*1024*1024


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
    if content is not None and len(content)>MAX_SOURCE_BYTES:
        raise IntakeError("source exceeds 10 MiB per-source intake cap")
    if content is not None and not document.get("license_uri") and rights=="open_license_verified":
        raise IntakeError("open-license full text requires an explicit license_uri")
    license_id=document.get("license_id")
    use_context=document.get("use_context","unknown")
    if content is not None and license_id=="CC-BY-NC-SA-4.0" and use_context!="noncommercial":
        raise IntakeError("CC BY-NC-SA full-text intake requires explicit noncommercial use")
    metadata_bytes=json.dumps(document,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return {
      "schema_version":1,"record_type":"merlin.science.source-intake",
      "source_id":sid,"title":document["title"],"creator":document["creator"],
      "repository":document["repository"],"canonical_url":document["canonical_url"],
      "rights_status":rights,"license_uri":document.get("license_uri"),
      "license_id":license_id,"use_context":use_context,
      "metadata_sha256":sha(metadata_bytes),"content_sha256":sha(content) if content is not None else None,
      "content_bytes":len(content) if content is not None else 0,"content_ingested":content is not None,
      "provenance":document["provenance"],"staged_at":datetime.now(timezone.utc).isoformat(),
      "promotion_state":"pending_human_review","claim_extraction_state":"not_run",
      "canonical_research_graph_write":False,"authority_delta":0
    }


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--record",type=Path,required=True)
    p.add_argument("--content",type=Path)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--staging-root",type=Path,default=Path("state/merlin-ingestion-staging"))
    p.add_argument("--max-source-bytes",type=int,default=MAX_SOURCE_BYTES)
    p.add_argument("--max-staging-bytes",type=int,default=268435456)
    p.add_argument("--max-staged-files",type=int,default=5000)
    p.add_argument("--free-disk-reserve-bytes",type=int,default=1073741824)
    a=p.parse_args()
    try:
        document=json.loads(a.record.read_text(encoding="utf-8"))
        content=a.content.read_bytes() if a.content else None
        if content is not None and len(content)>a.max_source_bytes:
            raise IntakeError("source exceeds configured per-source byte cap")
        result=stage(document,content)
        root=a.staging_root.resolve(); out=a.out.resolve()
        if not out.is_relative_to(root):
            raise IntakeError("output path must be inside the bounded staging root")
        root.mkdir(parents=True,exist_ok=True)
        content_path=None; compressed=b""; content_is_new=False
        if content is not None:
            compressed=gzip.compress(content,compresslevel=6,mtime=0)
            content_path=root/"content"/(result["content_sha256"]+".gz")
            content_is_new=not content_path.exists()
            result["content_storage"]={"path":str(content_path.relative_to(root)),"compression":"gzip","compressed_bytes":len(compressed),"deduplicated":not content_is_new}
        else:
            result["content_storage"]=None
        record_bytes=json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True).encode()+b"\n"
        if out.exists():
            existing=json.loads(out.read_text(encoding="utf-8"))
            if existing.get("metadata_sha256")==result["metadata_sha256"] and existing.get("content_sha256")==result["content_sha256"]:
                print(json.dumps({"ok":True,"source_id":result["source_id"],"deduplicated":True,"promotion_state":existing.get("promotion_state")},sort_keys=True))
                return 0
            raise IntakeError("output record already exists with different content; refusing overwrite")
        for prior in root.glob("*.json"):
            try: old=json.loads(prior.read_text(encoding="utf-8"))
            except Exception: continue
            if old.get("canonical_url")==result["canonical_url"]:
                raise IntakeError("canonical URL already staged; reuse its existing source record")
        additional_bytes=len(record_bytes)+(len(compressed) if content_is_new else 0)
        additional_files=1+(1 if content_is_new else 0)
        guard=storage_check(root,a.max_staging_bytes,a.max_staged_files,a.free_disk_reserve_bytes,additional_bytes,additional_files)
        if not guard["ok"]: raise IntakeError("storage preflight blocked intake: "+json.dumps(guard["errors"]))
        if content_is_new and content_path is not None:
            content_path.parent.mkdir(parents=True,exist_ok=True)
            content_path.write_bytes(compressed)
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(record_bytes)
        print(json.dumps({"ok":True,"source_id":result["source_id"],"content_ingested":result["content_ingested"],"content_compressed_bytes":len(compressed),"storage_preflight":guard,"promotion_state":result["promotion_state"]},sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"ok":False,"error":str(exc),"error_type":type(exc).__name__},sort_keys=True),file=sys.stderr)
        return 2


if __name__=="__main__": raise SystemExit(main())
