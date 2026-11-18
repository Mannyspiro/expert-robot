"""Replay the seven known dot retrieval cases from hash-checked Merlin source."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def replay(root):
    prior = root / "docs/evidence/dot-cross-agent-retrieval-review.json"
    receipt = json.loads(prior.read_bytes())
    for path, sha in {**receipt["sources"], **receipt["input_documents_sha256"]}.items():
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != sha:
            raise ValueError(f"Historical source changed: {path}")
    with tempfile.TemporaryDirectory() as temp:
        start = time.perf_counter()
        cmd = [sys.executable, "scripts/measure_dot_review.py", "--registry", temp]
        import os
        measured = subprocess.run(cmd, cwd=root, env={**os.environ, "PYTHONPATH":str(root / "python")},
                                  check=True, capture_output=True, text=True)
        elapsed = time.perf_counter() - start
        fresh = json.loads(measured.stdout)
    if fresh != receipt:
        raise ValueError("Replay diverged from the original receipt")
    return {"schema":"merlin-rsi-daily-historical-cross-agent-replay/1",
            "recorded_commit": receipt["source_commit"],
            "receipt_path": str(prior.relative_to(root)),
            "receipt_sha256": hashlib.sha256(prior.read_bytes()).hexdigest(),
            "sources":receipt["sources"],
            "observation_ref":fresh["observations_ref"], "report_ref":fresh["report_ref"],
            "role_scope":"Two fixed policy adapters and a separate fixed locator evaluator, replayed from the prior study. Same public case IDs and labels.",
            "prior_reproduced": True, "wall_seconds":elapsed, "scores":fresh["scores"],
            "historical_recommendation":fresh["recommendation"],"fresh_holdout":False,
            "executed_model_calls":0,"external_requests":0,
            "daily_adoption_authority":False}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    print(json.dumps(replay(parser.parse_args().root.resolve()),indent=2))
