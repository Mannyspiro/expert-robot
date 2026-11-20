"""Verify arm-input equality and distinguish topology rejection from abstention."""
import hashlib
import json
from pathlib import Path

here=Path(__file__).resolve().parent
arms={name:json.loads((here/(name+".json")).read_bytes()) for name in ("baseline","arm_a","arm_b")}
base=arms["baseline"]
expected_cases=[(r["id"],r["source_sha256"],r["image_sha256"],r["expected_label"],r["partition"]) for r in base["results"]]
out={}
for name,report in arms.items():
    assert report["protocol_sha256"]==base["protocol_sha256"]
    assert [(r["id"],r["source_sha256"],r["image_sha256"],r["expected_label"],r["partition"]) for r in report["results"]]==expected_cases
    hold=[r for r in report["results"] if r["partition"]=="heldout"]
    out[name]=dict(source_sha256=report["source_sha256"],report_sha256=hashlib.sha256((here/(name+".json")).read_bytes()).hexdigest(),
            flags=report["flags"],development_passed=report["passed_development"],heldout_passed=report["passed_heldout"],
            accepted_positives=sum(r["actual_label"]==r["expected_label"]=="accept" for r in hold),
            correctly_withheld=sum(r["actual_label"]==r["expected_label"]=="withhold" for r in hold),
            false_acceptances=sum(r["actual_label"]=="accept" and r["expected_label"]=="withhold" for r in hold),
            positive_regressions=[r["id"] for b,r in zip(base["results"],report["results"]) if b["passed"] and not r["passed"]],
            repaired_baseline_errors=[r["id"] for b,r in zip(base["results"],report["results"]) if not b["passed"] and r["passed"]],
            ready_for_further_trials=all(r["passed"] for r in report["results"]),
            diagnostics={r["id"]:r["diagnostics"] for r in hold},wall_seconds=report["wall_seconds"])
print(json.dumps(dict(protocol_sha256=base["protocol_sha256"],same_input_bytes=True,arms=out,
    scope="Single novel geometry and predeclared mutations. Synthetic raster fixed at one renderer and resolution. All-pass human reports intentionally wrong for H2 and H3. End-to-end wall times descriptive. Withholding indicates a mismatch or uncertainty; it does not prove electrical topology."),indent=2))
