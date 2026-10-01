#!/usr/bin/env python3
"""Reject explicit evaluation-identity leakage in an automatic-promotion candidate diff."""

import argparse
import json
import subprocess
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument("repo",type=Path)
    p.add_argument("--base-sha",required=True)
    p.add_argument("--candidate-sha",required=True)
    p.add_argument("--policy",type=Path,default=Path("config/blind_evaluation_policy.json"))
    p.add_argument("--output",type=Path)
    args=p.parse_args()

    policy=json.loads(args.policy.read_text(encoding="utf-8"))
    hidden=policy["hidden_identifiers"]
    diff=subprocess.check_output(
        ["git","-C",str(args.repo),"diff","--unified=0",f"{args.base_sha}...{args.candidate_sha}","--"],
        text=True,errors="replace")
    added="\n".join(line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
    leaks=[token for token in hidden if token in added]
    result={"schema_version":1,"blind_identity_clean":not leaks,"leaked_identifiers":leaks}
    rendered=json.dumps(result,indent=2)+"\n"
    if args.output:
        args.output.write_text(rendered,encoding="utf-8")
    print(rendered,end="")
    if leaks:
        raise SystemExit(2)

if __name__=="__main__":
    main()
