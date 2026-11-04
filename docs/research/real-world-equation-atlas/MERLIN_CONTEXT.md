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
1. Record Avrea run #1302 as successful for the 001–030 revision; run a new validation for the combined 001–040 revision and inspect its complete artifact bundle.
2. Extend receipts with test-output digests, container image digests, seeds/tolerances, and experiment-to-entry mapping.
3. Normalize entries 031–040 with primary PDE, electromagnetism, and numerical-method sources.
4. Expand dimensional checks and numerical convergence/sensitivity tests.
5. Execute separate Lean qualification and inspect exact theorem/axiom output.
6. Add XMG serialization and deterministic SVG exports from tested typed geometry.
7. Feed only appropriately supported entries into Math Kung Fu lessons.

The standing authority boundary remains: research and verification can produce evidence; promotion, merge, and permission changes remain approval-gated. Capability grows, authority never expands.


## Phase 0.4 research update — 2026-11-04
- Added RWEA-031–040: local conservation balance, heat conduction, advection-diffusion, linear wave, Laplace, Poisson, linear advection, incompressible Newtonian Navier–Stokes, differential Maxwell system, and Poynting energy balance.
- Added specialist source records S27–S29 from MIT OpenCourseWare PDE, numerical PDE, and electromagnetics courses, with entry-level crosswalks and explicit evidence boundaries.
- The new tranche is authored as canonical JSON and all ten entries remain UNVERIFIED. The compact source crosswalk does not replace a full primary-source derivation audit; RWEA-040 in particular needs a dedicated Poynting-theorem derivation and material-medium convention review.
- Updated the normalizer and schema tests to combine legacy 001–020 with canonical 021–030 and 031–040 batches into a 40-entry schema-validated output. CI now includes the 031–040 source file and emits the 001–040 normalized artifact.
- This work was authored through the GitHub repository integration on the Merlin research branch. The Avrea workflow is the repository's configured self-hosted runner; no separate direct Avrea session is claimed.

## Revised next execution focus
1. Complete Avrea CI validation for the 001–040 batch and inspect its evidence artifact and receipt.
2. Add executable dimensional checks for heat, wave, diffusion, Navier–Stokes, Maxwell, and Poynting equations, including component-wise vector/tensor units.
3. Add finite-volume conservation tests, heat/wave convergence tests, and electromagnetic energy-balance tests with deterministic seeds/tolerances where applicable.
4. Expand the source audit for Maxwell constitutive media, Poynting theorem derivation, fluid closures, and domain-specific boundary conditions.
5. Run the separate Lean qualification workflow; inspect exact theorem and axiom output before any formal status change.


## Avrea result clarification — 2026-11-04
- CI run #1302 (run ID `41839694953`) completed successfully for the 001–030 revision. Its downloaded artifact contains exactly 30 canonical entries, RWEA-001 through RWEA-030, all marked UNVERIFIED, along with a synthetic baseline and provenance receipt.
- The artifact ZIP SHA-256 is `699fa3156fc24ee108d38d02246b38ac994ae03941160715ff926a73493e02c7`.
- This successful run does not cover the later RWEA-031–040 tranche or the 40-entry normalizer/receipt-path changes. A separate run is required before reporting the 40-entry batch as validated.


## Phase 0.5 research update — 2026-11-04
- Added RWEA-041–050 covering Fourier series, continuous Fourier transform, convolution, LTI frequency response, DFT, Shannon-Nyquist sampling, uniform quantization, Shannon entropy, mutual information, and power spectral density.
- Added source register S30–S32 and an entry-level crosswalk to MIT OpenCourseWare signals/systems, sampling, and digital communications materials.
- Added canonical JSON tranche `NORMALIZED_ENTRIES_041-050.json`; every entry remains UNVERIFIED. The Shannon-Nyquist and quantization entries explicitly preserve ideal assumptions; the entropy/information entries distinguish discrete entropy from continuous differential entropy.
- Extended the canonical normalizer and schema test target from 40 to 50 entries. CI now includes the 041–050 input and is configured to emit the 001–050 combined artifact and evidence receipt.
- No Avrea run, numerical experiment suite, or Lean qualification for this 50-entry revision is yet claimed.

## Revised next execution focus
1. Run Avrea CI for the combined 001–050 revision and inspect the artifact and receipt.
2. Add executable spectral tests: Fourier/DFT round-trip, Parseval, convolution theorem, aliasing demonstrations, quantization error assumptions, entropy identities, and PSD normalization.
3. Add unit-aware metadata checks for amplitude, time, frequency, PSD, entropy, and logarithm base.
4. Audit the sampling theorem's strict band-limit condition and practical anti-alias filter assumptions.
5. Extend XMG with signal frames: time, frequency, scale, phase, probability, and information units as distinct typed frames.
6. Keep Math Kung Fu lesson generation limited to entries with source and validation gates satisfied.
