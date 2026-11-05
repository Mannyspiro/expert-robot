from merlin.math_discovery_atlas import (
    ATLAS_SCHEMA, atlas_candidates, atlas_digest, canonical_atlas_bytes,
    validate_candidate,
)

def test_atlas_is_deterministic_and_populated():
    assert ATLAS_SCHEMA == "merlin-math-discovery-atlas/1"
    assert canonical_atlas_bytes() == canonical_atlas_bytes()
    assert len(atlas_candidates()) >= 8
    assert len(atlas_digest()) == 64

def test_every_candidate_has_required_research_fields_and_is_not_crypto():
    for candidate in atlas_candidates():
        assert validate_candidate(candidate) == []
        assert candidate["cryptographic_status"] == "not_eligible"

def test_atlas_covers_requested_families():
    families = {candidate["family"] for candidate in atlas_candidates()}
    assert {
        "hyperbolic_geometry", "non_euclidean_transformations", "group_theory",
        "number_theory", "lattice_problems", "symbolic_algebra",
        "unusual_geometric_representations",
    } <= families

def test_missing_obligations_are_rejected():
    assert "missing required field: lean_obligations" in validate_candidate({
        "candidate_id": "bad", "family": "test", "formal_definition": "x",
        "inverse_classification": "unknown", "numerical_experiments": ["run"],
        "counterexample_obligations": ["search"], "evidence_basis": ["source"],
        "open_questions": ["why"], "cryptographic_status": "not_eligible",
    })
