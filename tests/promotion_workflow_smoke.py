#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
collar=(ROOT/".github/workflows/collared-rsi-generation.yml").read_text()
qual=(ROOT/".github/workflows/rsi-candidate-qualification.yml").read_text()
pub=(ROOT/".github/workflows/auto-promote-qualified.yml").read_text()

assert 'branches: ["candidate/**"]' in collar
assert "Resolve trusted offline evaluation image" in collar
assert "docker build --pull --no-cache" in collar
assert "sha256:" in collar

assert 'workflows: ["Collared RSI Generation"]' in qual
assert "github.event.workflow_run.head_branch" in qual
assert "github.event.workflow_run.id" in qual
assert "needs.qualify.outputs.collar_evidence_run_id" in qual
assert "qualify:\n    if:" in qual
assert "qualify:\n    if:" in qual and "    concurrency:\n      group: expert-robot-avrea-rsi-promotion-v2" in qual
assert "decide:\n    needs: qualify\n    concurrency:\n      group: expert-robot-avrea-rsi-promotion-v2" in qual
assert "contents: read" in qual
assert "actions: read" in qual
assert "contents: write" not in qual
assert "jobs:\n  qualify:" in qual
assert "\n  decide:" in qual
assert "Revalidate candidate scope on fresh runner" in qual
assert "Revalidate blind candidate on fresh runner" in qual
assert "Download independent collar evidence" in qual
assert "cd candidate" in qual
assert "build/expert_robot_math_benchmark" in qual
assert "../candidate-evidence/math-benchmark-results-$variant.json" in qual
assert "../trusted/config/benchmarks/progression_math_v2.json" in qual
assert "g2_progression_v2_baseline.json" in qual
assert "compare_progression_to_reference.py" in qual
assert "Verify trusted hidden hard-v2 witnesses against candidate" in qual
assert "candidate/config/benchmarks/core_math_holdout.json" not in qual
assert "--require-eligible" in qual

assert 'workflows: ["RSI Candidate Qualification"]' in pub
assert "contents: write" in pub
assert "runs-on: ubuntu-latest" in pub
assert "actions/checkout" not in pub
assert "qualified/latest" in pub
assert "git/refs/heads/qualified/latest" in pub
assert "git/refs/heads/main" not in pub
assert "main moved after qualification" in pub
assert "candidate ref moved after qualification" in pub
print("promotion workflow boundary smoke: PASS")
