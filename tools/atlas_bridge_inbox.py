#!/usr/bin/env python3
"""Atlas v1.6 read-only inbox adapter. NEVER grants authority or accepts a proof."""
import argparse, hashlib, json, re
from pathlib import Path
from urllib.parse import urlsplit

LIMIT = 32768
ALLOWED = {
    "EXPERT_ROBOT": "bounded_research_episode",
    "SGK": "lean_theorem_proof",
    "CACE": "mesh_residual_certificate",
}
FIELDS = {
    "schema", "project", "task_type", "claim_id", "claim_sha256",
    "claim_text", "assumptions", "source_url", "privileges",
    "network", "status", "qualification", "payload_sha256"
}

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")

def inspect_task(source, project):
    file = Path(source)
    if file.stat().st_size > LIMIT:
        raise ValueError("oversized work package")
    obj = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or set(obj) != FIELDS:
        raise ValueError("unexpected work package shape")
    expected = ALLOWED[project]
    if obj["schema"] != "atlas.bridge.v1" or obj["project"] != project or obj["task_type"] != expected:
        raise ValueError("wrong schema or project")
    if obj["privileges"] != "NONE" or obj["network"] != "NONE" or obj["status"] != "PROPOSED_ONLY":
        raise ValueError("untrusted package attempts to claim authority")
    if obj["qualification"] != "MUST_REVERIFY_AT_PINNED_TARGET":
        raise ValueError("qualification gate missing")
    if not re.fullmatch(r"DC[0-9]{6}", obj["claim_id"]):
        raise ValueError("invalid claim id")
    if not re.fullmatch(r"[a-f0-9]{64}", obj["claim_sha256"]):
        raise ValueError("invalid claim hash")
    if urlsplit(obj["source_url"]).scheme != "https" or not urlsplit(obj["source_url"]).hostname:
        raise ValueError("missing https provenance")
    check = {k: v for k, v in obj.items() if k != "payload_sha256"}
    if hashlib.sha256(canonical(check)).hexdigest() != obj["payload_sha256"]:
        raise ValueError("payload checksum mismatch")
    return {
        "claim_id": obj["claim_id"], "project": project,
        "claim_sha256": obj["claim_sha256"],
        "review_state": "UNTRUSTED_STAGED",
        "proof_accepted": False, "authority_change": False
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("work_package")
    p.add_argument("--project", required=True, choices=ALLOWED)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    result = inspect_task(args.work_package, args.project)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("x", encoding="utf-8") as f:
        f.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))

if __name__ == "__main__":
    main()
