#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
qual=(ROOT/".github/workflows/rsi-candidate-qualification.yml").read_text()
pub=(ROOT/".github/workflows/auto-promote-qualified.yml").read_text()

assert "contents: read" in qual
assert "actions: read" in qual
assert "contents: write" not in qual
assert "jobs:\n  qualify:" in qual
assert "\n  decide:" in qual
assert "Revalidate candidate scope on fresh runner" in qual
assert "Revalidate blind candidate on fresh runner" in qual
assert "Download independent collar evidence" in qual
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
