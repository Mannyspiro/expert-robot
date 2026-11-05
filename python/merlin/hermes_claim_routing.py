"""Fail-closed Hermes claim routing and separate outcome evaluation."""
from collections import Counter
from enum import Enum
from typing import Any, Iterable, Mapping

class Route(str, Enum):
    RESEARCH_ONLY = "research_only"
    LEAN_COMPILE = "lean_compile"
    QUARANTINE = "quarantine"
    REJECT = "reject"

def route_claim(claim: Mapping[str, Any]):
    if not isinstance(claim, Mapping): return (Route.REJECT, ("not_a_mapping",))
    if claim.get("previously_rejected") is True: return (Route.QUARANTINE, ("previously_rejected",))
    for key in ("claim_id", "formal_statement", "lean_source"):
        if not isinstance(claim.get(key), str) or not claim[key].strip():
            return (Route.REJECT, ("missing_or_invalid_required_text",))
    for key in ("assumptions", "falsifiability", "source_ids"):
        value = claim.get(key)
        if not isinstance(value, list) or not value or any(not isinstance(x, str) or not x.strip() for x in value):
            return (Route.REJECT, ("missing_or_invalid_evidence_fields",))
    statement, source = claim["formal_statement"].strip(), claim["lean_source"]
    if statement not in source: return (Route.RESEARCH_ONLY, ("statement_not_grounded_in_lean_source",))
    if any(x in source.lower() for x in ("sorry", "admit", "axiom ")):
        return (Route.RESEARCH_ONLY, ("placeholder_or_unreviewed_axiom",))
    if claim.get("ambiguity") is True or claim.get("eligibility") == "ambiguous":
        return (Route.RESEARCH_ONLY, ("ambiguous_claim",))
    return (Route.LEAN_COMPILE, ("complete_grounded_formal_claim",))

def evaluate_routing(examples: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    counts = Counter(); rows = []
    for item in examples:
        expected = item["expected_route"]; actual, reasons = route_claim(item["claim"])
        if expected == Route.LEAN_COMPILE.value and actual != Route.LEAN_COMPILE: counts["missed_eligibility"] += 1
        if expected != Route.LEAN_COMPILE.value and actual == Route.LEAN_COMPILE: counts["false_eligibility"] += 1
        if actual == Route.LEAN_COMPILE and expected != Route.LEAN_COMPILE.value: counts["unnecessary_lean_dispatch"] += 1
        outcome = item.get("outcome", {})
        for key in ("compilation_failure", "cace_rejection"):
            if outcome.get(key) is True: counts[key] += 1
        rows.append({"id": item["id"], "expected_route": expected, "actual_route": actual.value, "reason_codes": list(reasons)})
    keys = ("false_eligibility", "missed_eligibility", "unnecessary_lean_dispatch", "compilation_failure", "cace_rejection")
    return {"schema": "hermes-routing-evaluation/1", "total": len(rows), "metrics": {k: counts[k] for k in keys}, "rows": rows}

def assert_no_heldout_overlap(train, heldout):
    overlap = {x["id"] for x in train} & {x["id"] for x in heldout}
    if overlap: raise ValueError("training/held-out leakage: " + ", ".join(sorted(overlap)))
