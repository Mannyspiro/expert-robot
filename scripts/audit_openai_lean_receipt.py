#!/usr/bin/env python3
"""Fail-closed replay receipt; NOT comparator, semantic fidelity or CACE qualification."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ALLOWED={"propext","Classical.choice","Quot.sound"}
UPSTREAM="fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb"
MATHLIB="d13f23b723b8a846827a245b89c10fc7d3f11612"
TOOLCHAIN="leanprover/lean4:v4.34.1"
NAME=re.compile(r"[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*\Z")

def audit_transcript(stdout,theorem):
    if not NAME.fullmatch(theorem or ""):raise ValueError("bad theorem name")
    if any(s in stdout.lower() for s in ("error:","sorryax","unsolved goals")):
        raise ValueError("upstream Lean reported an error")
    if not re.search(r"(?m)^"+re.escape(theorem)+r"\s*:",stdout):
        raise ValueError("expected Lean #check output missing")
    label=re.escape("'"+theorem+"'")
    entries=re.findall(label+r" depends on axioms: \[([^\]]*)\]",stdout)
    none=re.findall(label+r" does not depend on any axioms",stdout)
    if len(entries)+len(none)!=1:raise ValueError("missing/duplicate axiom report")
    axioms=[x.strip() for x in entries[0].split(",") if x.strip()] if entries else []
    if len(axioms)!=len(set(axioms)) or not set(axioms).issubset(ALLOWED):
        raise ValueError("unapproved axiom(s)")
    return sorted(axioms)

def make_receipt(project,module,theorem,stdout,kernel_outcome,run_id,workflow_sha):
    if kernel_outcome!="success":raise ValueError("independent kernel checker did not succeed")
    if not re.fullmatch(r"[0-9]{1,20}",run_id or ""):raise ValueError("bad run ID")
    if not re.fullmatch(r"[0-9a-f]{40}",workflow_sha or ""):raise ValueError("bad workflow SHA")
    if not NAME.fullmatch(module or ""):raise ValueError("bad module")
    if (project/"lean-toolchain").read_text().strip()!=TOOLCHAIN:
        raise ValueError("toolchain pin mismatch")
    manifest=(project/"lake-manifest.json").read_bytes()
    if MATHLIB.encode() not in manifest:raise ValueError("mathlib pin mismatch")
    source=project/(module.replace(".","/")+".lean")
    if not source.is_file():raise ValueError("Lean source missing")
    axioms=audit_transcript(stdout,theorem)
    return {"schema_version":1,"experiment":"openai-upstream-kernel-receipt-v1",
      "upstream_repo":"openai/math","upstream_sha":UPSTREAM,
      "workflow_sha":workflow_sha,"github_run_id":run_id,
      "source_module":module,"declaration":theorem,
      "module_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
      "manifest_sha256":hashlib.sha256(manifest).hexdigest(),
      "transcript_sha256":hashlib.sha256(stdout.encode()).hexdigest(),
      "toolchain":TOOLCHAIN,"mathlib_sha":MATHLIB,
      "axiom_dependencies":axioms,"allowed_axioms":sorted(ALLOWED),
      "kernel_step_reported_success":True,
      "upstream_commit_checked_by_preceding_ci_step":True,
      "state":"kernel_step_passed_axioms_screened",
      "comparator_challenge_passed":False,
      "manuscript_fidelity_reviewed":False,
      "cace_integration_qualified":False,
      "promotion_authorized":False}

def main():
    p=argparse.ArgumentParser()
    for k in ("module","theorem","kernel-step-outcome","github-run-id","github-sha"):
        p.add_argument("--"+k,required=True)
    p.add_argument("--upstream-lean",type=Path,required=True)
    p.add_argument("--transcript",type=Path,required=True)
    p.add_argument("-o",type=Path,required=True)
    a=p.parse_args()
    out=make_receipt(a.upstream_lean,a.module,a.theorem,a.transcript.read_text(),
                     a.kernel_step_outcome,a.github_run_id,a.github_sha)
    a.o.write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps({"declaration":out["declaration"],
       "axiom_dependencies":out["axiom_dependencies"],"state":out["state"],
       "comparator_challenge_passed":False}))

if __name__=="__main__":main()
