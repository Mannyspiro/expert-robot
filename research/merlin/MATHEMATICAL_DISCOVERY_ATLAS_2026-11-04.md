# Merlin Mathematical Discovery Atlas

Date: 2026-11-04

## Purpose

The atlas turns mathematical curiosity into falsifiable, auditable research records. It is a research index, not a list of discoveries. Each candidate includes a formal definition, assumptions, inverse classification, Lean proof obligations, numerical experiments, counterexample obligations, evidence basis and open questions.

## Initial families

- Hyperbolic geometry: Möbius actions, hyperbolic functions and geodesic flow.
- Non-Euclidean transformations: geodesic dynamics and coordinate-model comparisons.
- Group theory: Lie exponential maps, finite group actions and orbit-stabilizer structure.
- Number theory: modular arithmetic and permutation criteria.
- Lattice problems: SVP/CVP definitions, low-dimensional exact experiments and basis conditioning.
- Symbolic algebra: rewrite-system termination, confluence and critical pairs.
- Unusual geometric representations: projective duality and hyperbolic embeddings of trees.

## Interpretation rules

An explicit inverse means an inverse exists under the stated domain restrictions. A local inverse is not a global inverse. A numerical inverse is an algorithmic approximation, not a mathematical inverse guarantee. Unknown means no conclusion is being claimed.

In particular, tanh on the real line has the explicit inverse artanh on (-1,1). Floating-point saturation and rounding collisions are finite-precision effects, not proof of mathematical one-wayness. Geometric distortion, large representations and large nominal key spaces do not establish cryptographic hardness.

## Evidence and status

The first atlas is literature-seeded, not independently reviewed. Its proof obligations are not completed Lean proofs; its numerical experiments are plans, not results; counterexample obligations are searches to perform, not evidence of absence. The machine-readable record marks these states explicitly.

## Workflow

1. Merlin selects a candidate and freezes its assumptions and statement.
2. Ideonomy proposes related formulations and analogies, recording the transformation from source concept to new conjecture.
3. Hermes dispatches separate research, numerical-experiment and proof-search stages to real configured engines.
4. Each engine emits exact artifact bytes, tool/version metadata, seeds and environment details.
5. The canonical registry stores the artifact and the knowledge graph links it to the hypothesis.
6. CACE independently checks the exact artifact digest and applicable proof/evidence claims.
7. Human review decides whether a candidate advances. No research handler receives promotion authority.

## Titan boundary

This atlas does not modify Titan cryptography. All experimental mathematical candidates are marked cryptographically ineligible. Titan production profiles must continue to rely on reviewed standardized primitives and protocol designs; novelty, obscurity, symbol complexity, nonlinear appearance or key-space counting are not substitutes for cryptanalysis and independent review.

## Initial next investigations

- Formalize tanh/artanh identities and domain restrictions in Lean.
- Formalize Möbius action composition and upper-half-plane preservation.
- Build low-dimensional exact SVP/CVP fixtures with independently checked optima.
- Add rewrite-system critical-pair enumeration for small finite rule sets.
- Add reproducible numerical notebooks/scripts only after each experiment has a declared metric, precision, seed and expected invariant.
