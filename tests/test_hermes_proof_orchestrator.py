from merlin.hermes_proof_orchestrator import dispatch_eligible_claim


def claim(**overrides):
    value = {
        "claim_id": "claim-1",
        "formal_statement": "theorem demo : True := by trivial",
        "lean_source": "theorem demo : True := by trivial",
        "assumptions": ["none"],
        "falsifiability": ["Lean rejects source"],
        "source_ids": ["paper:1"],
    }
    value.update(overrides)
    return value


def run(value, calls):
    return dispatch_eligible_claim(
        value, repository="owner/repo", commit_sha="a" * 40,
        lean_tool_version="Lean 4.32.1",
        lean_dispatcher=lambda **kw: calls.append(("lean", kw)) or {"compilation_status": "compiled"},
        artifact_recorder=lambda **kw: calls.append(("record", kw)) or {
            "artifact_sha256": kw["artifact_sha256"], "registry_verified": True
        },
    )


def test_valid_claim_is_recorded_then_dispatched_exactly_once():
    calls = []
    receipt = run(claim(), calls)
    assert [item[0] for item in calls] == ["record", "lean"]
    assert calls[1][1]["source_sha256"] == calls[0][1]["artifact_sha256"]
    assert receipt.compilation_status == "compiled"
    assert receipt.verification_status == "pending_independent_cace_verification"
    assert receipt.promotion_authority is False


def test_malformed_ambiguous_and_rejected_claims_never_reach_lean():
    samples = [
        None,
        {},
        claim(ambiguity=True),
        claim(previously_rejected=True),
        claim(lean_source=""),
        claim(source_ids=[]),
    ]
    for sample in samples:
        calls = []
        receipt = run(sample, calls)
        assert calls == []
        assert receipt.compilation_status == "not_dispatched"


def test_untrusted_registry_result_blocks_lean():
    calls = []
    try:
        dispatch_eligible_claim(
            claim(), repository="owner/repo", commit_sha="a" * 40,
            lean_tool_version="Lean 4.32.1",
            lean_dispatcher=lambda **kw: calls.append(kw) or {"compilation_status": "compiled"},
            artifact_recorder=lambda **kw: {"artifact_sha256": "0" * 64, "registry_verified": False},
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("untrusted registry result accepted")
    assert calls == []
