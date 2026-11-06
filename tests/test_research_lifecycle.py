from merlin.research_lifecycle import ResearchLifecycle, StageEvidence, STAGES


def evidence(stage, status="completed"):
    return StageEvidence(stage, "a" * 64, ("source:1",), "b" * 40, "engine", "1.0", status)


def test_lifecycle_requires_order_and_full_provenance():
    flow = ResearchLifecycle("hyp-1")
    for stage in STAGES[1:]:
        status = "compiled" if stage == "formalization" else "verified" if stage == "independent_verification" else "completed"
        if stage == "independent_verification":
            flow = flow.advance(evidence(stage, status), independent_receipt_verifier=lambda item: item == evidence(stage, status))
        else:
            flow = flow.advance(evidence(stage, status))
    assert flow.terminal_status == "independently_verified"
    assert flow.to_dict()["promotion_authority"] is False


def test_out_of_order_or_missing_provenance_rejected():
    flow = ResearchLifecycle("hyp-1")
    try:
        flow.advance(evidence("experiment"))
    except ValueError:
        pass
    else:
        raise AssertionError("out-of-order stage accepted")
    bad = StageEvidence("literature_evidence", "bad", (), "", "", "", "completed")
    try:
        flow.advance(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("incomplete provenance accepted")


def test_unavailable_cace_does_not_become_verified():
    flow = ResearchLifecycle("hyp-1")
    for stage in STAGES[1:-1]:
        status = "compiled" if stage == "formalization" else "completed"
        flow = flow.advance(evidence(stage, status))
    flow = flow.advance(evidence("independent_verification", "blocked"))
    assert flow.terminal_status == "verification_blocked"
    assert flow.to_dict()["promotion_authority"] is False
