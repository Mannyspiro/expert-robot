import json
from pathlib import Path
from merlin.hermes_claim_routing import Route, route_claim, evaluate_routing, assert_no_heldout_overlap
ROOT = Path(__file__).parent / "fixtures"
def load(name): return json.loads((ROOT / name).read_text())
def test_train_metrics_are_clean():
    report = evaluate_routing(load("hermes-routing-train.json"))
    assert report["metrics"]["false_eligibility"] == 0
    assert report["metrics"]["missed_eligibility"] == 0
    assert report["metrics"]["unnecessary_lean_dispatch"] == 0
def test_heldout_is_disjoint_and_cace_rejection_separate():
    train, held = load("hermes-routing-train.json"), load("hermes-routing-heldout.json")
    assert_no_heldout_overlap(train, held)
    report = evaluate_routing(held)
    assert report["metrics"]["cace_rejection"] == 1
    assert report["metrics"]["false_eligibility"] == 0
def test_rejected_claim_is_quarantined():
    assert route_claim(load("hermes-routing-heldout.json")[3]["claim"])[0] is Route.QUARANTINE
def test_overlap_fails_closed():
    item = load("hermes-routing-train.json")[0]
    try: assert_no_heldout_overlap([item], [item])
    except ValueError: pass
    else: raise AssertionError("overlap accepted")
