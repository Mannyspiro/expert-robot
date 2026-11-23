#!/usr/bin/env python3
"""Explicit review-only Second Brain handoff for verified research receipts.

Produces a bounded Markdown review candidate outside the vault. No automatic
Obsidian import, knowledge-graph promotion, truth assertion or model training.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python"))
from merlin.bounded_research_loop import ResearchSubloops


def preview(checkpoint: Path) -> dict:
    path=Path(checkpoint)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>524288:
        raise ValueError("regular bounded checkpoint required")
    raw=path.read_bytes()
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:
                raise ValueError("duplicate checkpoint key")
            result[key]=value
        return result
    loop=ResearchSubloops.restore(json.loads(raw,object_pairs_hook=unique))
    records=[]
    for receipt in loop.receipts:
        if receipt["status"]!="checked":
            continue
        records.append({
            "task_id":receipt["task_id"],
            "observation_sha256":receipt["observation_sha256"],
            "receipt_sha256":receipt["receipt_sha256"],
            "checker":receipt["verification"]["checker"],
            "status":"structurally_checked_not_scientific_truth",
        })
    return {"schema":"merlin-second-brain-research-review/1",
            "checkpoint_sha256":hashlib.sha256(raw).hexdigest(),
            "receipts":records,
            "review_required":True,"automatically_promoted":False,
            "scientific_truth_established":False,"production_qualified":False}


def markdown(report:dict)->str:
    lines=["# Merlin research evidence — review candidate","",
           "Status: **Unreviewed; do not treat as verified scientific truth**","",
           "Checkpoint SHA-256: `"+report["checkpoint_sha256"]+"`","",
           "No vault write or knowledge-graph promotion was performed.",""]
    for item in report["receipts"]:
        lines.extend(["## Task: `"+item["task_id"]+"`","",
                      "- Observation SHA-256: `"+item["observation_sha256"]+"`",
                      "- Receipt SHA-256: `"+item["receipt_sha256"]+"`",
                      "- Checker: `"+item["checker"]+"`",
                      "- Evidence status: structurally checked, not independent scientific proof",""])
    return "\n".join(lines)+"\n"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--checkpoint",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    report=preview(args.checkpoint)
    if args.output.is_symlink() or args.output.exists():
        raise ValueError("review candidate output must be new, nonsymlink file")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as out:
        out.write(markdown(report))
    print(json.dumps(report,sort_keys=True))


if __name__=="__main__":
    main()
