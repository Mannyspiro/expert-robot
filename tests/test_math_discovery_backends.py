from __future__ import annotations

import pytest

from merlin.cace_adapter import CaceVerificationAdapter
from merlin.event_outbox import MerlinEventOutbox
from merlin.math_discovery_backends import (
    COUNTEREXAMPLE_ENGINE, COUNTEREXAMPLE_ENGINE_VERSION,
    RK4_ENGINE, RK4_ENGINE_VERSION, default_runtime_environment,
    finite_cyclic_translation_search, rk4_solver, round_robin_ideonomy_claim,
)
from merlin.math_discovery_integrated import (
    BoundedCounterexampleAdapter, IdeonomyConjectureAdapter,
    ReproducibleNumericalAdapter,
)
from merlin.project_registry import MerlinRegistry


def test_actual_rk4_backend_is_replayed_and_hashed(tmp_path):
    adapter = ReproducibleNumericalAdapter(
        rk4_solver, engine=RK4_ENGINE, engine_version=RK4_ENGINE_VERSION,
        tool_version="python-standard-library", environment=default_runtime_environment(),
    )
    result = adapter({
        "seed": 0,
        "precision": "IEEE-754 binary64",
        "parameters": {
            "matrix": [[-1.0]], "initial_state": [1.0],
            "start": 0.0, "stop": 1.0, "step": 0.01,
        },
    })
    assert result["status"] == "completed"
    assert result["reproducible"] is True
    assert result["engine"] == RK4_ENGINE
    assert result["engine_version"] == RK4_ENGINE_VERSION
    assert result["raw_output_sha256"]


def test_finite_counterexample_search_is_explicitly_bounded():
    adapter = BoundedCounterexampleAdapter(
        finite_cyclic_translation_search,
        engine=COUNTEREXAMPLE_ENGINE,
        engine_version=COUNTEREXAMPLE_ENGINE_VERSION,
        tool_version="python-integer-enumeration/1",
    )
    result = adapter({
        "seed": 0, "precision": "exact integer arithmetic",
        "search_domain": "cyclic_translation_bijectivity",
        "bounds": {"n_min": 1, "n_max": 20, "k_min": -20, "k_max": 20},
        "method": "exhaustive enumeration of every residue for each (n,k)",
    })
    assert result["status"] == "completed"
    assert result["termination_status"] == "complete"
    assert result["counterexample"] is None
    assert result["search_scope"]["bounds"]["n_max"] == 20
    assert result["engine_version"] == COUNTEREXAMPLE_ENGINE_VERSION


def test_ideonomy_emits_only_grounded_claims_with_source_identity():
    adapter = IdeonomyConjectureAdapter(round_robin_ideonomy_claim)
    outputs = adapter({
        "candidate": {"candidate_id": "round-robin-queue"},
        "seeds": [{"conjecture_id": "queue-state-transition"}],
    })
    eligible = [item for item in outputs if item["lean_translation_eligible"]]
    assert eligible
    for claim in eligible:
        assert claim["formal_statement"] in claim["lean_source"]
        assert set(claim["source_ids"]) == set(claim["source_identity"]["primitive_ids"])
        assert claim["assumptions"]
        assert claim["falsifiable_statement"]
        assert "sorry" not in claim["lean_source"]
    assert any(item["epistemic_status"] == "ideonomy_proposal_no_grounded_claim"
               for item in outputs)


def test_cace_transport_unconfigured_fails_closed(tmp_path):
    registry = MerlinRegistry(tmp_path / "registry")
    registry.register_project("merlin-test", "Merlin local integration test")
    outbox = MerlinEventOutbox(tmp_path / "outbox.sqlite3")
    cace = CaceVerificationAdapter(
        verify_transport=None, registry=registry, outbox=outbox,
    )
    with pytest.raises(RuntimeError, match="transport is not configured"):
        cace.verify_artifact(
            project_id="merlin-test", repository="Mannyspiro/expert-robot",
            commit_sha="0" * 40, artifact_sha256="0" * 64,
            artifact_kind="research", artifact_schema="test/1",
            requester_id="merlin-local-test", logical_path="tests/artifact.json",
        )
