"""Use Merlin's clue comparison and plan revision on measured robustness results."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from merlin.scientific_loop import (
    ConditionalFact, Observation, Prediction, assess_clue_hypotheses,
    update_plan_from_observations,
)
from measure_mesh_interpolation import REPO


def review():
    evidence = REPO / "docs/evidence/mesh-robustness-results.json"
    raw = evidence.read_bytes()
    measured = json.loads(raw)
    prior_path = REPO / "config/merlin/plan-updates/20261118-mesh-three-row.json"
    prior_raw = prior_path.read_bytes()
    previous = json.loads(prior_raw)
    plan = json.loads((REPO / "config/merlin/production-master-plan.json").read_bytes())
    observations = []
    for perturbation in ("baseline", "narrow", "broad", "background", "noise"):
        cases = [case for case in measured["cases"] if case["perturbation"] == perturbation]
        observations.append(Observation(
            "mesh-robustness-"+perturbation, "How many of four cases beat both controls?",
            "Frozen deterministic synthetic perturbation grid",
            {"pass_count":sum(c["passed"] for c in cases)}, {"pass_count":"cases"},
            {"pass_count":0}, {"scope":"Four locations/tilts per perturbation",
             "uncertainty":"Deterministic count only; population uncertainty unmeasured."},
            (str(evidence.relative_to(REPO)),), datetime.now(timezone.utc).isoformat(),
            hashlib.sha256(raw).hexdigest()))
    inquiry = assess_clue_hypotheses(observations, {
        "all_perturbations_transfer":[Prediction("pass_count",4,0,"cases")],
        "universal_failure":[Prediction("pass_count",0,0,"cases")]},
        specialist_facts=[ConditionalFact(
            "gaussian-log-ratio", "Two positive Gaussian samples determine center with known width and background.",
            ("scripts/merlin/measure_mesh_three_rows.py",
             "docs/evidence/mesh-three-row-protocol.txt"),
            ("Known Gaussian width", "Accurately subtracted background", "Positive residuals"))],
        scope="20 noiseless-scoring synthetic cases, with one seeded pilot-noise pattern",
        next_test="Estimate or bound background with the same nine probes before inversion; freeze fallback criteria and independent perturbations.")
    actions = previous["next_actions"][:-1] + [inquiry["next_discriminating_test"]]
    update = update_plan_from_observations(
        {"plan_id":plan["plan_id"],"version":plan["version"]}, observations, next_actions=actions)
    update.update(prior_update=str(prior_path.relative_to(REPO)),
                  prior_update_sha256=hashlib.sha256(prior_raw).hexdigest(),
                  inquiry=inquiry, evidence=str(evidence.relative_to(REPO)),
                  preregistered_commit="c4aba183298ed28c869b93b5c81d348bf592b6ad",
                  decision="Background mismatch failed all four cases and selected uniform. Retain this inverse model as experimental.",
                  repair="Added explicit fallback for invalid inversion or out-of-domain warp; geometry errors retain failure status.",
                  limits=["Pilot noise only; scoring and mesh-vertex data are exact.",
                          "One deterministic noise pattern; field family and width prior are known.",
                          "Both universal explanations were contradicted. Applicability depends on perturbation type."])
    return update


if __name__ == "__main__":
    print(json.dumps(review(),indent=2,allow_nan=False))
