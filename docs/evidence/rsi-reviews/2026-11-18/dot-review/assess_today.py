"""Score the independent frozen daily checks using Merlin's scientific loop."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys


def assess(root, results_dir):
    sys.path.insert(0, str(root / "python"))
    from merlin.scientific_loop import Observation, Prediction, compare_observation
    result_path = results_dir / "daily-holdout-result.json"
    protocol_path = results_dir / "daily-holdout.json"
    raw = result_path.read_bytes()
    result = json.loads(raw)
    protocol_hash = sha256(protocol_path.read_bytes()).hexdigest()
    if protocol_hash != result["protocol_sha256"]:
        raise ValueError("observations refer to a different protocol")
    expected_ids = [c["id"] for c in json.loads(protocol_path.read_bytes())["sequence"]]
    rows = result["cases"]
    if [r["id"] for r in rows] != expected_ids or len(set(expected_ids)) != len(expected_ids):
        raise ValueError("incomplete held-out observations")
    successes = sum(row["passed"] is True for row in rows)
    if successes != result["summary"]["passed"]:
        raise ValueError("case count mismatch")
    obs = Observation("same-client-revocation-and-catalogue-refresh",
        "Did each baseline response match the preregistered action and historical pin?",
        "Independent operator of a synthetic in-process HTTP ASGI fixture",
        {"exact":successes}, {"exact":"cases"}, {"exact":0},
        {"uncertainty":"Exact count in the frozen sample. Generalization unmeasured.",
         "measurement_scope":result["limits"]},
        (result_path.name, protocol_hash), datetime.fromtimestamp(result_path.stat().st_mtime,timezone.utc).isoformat(),
        sha256(raw).hexdigest())
    return {"assessment":compare_observation(obs,[Prediction("exact",len(expected_ids),0,"cases")]),
            "protocol_sha256":protocol_hash,"results_sha256":obs.artifact_sha256,
            "merlin_scientific_loop_sha256":sha256((root/"python/merlin/scientific_loop.py").read_bytes()).hexdigest(),
            "baseline_summary":result["summary"],"available_gain_cases":len(rows)-successes,
            "decision":"retain_baseline" if successes == len(rows) else "investigate_baseline_failures",
            "candidate_comparison":"No new coder outputs for this held-out task; no comparative fresh trial or measured regression rate.",
            "qualification":False,"promotion_authority":False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("merlin_root",type=Path)
    parser.add_argument("results_dir",type=Path)
    args=parser.parse_args()
    print(json.dumps(assess(args.merlin_root.resolve(),args.results_dir.resolve()),indent=2))
