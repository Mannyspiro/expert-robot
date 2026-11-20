"""Repeat the lightweight RSI parent-selection experiment using a fresh Merlin registry."""
import json
from pathlib import Path
from runpy import run_path
from tempfile import TemporaryDirectory

from dot_ai_os.cross_agent_review import CrossAgentReviewer
from dot_ai_os.training_parents import choose_parents, plan_training_parents
from merlin.project_registry import MerlinRegistry


def measure():
    root = Path(__file__).resolve().parents[2]
    run = run_path(str(root / "scripts/measure_dot_review.py"))["run"]
    with TemporaryDirectory() as directory:
        trial = run(directory)
        ref = trial["protocol_ref"]
        reviewer = CrossAgentReviewer(MerlinRegistry(directory), project_id=ref["project_id"])
        plan = plan_training_parents(reviewer, ref)
    parents = [entry["arm"] for entry in plan["parents"]]
    training = {key: case for key, case in trial["cases"].items() if case["split"] == "train"}
    rows = {arm: {key for key, case in training.items() if case["observed"][arm] == case["expected"]}
            for arm in ("baseline", "coder_a", "coder_b")}
    aggregate = sorted(rows, key=lambda arm: -len(rows[arm]))[:2]
    # Independent small control: the two highest individual scores duplicate two cases.
    control = {"baseline": {"a", "b"}, "coder_a": {"a", "b"}, "coder_b": {"c"}}
    control_selection = choose_parents(control)
    return {
        "schema": "merlin-training-parent-measurement/1",
        "upstream": "gepa-ai/gepa@8b0ce6cd99a234f6b74daf37558a2ac0ce18f975",
        "upstream_git_blob": "05567c8b3f69209acebfb1bb460fc4b445006851",
        "dot_training": {"cases": len(training), "aggregate_parents": aggregate,
                         "aggregate_covered": len(set.union(*(rows[a] for a in aggregate))),
                         "selected_parents": parents, "selected_covered": plan["train_cases_covered"]},
        "complementary_control": {
            "aggregate_covered": len(control["baseline"] | control["coder_a"]),
            "selected_parents": control_selection,
            "selected_covered": len(set.union(*(control[a] for a in control_selection)))},
        "new_provider_calls": 0, "promotion_authority": False,
        "scope": "Training coverage and requested parent slots for fixed software adapters."}


if __name__ == "__main__":
    print(json.dumps(measure(), indent=2))
