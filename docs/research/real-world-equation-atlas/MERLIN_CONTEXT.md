# Merlin Context Package — Equation Atlas Research

## Source project and workflow
- Repository: Mannyspiro/expert-robot (private GitHub repository).
- Existing academic research capability: `python/merlin/academic_spider.py`, tests at `tests/test_academic_spider.py`, documentation at `docs/MERLIN_ACADEMIC_SPIDER_V01.md`.
- This contribution is isolated on branch `feat/merlin-real-world-equation-atlas-v01-20261104`, based on `feat/merlin-academic-spider-v01-20261103`.
- No protected-main changes are intended. Review through a PR before merging.

## Relevant Merlin capabilities and research themes
The current context includes: Shannon–Nyquist Signal & Aliasing Validator; MIT Ideonomy Simplex Combinator; AlphaFold/Evoformer and Ramachandran scoring; Internet Research & arXiv Literature Invariant Synthesizer; CAD/PCB/signal integrity; post-quantum cryptography; metamaterials/electromagnetism; biological growth/evolution; DNA transcription/genetics; spacetime/relativity.

User's broader research direction:
- Xenomathematics: discover alternate mathematical representations, operators, glyph systems, and coordinate systems without assuming human notation is fundamental.
- Multi-frame geometry: represent one object simultaneously in typed 2D/3D/4D/5D+ frames, with explicit projections, embeddings, mappings, and invariants.
- Geometric operators: glyphs can encode state transformations; notation is separate from the underlying operation.
- Research must separate established mathematics, computational conjectures, speculative models, and refuted ideas.
- CAD, simulation, visual explanations, and formal proofs should be integrated only where they add reproducible evidence.
- Math Kung Fu should teach intuition through shape, transformations, operators, equations, and structurally analogous problems, with concise explanations and staged difficulty.

## XMG model
Represent a shared object as:
`X = (O, {F_i}, {T_ij}, Ops, Inv)`
- O: underlying object/state.
- F_i: typed coordinate or representation frames.
- T_ij: explicit maps between frames.
- Ops: typed operations acting on objects or representations.
- Inv: invariants preserved under specified transformations.
Track frame conventions, units, dimensions, information loss, provenance, and whether a map is an active physical transformation, passive coordinate change, projection, or embedding.

## Model selection
No single equation is universally optimal. Compare models for each application on:
- predictive/fit error and external validity;
- computation, memory, and latency;
- model complexity and interpretability;
- uncertainty, sensitivity, and robustness;
- feasibility and hard constraint satisfaction.
A candidate objective is
`J(M)=w_pE_prediction+w_cE_compute+w_kE_complexity+w_uE_uncertainty+w_sE_sensitivity+w_rE_robustness+P_constraints`.
Justify weights; expose Pareto trade-offs; never hide unacceptable safety/physical constraint violations in a weighted score.

## Research pipeline
1. Ideonomy enumerates applications and candidate structures.
2. Academic Spider gathers literature with source provenance.
3. Equation Atlas normalizes equations, variables, units, assumptions, and regimes.
4. XMG maps representations and transformations across frames.
5. Simulation/CAD runs controlled numerical or physical experiments.
6. Independent verification checks derivations, dimensional consistency, tests, and reproducibility.
7. Lean formalizes mathematical claims where feasible.
8. Math Kung Fu converts supported results into visual lessons and exercises.

## Non-claims
This package records research direction and proposed outputs. It does not claim that a Merlin runtime was executed, a simulation was run, a CAD model was generated, a Lean theorem was proved, or literature was exhaustively reviewed in this commit.


## Phase 0.3 implementation update — 2026-11-04
- Avrea CI run 1271 (run ID 41837021534) completed successfully for the initial atlas checks and produced the reproducibility baseline artifact. This is execution evidence for that revision only; it is not an empirical validation or Lean qualification.
- The canonical entry schema now has an explicit per-variable `dimension` field so SI dimensional metadata is not discarded during normalization.
- `python/merlin/equation_atlas/normalize.py` migrates legacy entries 001–020 into canonical entries and validates each with JSON Schema Draft 2020-12. It preserves legacy conditions as explicit assumptions and source-register IDs as review-required citation records.
- All migrated entries are explicitly `UNVERIFIED`; a citation identifier is not treated as claim-level source validation.
- Added RWEA-021–030 for continuous/discrete state-space models, Kalman filtering, PID, LQR, serial-chain forward kinematics, Jacobians, numerical inverse kinematics, manipulator dynamics, and joint stiffness control.
- Added specialist references S22–S26: MIT Feedback Control Systems, Modern Robotics, MIT Underactuated Robotics, Åström–Murray Feedback Systems, and MIT Robotic Manipulation. Entry-level citations state the precise chapter or lecture coverage and preserve remaining application-specific limitations.
- The LQR cost matrices carry explicit time factors in their units; mixed revolute/prismatic robot coordinates and task-space angular/linear quantities remain typed rather than collapsed into one scalar unit.
- `python/merlin/equation_atlas/receipts.py` creates content-addressed evidence receipts binding the generated artifact to declared source files, code revision, command, and runtime metadata.
- CI run #1289 completed successfully on Avrea for the first 20 entries. It generated and schema-validated all 20 canonical entries, generated and validated the receipt, and published an artifact containing the baseline, canonical normalized tranche, and receipt. The artifact was downloaded and inspected; its receipt contains nine source hashes and all 20 entries are marked UNVERIFIED. A separate pending run is validating the combined 001–030 batch.

## Data and evidence rules
- Canonical entries are the typed source of truth; legacy JSON is migration input only until replaced.
- Preserve SI dimensions, coefficient dimensions, variable domains, and mixed-unit vector/matrix structure. Never silently coerce unknown units to dimensionless.
- Missing application details, boundary conditions, validity regimes, citations, and uncertainty remain explicit gaps, not invented facts.
- Keep independent evidence dimensions separate: source support, dimensional consistency, symbolic checking, computational reproduction, empirical validation, and formal verification.
- A generated receipt proves provenance and byte identity only within its declared scope. It does not establish scientific truth.
- A successful Avrea run is recorded against its exact commit and workflow run. Later changes require a new run before they are called tested.

## Next execution focus
1. Inspect the pending Avrea run for combined 001–030 validation and the complete artifact bundle.
2. Extend receipts with test-output digests, container image digests, seeds/tolerances, and experiment-to-entry mapping.
3. Normalize entries 031–040 with primary PDE, electromagnetism, and numerical-method sources.
4. Expand dimensional checks and numerical convergence/sensitivity tests.
5. Execute separate Lean qualification and inspect exact theorem/axiom output.
6. Add XMG serialization and deterministic SVG exports from tested typed geometry.
7. Feed only appropriately supported entries into Math Kung Fu lessons.

The standing authority boundary remains: research and verification can produce evidence; promotion, merge, and permission changes remain approval-gated. Capability grows, authority never expands.
