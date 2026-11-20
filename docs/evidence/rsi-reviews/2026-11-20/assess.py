"""Compare heldout drafting outcomes to declared production acceptance criteria."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

from merlin.scientific_loop import Observation, Prediction, compare_observation

evaluation = Path(sys.argv[1])
data = evaluation.read_bytes()
matrix = json.loads(data)
positives = [case for case, label in matrix["holdout"].items() if label == "accept"]
withholds = [case for case, label in matrix["holdout"].items() if label == "withhold"]
def verify(arm):
    observed = matrix["observed"][arm]
    metrics = {"heldout_valid_accepted": sum(observed[k] == "accept" for k in positives),
               "heldout_invalid_or_ambiguous_withheld": sum(observed[k] == "withhold" for k in withholds),
               "development_correct": sum(observed[k] == v for k,v in matrix["train"].items())}
    goals = dict(zip(metrics,[len(positives),len(withholds),len(matrix["train"])]))
    units = dict.fromkeys(metrics,"cases")
    obs = Observation(arm, "Does the review preserve valid registered diagrams and block flawed ones?",
                      "Independent synthetic registered wiring review",
                      metrics,units,dict.fromkeys(metrics,0),
                      {"scope":"Finite exact synthetic test count, no estimate for freeform drawings."},
                      ("expert-robot@584b948332b76596311d75133c0430d761e2f67a","eval/holdout.json"),
                      datetime.now(timezone.utc).isoformat(),sha256(data).hexdigest())
    return compare_observation(obs,[Prediction(k,v,0,units[k]) for k,v in goals.items()])

print(json.dumps({arm:verify(arm) for arm in matrix["observed"]},indent=2))
