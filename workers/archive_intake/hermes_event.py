#!/usr/bin/env python3
"""Build deterministic Hermes-compatible project intake events; no network dispatch."""
from __future__ import annotations
import argparse, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
from register_inventory import RegistryError, validate_manifest

def build_event(manifest: dict, project_id: str, repository: str | None = None,
                commit_sha: str | None = None) -> dict:
    validate_manifest(manifest)
    if not project_id or not project_id.strip():
        raise RegistryError("project_id is required")
    if bool(repository) != bool(commit_sha):
        raise RegistryError("repository and commit_sha must be supplied together")
    if commit_sha and (len(commit_sha) != 40 or any(c not in "0123456789abcdef" for c in commit_sha.lower())):
        raise RegistryError("commit_sha must be a full 40-character hexadecimal SHA")
    body = {"event_type":"merlin.project.intake.registered.v1","project_id":project_id,
      "intake_id":manifest["intake_id"],"manifest_sha256":hashlib.sha256(
        json.dumps(manifest,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
      "created_at":datetime.now(timezone.utc).isoformat(),
      "archive_sha256":manifest["archive"]["sha256"],"file_count":manifest["file_count"]}
    if repository:
        body["source"]={"repository_full_name":repository,"commit_sha":commit_sha.lower()}
    stable = json.dumps(body,sort_keys=True,separators=(",",":")).encode()
    body["event_id"]="sha256:"+hashlib.sha256(stable).hexdigest()
    return body

def main():
    parser=argparse.ArgumentParser(description="Create a local Hermes event envelope; does not send it.")
    parser.add_argument("manifest",type=Path); parser.add_argument("--project-id",required=True)
    parser.add_argument("--repository"); parser.add_argument("--commit-sha")
    parser.add_argument("--outbox",type=Path,required=True)
    args=parser.parse_args()
    try:
        manifest=json.loads(args.manifest.read_text(encoding="utf-8"))
        event=build_event(manifest,args.project_id,args.repository,args.commit_sha)
        args.outbox.parent.mkdir(parents=True,exist_ok=True)
        args.outbox.write_text(json.dumps(event,indent=2,sort_keys=True)+"\\n",encoding="utf-8")
        print(json.dumps({"status":"queued_locally","event_id":event["event_id"],"outbox":str(args.outbox)},indent=2))
        return 0
    except (OSError,ValueError,RegistryError) as exc:
        print(json.dumps({"status":"rejected","error":str(exc)},indent=2),file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
