# Real-World Equation Atlas — Merlin Research Package

This directory contains the 100-entry atlas, research prompt, Merlin context, source crosswalk, normalized entry tranche, validation code, reproducible experiments, XMG contract, Lean theorem candidates, and Math Kung Fu lesson sequence.

## Research and data files
- `PROMPT.md` — complete Merlin research instruction.
- `ATLAS_001-100.md` — initial equation atlas.
- `SOURCES_AND_CITATION_CROSSWALK.md` — source register and equation-ID mapping, with explicit application-specific gaps.
- `NORMALIZED_ENTRIES_001-020.json` — legacy metadata migration input.
- `NORMALIZED_ENTRIES_021-030.json` — canonical robotics, dynamics, and control tranche with claim-linked sources.
- `equation-entry.schema.json` — canonical machine-readable entry schema, including SI dimension metadata.
- `NORMALIZED_ENTRIES_001-020_V0.3.json` — generated canonical migration output (created and validated in CI).
- `EVIDENCE_RECEIPT_CONTRACT_V0.1.md` — content-addressed reproducibility receipt contract.
- `evidence-receipt.schema.json` — schema for receipt validation.
- `MERLIN_CONTEXT.md` — relevant project context and research architecture.
- `PHASE_0.3_EXECUTION_PLAN.md` — next-stage workstreams, evidence receipts, verification ladder, XMG integration, and recommended execution order.
- `RESEARCH_STATUS_V0.2.md` — current status record (document heading tracks v0.3 and records the observed Avrea run).
- `XMG_MULTI_FRAME_CONTRACT.md` — typed multi-frame representation, transformations, invariants, and visualization contract.
- `LESSON_001_OPTIMIZATION.md`, `LESSON_SEQUENCE_V0.2.md` — learning modules.

## Verification and experiments
- `VERIFICATION_AND_LEAN.md` — evidence layers and promotion gates.
- `EXPERIMENT_RUNBOOK.md` — reproducible commands and experiment definitions.
- `BASELINE_EXPERIMENT_RESULTS.json` — local reference values.
- `python/merlin/equation_atlas/` — dimensional, symbolic, numerical, canonical normalization, and evidence-receipt modules.
- `tests/test_merlin_equation_atlas.py` — regression tests.
- `formal/MathAI/EquationAtlas.lean` — active Lean theorem candidates.
- `formal/MathAI/Audit.lean` and `formal/theorem_registry.json` — axiom-audit binding and theorem candidate registry.

## Avrea execution evidence
On 2026-11-04, CI run 1271 (run ID `41837021534`) completed successfully on the configured Avrea runner for the earlier starter implementation. The canonical schema migration and evidence-receipt implementation passed Avrea CI run #1289 (run ID `41838851056`). The downloaded artifact was inspected and contains the five-family synthetic baseline, the generated canonical 20-entry tranche, and a receipt with nine source hashes. The artifact bundle SHA-256 is `03c811b6d1af905bd0a6dd2605ce4055b71eec2f04e538542cca19b87aae42fb`. All migrated entries remain `UNVERIFIED`; this run does not establish empirical validity or Lean proof success. That run does not establish empirical validity or Lean proof success. The combined 001–040 tranche is now queued for its own Avrea validation.

## Status and limitations
This is an initial research implementation, not a completed verification of all 100 equations. Entries 001–020 are migrated from legacy metadata; entries 021–030 are a sourced robotics/control tranche; entries 031–040 cover PDEs, conservation laws, fluids, and electromagnetism. The normalizer now combines all four batches into a canonical 50-entry output and validates each entry against JSON Schema; the 40-entry revision still requires its own Avrea run. All entries remain `UNVERIFIED`. Executable dimensional checks still cover eight representative relations; source coverage gaps remain. Lean code remains candidate until the separate pinned formal-qualification workflow compiles it and its axiom report is reviewed. Numerical baselines are synthetic reproducibility checks, not empirical validation.

## Next completion gates
1. Close specialist primary-source gaps with claim-level citations.
2. Inspect the Avrea run for the combined 001–040 migration, schema checks, and evidence bundle.
3. Correct any failures, then normalize entries 031–040 with primary sources and units.
4. Extend dimensional and symbolic checks across all applicable entries.
5. Add convergence, sensitivity, uncertainty, and benchmark comparisons to the numerical experiments.
6. Run and inspect the separate pinned Lean qualification workflow.
7. Extend evidence receipts to bind equation versions, dependency lock, seeds, tolerances, test output and benchmark provenance.
8. Serialize XMG objects and generate deterministic multi-frame SVG/GLTF views with transform invariants.
9. Generate lessons only from entries with explicit evidence labels.

- `NORMALIZED_ENTRIES_031-040.json` — canonical PDE, conservation-law, fluid, and electromagnetism tranche.
- `NORMALIZED_ENTRIES_001-040_V0.3.json` — generated combined canonical output (created and schema-validated in CI).


## Latest verified run boundary
Avrea CI run #1302 (run ID `41839694953`) passed for commit `85bd57ea0496d6935bd6e29273b91b08fee76b29` and produced the 30-entry artifact. The artifact was downloaded and inspected: it contains entries RWEA-001–030, all `UNVERIFIED`, plus the synthetic baseline and a provenance receipt. Its receipt does not include RWEA-031–040. The 40-entry revision is authored but awaits a new CI run.

- `NORMALIZED_ENTRIES_041-050.json` — canonical Fourier, sampling, signal-processing, and information-theory tranche.
- `NORMALIZED_ENTRIES_001-050_V0.3.json` — generated combined canonical output (pending Avrea validation).


## Latest authored tranche
RWEA-041–050 has been added with source links S30–S32. The combined 001–050 normalizer and CI artifact path have been updated, but this revision is not yet Avrea-validated. All 50 entries remain UNVERIFIED.


## Phase 0.6 — stochastic atlas tranche
- `NORMALIZED_ENTRIES_051-060.json` — canonical Markov chains, Poisson process, Brownian motion, Langevin SDE, Fokker–Planck, Bayes, Kalman filtering, Fisher information, and entropy production.
- `NORMALIZED_ENTRIES_001-060_V0.3.json` — generated combined canonical output; Avrea validation pending.
- `python/merlin/equation_atlas/experiments/stochastic.py` — deterministic synthetic stochastic-model checks.
- `tests/test_merlin_stochastic.py` — regression tests for stationary distributions, Brownian variance, Bayesian updating, scalar Kalman update, Ornstein–Uhlenbeck variance, and entropy production.

All 60 entries remain `UNVERIFIED`. The earlier Avrea success applies only to the 001–030 revision; no CI pass is claimed for the current 001–060 revision.


## Phase 0.7 — biological and collective systems
- `NORMALIZED_ENTRIES_061-070.json` — reaction-diffusion, Turing instability, cellular automata, population/evolutionary dynamics, neural population models, biological information, synchronization, percolation, and self-organization.
- `NORMALIZED_ENTRIES_001-070_V0.3.json` — generated combined canonical output; CI/Avrea validation pending.
- `python/merlin/equation_atlas/experiments/biological_complexity.py` — deterministic toy checks.
- `tests/test_merlin_biological_complexity.py` — regression tests for diffusion mass conservation, logistic boundedness, replicator simplex invariance, Rule 30, Kuramoto synchronization, mutual information, and graph connectivity.

All 70 entries remain `UNVERIFIED`. The 061–070 sources are foundational references; the percolation entry especially needs a dedicated percolation-theory source before stronger threshold claims.


## Phase 0.8 — invasion, epidemics, stochastic chemistry, and adaptive networks
- `NORMALIZED_ENTRIES_071-080.json` adds Fisher-KPP invasion waves, Lotka-Volterra predator-prey dynamics, SIR epidemics, network metapopulation migration, Amari neural fields, the chemical master equation, Gillespie SSA, the reaction-diffusion master equation, adaptive coevolutionary networks, and generalized Lotka-Volterra communities.
- Source crosswalk S48–S56 provides dedicated foundational references. Entry-level claims remain bounded by each source's stated assumptions.
- `XMG_CROSS_DOMAIN_OPERATOR_CONTRACT_V0.1.json` defines typed contracts for reaction, diffusion, advection, graph coupling, stochastic jumps, phase coupling, neural convolution, and frame projection.
- `python/merlin/equation_atlas/operators.py` validates declared operator pipelines and exact frame compatibility. It validates contracts only; it does not execute the underlying physics.
- `tests/test_merlin_xmg_operator_contract.py` tests valid composition, mismatched frames, invalid input/output types, and unknown operators.
- The normalizer and Avrea CI have been extended to 80 entries and include the new contract/test files in the evidence receipt. This latest revision awaits its own CI run; the prior successful run #1343 applies only to its exact earlier commit.
- All 80 entries remain `UNVERIFIED`. No empirical validation, production operator runtime, or Lean qualification is claimed.


## Phase 0.9 — first executable simulation primitives
- Added `python/merlin/equation_atlas/simulation.py` with an explicit-Euler integration interface, periodic 1-D diffusion RHS, periodic first-order upwind advection RHS, symmetric graph-exchange RHS, and direct-method Gillespie SSA.
- Every deterministic run records the initial-state hash, parameter hash, final-state hash, time step, step count, method, seed, boundary declaration, code revision, and a canonical run hash.
- SSA records seeded trajectory states/times, reaction indices, parameter and state hashes, and rejects invalid propensities or negative molecular counts.
- Added synthetic regression tests for periodic diffusion conservation, periodic advection conservation, balanced graph-exchange conservation and nonnegativity, RHS shape validation, seeded SSA reproducibility, and molecule-count conservation.
- CI now runs the simulation-engine test module and includes both engine source and tests in the evidence receipt.
- Scope remains deliberately limited: these are small reference solvers, not production-grade adaptive integrators, GPU solvers, validated physical simulators, or empirical models. Stability/CFL limits and units must be checked by each model configuration.
- The Phase 0.9 code revision is awaiting its own Avrea CI result. The previously passed run #1354 does not cover these new files.


### Phase 0.9 verification — Avrea CI run #1360
- Run ID: `41843498944`; successful conclusion for PR head `2854e92eafd36b5ad8de3f8ef6a6e4066c44738e`.
- All workflow steps completed successfully, including the equation-atlas stage (which runs `test_merlin_simulation_engine.py`), artifact publication, CAD/engineering checks, CACE, Hermes, and independent smoke tests.
- Downloaded artifact ZIP SHA-256: `39b32edc8e190143cf62cc0621860fe5a0bc8fa7aff8a798ab803409ed89daa3`.
- Evidence receipt SHA-256: `690efca64e79c3efb40bfd3e4b180118ad14ecb98cd233019d72cb6df9b22cd9`.
- Normalized atlas SHA-256: `da3f9edba190fe667aecbae21eabfe422350e1be9a139fcba2bcea187236dc51`; inspection confirmed 80 ordered unique entries, RWEA-001–080.
- Receipt records PR merge-ref snapshot `7cbaa1f40e6e2c0c5e5e787add3e85d552874e0f`, not the branch-head SHA. It includes hashes for `simulation.py` and `test_merlin_simulation_engine.py`.
- Verification is limited to the recorded synthetic test suite and byte-level provenance; it does not establish empirical validity or scientific truth.
