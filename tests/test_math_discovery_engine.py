from merlin.math_discovery_engine import (
    MathematicalDiscoveryEngine, ResearchAdapters, compare_experiment_to_claim,
    evidence_score, generate_conjecture_seeds, generate_lean_skeleton,
)
from merlin.math_discovery_atlas import atlas_candidates

def test_seed_generation_is_explicitly_hypothetical():
    seeds = generate_conjecture_seeds(atlas_candidates()[0])
    assert seeds
    assert all(s["status"] == "hypothesis_seed_not_conjecture" for s in seeds)

def test_lean_output_is_a_placeholder_not_a_claimed_proof():
    source = generate_lean_skeleton({
        "conjecture_id": "tanh-inverse", "statement_prompt": "prove inverse",
        "assumptions": ["x is real"],
    })
    assert "sorry" in source
    assert "not a theorem statement or verified proof" in source

def test_missing_adapters_do_not_fabricate_results():
    engine = MathematicalDiscoveryEngine(ResearchAdapters())
    assert engine.run_numerical({"seed": 7})["status"] == "not_dispatched"
    assert engine.search_counterexamples({"seed": 7})["status"] == "not_dispatched"
    assert engine.verify_with_cace({"artifact_sha256": "a"})["verification_status"] == "not_requested"

def test_reproducibility_fields_are_mandatory():
    engine = MathematicalDiscoveryEngine(ResearchAdapters(numerical=lambda _: {
        "engine": "toy", "engine_version": "1", "tool_version": "1",
        "precision": "float64", "seed": 42, "status": "completed",
    }))
    result = engine.run_numerical({})
    assert result["seed"] == 42
    assert len(result["artifact_sha256"]) == 64

def test_experiment_comparison_does_not_claim_proof():
    result = compare_experiment_to_claim({}, {"formal_comparison": {
        "status": "consistent_with_claim", "method": "interval check",
        "tolerance": 1e-8, "scope": "sampled domain",
    }})
    assert result["status"] == "consistent_with_claim"
    assert "not a formal proof" in result["warning"]

def test_ranking_weights_evidence_and_reproducibility():
    weak = {"proof": {}, "experiment": {}, "counterexample": {}, "cace": {},
            "mathematical_significance": 0.9}
    strong = {"proof": {"status": "verified"},
              "experiment": {"status": "completed", "reproducible": True,
                             "environment_digest": "abc", "seed": 2, "tool_version": "1"},
              "counterexample": {"status": "completed", "search_scope": "finite range"},
              "cace": {"verification_status": "verified"},
              "evidence_sources_reviewed": True, "mathematical_significance": 0.6}
    assert evidence_score(strong)["composite"] > evidence_score(weak)["composite"]
