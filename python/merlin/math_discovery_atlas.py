"""Deterministic mathematical discovery atlas for Merlin.

This catalogue creates falsifiable research records, not cryptographic claims.
Every candidate is explicitly ineligible for production cryptography.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Mapping

ATLAS_SCHEMA = "merlin-math-discovery-atlas/1"

@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    family: str
    title: str
    formal_definition: str
    domain_and_assumptions: tuple[str, ...]
    inverse_classification: str
    lean_obligations: tuple[str, ...]
    numerical_experiments: tuple[str, ...]
    counterexample_obligations: tuple[str, ...]
    evidence_basis: tuple[str, ...]
    open_questions: tuple[str, ...]
    cryptographic_status: str = "not_eligible"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

_CANDIDATES = (
    Candidate(
        "hyperbolic-mobius-action", "hyperbolic_geometry",
        "Möbius transformations on the upper half-plane",
        "For a real matrix A=[[a,b],[c,d]] with ad-bc>0, act by z ↦ (az+b)/(cz+d) on the upper half-plane; matrices differing by a nonzero scalar induce the same projective map.",
        ("z has positive imaginary part", "matrix entries are real", "determinant is positive"),
        "explicit_inverse",
        ("Prove the action preserves the upper half-plane.", "Prove composition corresponds to matrix multiplication.", "Prove the inverse action is induced by the inverse matrix."),
        ("Compare complex formula with matrix action on sampled points.", "Track distance and round-trip error near large coefficients.", "Test determinant rescaling invariance."),
        ("Test determinant zero and negative determinant boundaries.", "Search for numerical instability near cz+d=0.", "Check projectively equivalent matrices."),
        ("Classical PSL(2,R) action; standard hyperbolic geometry."),
        ("Quantify conditioning under coefficient scaling.", "Distinguish exact algebra from floating-point behavior."),
    ),
    Candidate(
        "hyperbolic-tanh-domain", "hyperbolic_geometry",
        "Hyperbolic tangent and its inverse",
        "tanh: R → (-1,1), tanh(x)=(exp(2x)-1)/(exp(2x)+1); artanh(y)=0.5 log((1+y)/(1-y)).",
        ("Real-valued exact mathematics", "inverse restricted to -1<y<1"),
        "explicit_inverse",
        ("Prove artanh(tanh(x))=x for real x.", "Prove tanh(artanh(y))=y for -1<y<1.", "Prove strict monotonicity and range."),
        ("Measure cancellation and saturation in float32/float64.", "Compare stable library implementations with direct exponential formula.", "Plot inverse sensitivity near ±1."),
        ("Test endpoints ±1, values outside range, overflow and underflow.", "Construct finite-precision collisions caused by rounding."),
        ("Standard real analysis identities."),
        ("Document precision-dependent loss of recoverability; do not confuse it with mathematical one-wayness."),
    ),
    Candidate(
        "hyperbolic-geodesic-flow", "non_euclidean_transformations",
        "Geodesic flow on constant-curvature surfaces",
        "Study the geodesic flow on the unit tangent bundle of a complete surface with constant curvature K<0, using the metric geodesic equations.",
        ("Smooth complete Riemannian surface", "constant negative curvature", "initial unit tangent vector"),
        "numerical_inverse",
        ("Formalize geodesic equation under stated regularity assumptions.", "Prove speed is conserved.", "State conditions for uniqueness and time reversibility."),
        ("Integrate geodesics and compare conserved speed.", "Compare forward-then-backward integration error across step sizes.", "Measure sensitivity to initial conditions."),
        ("Test incomplete manifolds and coordinate singularities.", "Separate dynamical sensitivity from non-invertibility."),
        ("Riemannian geometry and geodesic-flow theory."),
        ("Specify manifold and coordinates before any numerical claim."),
    ),
    Candidate(
        "lie-group-exponential", "group_theory",
        "Lie group exponential and logarithm maps",
        "For a matrix Lie group G with Lie algebra g, exp maps X in g to the matrix exponential; log is only locally single-valued near the identity in general.",
        ("Finite-dimensional matrix Lie group", "matrix norm and convergence assumptions", "local chart for logarithm"),
        "local_inverse",
        ("Prove exp(X) lies in the relevant group under hypotheses.", "Establish local inverse behavior near zero.", "Document non-injectivity outside the local chart."),
        ("Compare exp/log round trips near and far from identity.", "Measure conditioning near branch cuts and repeated eigenvalues.", "Compare scaling-and-squaring with reference precision."),
        ("Find distinct X,Y with exp(X)=exp(Y).", "Test logarithm branch ambiguity.", "Check group-specific constraints."),
        ("Standard Lie theory and matrix analysis."),
        ("Map injectivity radius and branch selection by group."),
    ),
    Candidate(
        "finite-group-orbit", "group_theory",
        "Finite group actions and orbit-stabilizer structure",
        "A finite group G acts on a set X; orbit(x)={g·x:g∈G}, stabilizer(x)={g∈G:g·x=x}.",
        ("Finite group with verified operation table or generators and relations", "Well-defined action"),
        "explicit_inverse",
        ("Prove orbit-stabilizer theorem for finite G.", "Prove action axioms for each encoded action.", "Verify subgroup properties of stabilizers."),
        ("Enumerate small groups and compare orbit sizes.", "Cross-check generator-based enumeration against multiplication tables."),
        ("Test malformed operation tables and non-actions.", "Search small countermodels to omitted axioms."),
        ("Elementary finite group theory."),
        ("Scale enumeration without confusing computational evidence with proof."),
    ),
    Candidate(
        "modular-arithmetic-structure", "number_theory",
        "Modular maps and permutation criteria",
        "For integer a and n>1, f(x)=a·x mod n is a permutation of Z/nZ exactly when gcd(a,n)=1.",
        ("Integer modulus n>1", "residue classes modulo n"),
        "explicit_inverse",
        ("Prove the permutation criterion.", "Prove inverse multiplier is a modular inverse when gcd(a,n)=1."),
        ("Exhaustively enumerate small moduli.", "Compare extended Euclidean inverse with brute force."),
        ("Test composite moduli and non-coprime multipliers.", "Check zero and unit edge cases."),
        ("Elementary number theory; Euclidean algorithm."),
        ("Keep arithmetic permutation facts separate from cryptographic security."),
    ),
    Candidate(
        "lattice-cvp-svp", "lattice_problems",
        "Closest and shortest vector problems",
        "For full-rank basis B in R^n, lattice L(B)={Bz:z∈Z^n}; SVP seeks a shortest nonzero lattice vector and CVP seeks a lattice point nearest a target t.",
        ("Full-rank basis", "Euclidean norm unless otherwise stated", "dimension and encoding precision declared"),
        "unknown",
        ("Formalize lattice and basis equivalence.", "Prove lower/upper bounds for selected toy instances.", "State exact versus approximate problem variants."),
        ("Enumerate exact solutions in low dimensions.", "Compare Babai nearest-plane output with exact enumeration.", "Track basis conditioning and precision."),
        ("Generate adversarial skewed bases.", "Test ties, rank deficiency and precision loss.", "Compare results under unimodular basis changes."),
        ("Established computational number theory; ML-KEM standard references motivate relevance but do not prove a new construction."),
        ("No hardness claim without a precise problem distribution and reduction analysis."),
    ),
    Candidate(
        "symbolic-rewrite-confluence", "symbolic_algebra",
        "Termination and confluence of rewrite systems",
        "A rewrite relation → on terms is terminating if no infinite rewrite chain exists and confluent if u←*t→*v implies a common descendant.",
        ("Explicit term grammar", "oriented rewrite rules", "termination order if claimed"),
        "unknown",
        ("Prove termination using a well-founded measure.", "Check local confluence and apply an appropriate confluence theorem.", "Prove type preservation for typed terms."),
        ("Enumerate critical pairs for finite rule sets.", "Compare normal forms under different rewrite orders.", "Measure rewrite growth and normalization cost."),
        ("Search for loops and divergent normal forms.", "Test overlapping left-hand sides and non-terminating rules."),
        ("Term rewriting theory; Knuth-Bendix methods."),
        ("Separate a heuristic simplifier from a proven normalizer."),
    ),
    Candidate(
        "projective-duality", "unusual_geometric_representations",
        "Projective duality of points and lines",
        "In a projective plane, represent a line by homogeneous coefficients and a point by homogeneous coordinates; incidence is the vanishing of their bilinear pairing.",
        ("Homogeneous coordinates modulo nonzero scale", "nondegenerate projective plane"),
        "explicit_inverse",
        ("Prove incidence is scale invariant.", "Formalize point-line duality in the selected plane.", "Verify duality twice returns the original object up to projective equivalence."),
        ("Generate random homogeneous points and lines.", "Compare determinant-based incidence with bilinear pairing.", "Test scale invariance numerically."),
        ("Test zero coordinate triples and degenerate configurations.", "Check cases at infinity."),
        ("Classical projective geometry."),
        ("Choose a concrete field and state dimension before implementation."),
    ),
    Candidate(
        "hyperbolic-embedding-distortion", "unusual_geometric_representations",
        "Tree embeddings in hyperbolic space",
        "Study maps from finite rooted trees into a specified hyperbolic metric space and quantify pairwise distance distortion.",
        ("Finite tree with positive edge weights", "specified curvature and metric model", "embedding and distortion definition fixed"),
        "unknown",
        ("Prove metric properties of the chosen model.", "State and prove distortion bounds for a restricted tree family.", "Verify coordinate-to-distance identities."),
        ("Embed balanced and unbalanced trees.", "Measure distortion versus depth and branching factor.", "Compare Poincaré-ball and hyperboloid coordinates."),
        ("Test boundary-near points and numerical overflow.", "Search for counterexamples to conjectured universal bounds."),
        ("Hyperbolic metric geometry and tree embedding literature."),
        ("No uniqueness or cryptographic hardness follows from geometric distortion."),
    ),
)

def atlas_candidates() -> tuple[dict[str, Any], ...]:
    return tuple(c.as_dict() for c in _CANDIDATES)

def atlas_document() -> dict[str, Any]:
    return {
        "schema": ATLAS_SCHEMA,
        "title": "Merlin Mathematical Discovery Atlas",
        "method": "candidate → formal definition → Lean obligations → numerical experiments → counterexamples → evidence assessment",
        "families": sorted({c.family for c in _CANDIDATES}),
        "candidates": list(atlas_candidates()),
        "assessment_policy": {
            "proof_status": "not_started",
            "experiment_status": "not_run",
            "evidence_status": "literature_seeded_not_independently_reviewed",
            "cryptographic_status": "not_eligible",
            "promotion_authority": False,
        },
        "promotion_gates": [
            "precise statement and assumptions",
            "reproducible experiment with environment and seeds",
            "counterexample search and boundary analysis",
            "Lean proof checked by the pinned project toolchain where applicable",
            "independent CACE verification of exact artifact bytes",
            "human review; no automatic production promotion",
        ],
    }

def canonical_atlas_bytes() -> bytes:
    return (json.dumps(atlas_document(), ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")

def atlas_digest() -> str:
    return hashlib.sha256(canonical_atlas_bytes()).hexdigest()

def validate_candidate(candidate: Mapping[str, Any]) -> list[str]:
    errors = []
    required = ("candidate_id", "family", "formal_definition", "inverse_classification",
                "lean_obligations", "numerical_experiments", "counterexample_obligations",
                "evidence_basis", "open_questions")
    for key in required:
        if key not in candidate or candidate[key] in (None, "", [], ()):
            errors.append("missing required field: " + key)
    if candidate.get("inverse_classification") not in {
        "explicit_inverse", "local_inverse", "numerical_inverse", "unknown"
    }:
        errors.append("invalid inverse classification")
    if candidate.get("cryptographic_status") != "not_eligible":
        errors.append("experimental candidates must remain cryptographically ineligible")
    return errors

def hermes_math_atlas_research_executor(task, context):
    """Emit atlas or a selected family as an immutable Hermes research artifact."""
    objective = str(task.get("objective", "")).lower()
    family = task.get("family")
    if task.get("stage") != "research" or not any(
        term in objective for term in ("mathematical discovery atlas", "math atlas", "mathematical discovery")
    ):
        raise ValueError("task must request the mathematical discovery atlas")
    document = atlas_document()
    if family is not None:
        selected = [c for c in document["candidates"] if c["family"] == family]
        if not selected:
            raise ValueError("unknown atlas family")
        document["candidates"] = selected
        document["families"] = [family]
    document["task"] = {
        "task_id": context.task_id,
        "hypothesis_id": context.hypothesis_id,
        "objective": str(task.get("objective", "")),
    }
    payload = (json.dumps(document, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    return {
        "artifact_bytes": payload,
        "media_type": "application/vnd.merlin.math-atlas+json",
        "summary": "Generated typed mathematical discovery atlas with proof, experiment and counterexample plans.",
        "metadata": {
            "artifact_schema": ATLAS_SCHEMA,
            "atlas_sha256": atlas_digest(),
            "candidate_count": len(document["candidates"]),
            "families": document["families"],
            "promotion_authority": False,
        },
    }

__all__ = ["ATLAS_SCHEMA", "atlas_candidates", "atlas_document",
           "canonical_atlas_bytes", "atlas_digest", "validate_candidate",
           "hermes_math_atlas_research_executor"]
