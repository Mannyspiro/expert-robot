"""Assemble the independent evaluator's exact emitted labels into dot's matrix."""
import json
from pathlib import Path

folder = Path(__file__).resolve().parent / "eval"
labels = {"train": {}, "holdout": {}}
observed = {}
for arm, filename in (("baseline", "baseline"), ("coder_a", "candidate"), ("coder_b", "alternative")):
    result = json.loads((folder / (filename + ".json")).read_text())
    observed[arm] = {}
    for row in result["results"]:
        case = row["id"]
        split = "train" if row["partition"] == "development" else "holdout"
        previous = labels[split].setdefault(case, row["expected_label"])
        if previous != row["expected_label"]:
            raise ValueError(f"mismatched protocol on {case}")
        observed[arm][case] = row["actual_label"]
    if set(observed[arm]) != labels["train"].keys() | labels["holdout"].keys():
        raise ValueError(f"missing or extra case in {arm}")
print(json.dumps({**labels, "observed": observed}, indent=2))
