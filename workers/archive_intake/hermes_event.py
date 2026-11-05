#!/usr/bin/env python3
"""Build deterministic Hermes-compatible project intake events; no network dispatch."""
from __future__ import annotations
import argparse, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
from register_inventory import RegistryError, validate_manifest
from canonical_registry import get_github_receipt

def build_event(manifest: dict, project_id: str, commit_receipt: dict | None = None) -> dict:
    validate_manifest(manifest)
    if not isinstance(project_id, str) or not project_id.strip():
        raise RegistryError("project_id is required")
    source = None
    if commit_receipt is not None:
        required=("receipt_id","repository","canonical_sha","api_response_sha256","verification_source")
        if any(not commit_receipt.get(k) for k in required):
            raise RegistryError("GitHub provenance must be a complete fetched commit receipt")
        if not commit_receipt["receipt_id"].startswith("sha256:") or len(commit_receipt["canonical_sha"])!=40:
            raise RegistryError("invalid GitHub commit receipt identity")
        source={"repository_full_name":commit_receipt["repository"],"commit_sha":commit_receipt["canonical_sha"],
                "receipt_id":commit_receipt["receipt_id"],"signature_verified":bool(commit_receipt.get("signature_verified"))}
    manifest_sha = hashlib.sha256(
        json.dumps(manifest,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    identity = {"event_type":"merlin.project.intake.registered.v1","project_id":project_id,
      "intake_id":manifest["intake_id"],"manifest_sha256":manifest_sha,"source":source}
    event_id = "sha256:" + hashlib.sha256(
        json.dumps(identity,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    body = {**identity,"event_id":event_id,"created_at":manifest.get("finished_at"),
      "archive_sha256":manifest["archive"]["sha256"],"file_count":manifest["file_count"]}
    if source is None:
        body.pop("source")
    return body

def main():
    parser=argparse.ArgumentParser(description="Create a local Hermes event envelope; does not send it.")
    parser.add_argument("manifest",type=Path); parser.add_argument("--project-id",required=True)
    parser.add_argument("--github-receipt-id")
    parser.add_argument("--database",default="data/merlin.sqlite3")
    parser.add_argument("--outbox",type=Path,required=True)
    args=parser.parse_args()
    try:
        manifest=json.loads(args.manifest.read_text(encoding="utf-8"))
        receipt=get_github_receipt(args.database,args.github_receipt_id,args.project_id) if args.github_receipt_id else None
        event=build_event(manifest,args.project_id,receipt)
        args.outbox.parent.mkdir(parents=True,exist_ok=True)
        args.outbox.write_text(json.dumps(event,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print(json.dumps({"status":"queued_locally","event_id":event["event_id"],"outbox":str(args.outbox)},indent=2))
        return 0
    except (OSError,ValueError,RegistryError) as exc:
        print(json.dumps({"status":"rejected","error":str(exc)},indent=2),file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
