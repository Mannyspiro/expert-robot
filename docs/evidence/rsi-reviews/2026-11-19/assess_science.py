"""Compare the independent controlled-drafting observations with frozen predictions."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

from merlin.scientific_loop import Observation, Prediction, compare_observation

path = Path(sys.argv[1])
data = path.read_bytes()
matrix = json.loads(data)
measured = {
    "foreign_format_rejected_before_other_decoder": sum(
        matrix["observed"][arm]["B4"] == matrix["holdout"]["B4"]
        for arm in ("coder_a", "coder_b")
    ),
    "branched_drawing_correct": sum(
        matrix["observed"][arm][case] == matrix["holdout"][case]
        for arm in matrix["observed"] for case in ("B0", "B1", "B2")
    ),
    "wrong_verdict_detected": sum(
        matrix["observed"][arm]["B3"] == matrix["holdout"]["B3"]
        for arm in matrix["observed"]
    ),
}
expected = {
    "foreign_format_rejected_before_other_decoder": 2,
    "branched_drawing_correct": 9,
    "wrong_verdict_detected": 3,
}
units = {key: "fixture observations" for key in expected}
observation = Observation(
    "drafting-decoder-and-review-trust",
    "Does decoder restriction preserve review behavior and detect a mistaken all-pass verdict?",
    "Independent synthetic branch fixture on isolated normal interface",
    measured,
    units,
    dict.fromkeys(expected, 0.0),
    {"scope": "Exact observed counts on a finite synthetic test set. No uncertainty estimate for arbitrary drawings."},
    ("expert-robot@e7be083b754b36e90d9ebffbe9f7ef9069296e06", "eval/holdout.json", path.name),
    datetime.now(timezone.utc).isoformat(),
    sha256(data).hexdigest(),
)
print(json.dumps(compare_observation(observation, [
    Prediction(metric, count, 0, units[metric]) for metric, count in expected.items()
]), indent=2))
