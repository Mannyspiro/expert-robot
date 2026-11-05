#!/usr/bin/env python3
"""Fetch a commit from GitHub and persist a content-addressed provenance receipt."""
from __future__ import annotations
import argparse, hashlib, json, os, re, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from canonical_registry import connect, initialize

def fetch_commit(repository, requested_sha, token=None):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repository): raise ValueError("repository must be owner/name")
    if not re.fullmatch(r"[0-9a-fA-F]{40}",requested_sha): raise ValueError("full 40-character commit SHA required")
    url="https://api.github.com/repos/"+repository+"/commits/"+requested_sha.lower()
    headers={"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"Merlin-Provenance-Adapter"}
    if token: headers["Authorization"]="Bearer "+token
    req=urllib.request.Request(url,headers=headers)
    with urllib.request.urlopen(req,timeout=20) as response:
        if response.status!=200: raise RuntimeError("GitHub API returned non-200 response")
        raw=response.read(4*1024*1024+1)
    if len(raw)>4*1024*1024: raise RuntimeError("GitHub response exceeds 4 MiB")
    data=json.loads(raw)
    canonical=data.get("sha","")
    if canonical.lower()!=requested_sha.lower(): raise RuntimeError("GitHub returned a different commit SHA")
    commit=data.get("commit",{}); verification=commit.get("verification") or {}
    return {"receipt_version":"1.0","repository":repository,"requested_sha":requested_sha.lower(),
      "canonical_sha":canonical.lower(),"commit_url":data.get("html_url",""),
      "api_response_sha256":hashlib.sha256(raw).hexdigest(),
      "signature_verified":bool(verification.get("verified")),
      "signature_reason":verification.get("reason"),"retrieved_at":datetime.now(timezone.utc).isoformat(),
      "author_date":commit.get("author",{}).get("date"),"committer_date":commit.get("committer",{}).get("date"),
      "verification_source":"github_rest_commit_endpoint"}

def store_receipt(database, receipt, project_id=None):
    rid="sha256:"+hashlib.sha256(json.dumps(receipt,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    with connect(database) as db:
        if project_id and not db.execute("SELECT 1 FROM projects WHERE project_id=?",(project_id,)).fetchone():
            raise ValueError("unknown project_id")
        db.execute("""INSERT OR IGNORE INTO github_commit_receipts
          (receipt_id,project_id,repository,requested_sha,canonical_sha,commit_url,api_response_sha256,
           signature_verified,signature_reason,retrieved_at)
          VALUES(?,?,?,?,?,?,?,?,?,?)""",(rid,project_id,receipt["repository"],receipt["requested_sha"],
          receipt["canonical_sha"],receipt["commit_url"],receipt["api_response_sha256"],
          int(receipt["signature_verified"]),receipt["signature_reason"],receipt["retrieved_at"]))
    return {**receipt,"receipt_id":rid}

def main():
    p=argparse.ArgumentParser(); p.add_argument("repository"); p.add_argument("commit_sha")
    p.add_argument("--database",default="data/merlin.sqlite3"); p.add_argument("--project-id"); p.add_argument("--require-signed",action="store_true")
    a=p.parse_args(); initialize(a.database)
    receipt=fetch_commit(a.repository,a.commit_sha,os.environ.get("GITHUB_TOKEN"))
    if a.require_signed and not receipt["signature_verified"]: raise SystemExit("GitHub did not report a verified commit signature")
    print(json.dumps(store_receipt(a.database,receipt,a.project_id),indent=2))
if __name__=="__main__": main()
