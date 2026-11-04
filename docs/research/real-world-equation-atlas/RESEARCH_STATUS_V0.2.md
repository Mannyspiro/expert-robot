# Merlin Equation Atlas — Research status v0.3

## Delivered to this branch
- Authoritative source register and equation-ID citation crosswalk.
- SI dimension algebra with eight representative homogeneity checks.
- Symbolic checks for constrained rectangle optimization, logistic equilibria, and least-squares gradient structure.
- Deterministic numerical baselines for constrained optimization, least squares, heat diffusion, logistic growth, and Fourier sampling.
- Normalized metadata tranche for RWEA-001 through RWEA-020.
- XMG typed multi-frame contract and examples.
- Lean theorem candidates for elementary inequalities and normalized logistic positivity.
- Math Kung Fu lesson sequence derived from the supported model structures.
- Avrea-backed GitHub Actions CI now observed completing successfully for commit `d2c786a7f2ad4b8dddbcca6316228ed7d23e439c`.

## Avrea execution evidence — 2026-11-04
- Workflow: CI, run ID `41837021534`, run number 1271.
- Runner job: `build-and-smoke`, completed with conclusion `success`.
- The step `Merlin equation-atlas symbolic, dimensional and numerical checks` completed successfully.
- The step `Publish equation-atlas reproducibility artifact` completed successfully.
- Artifact: `merlin-equation-atlas-baseline`, artifact ID `13325897559`, SHA-256 `b6711bf55a427eae7fa905e1c3fae0396c0ea5323ca04eb8c9ca3528ef5b168f`.
- The artifact was downloaded and inspected. It contains the deterministic JSON baseline for the five experiment families: optimization, least squares, heat FTCS, logistic RK4, and Fourier sampling.
- Other CI stages in the same successful job included C++ build/tests, deterministic research/API tests, engineering IR/persistence/CAD/coordinate-frame tests, CACE guardrails, Hermes/voice contracts, and independent smoke tests.

## Verification truth table
| Layer | Current state | What is not yet established |
|---|---|---|
| Source register | Added | Crosswalk entries flagged for specialist references are not source-complete; not every equation has an individually verified primary source |
| Units/dimensions | Starter checker executed successfully in Avrea CI | Only eight representative relations are executable; not all 100 entries |
| Symbolic | Starter checks executed successfully in Avrea CI | Not a proof of physical adequacy |
| Numerical | Deterministic scripts executed successfully in Avrea CI; output artifact archived | Synthetic baselines are not independent empirical validation; no broad convergence or uncertainty study yet |
| Lean | Candidate theorems and axiom audit source integrated | This CI run did not execute formal qualification; theorem candidates remain unverified until the pinned Lean workflow compiles them |
| XMG | Typed design contract and examples added | No interactive CAD/3D renderer or runtime integration has been executed |
| Learning | Lesson sequence added | Lessons need visual assets and adaptive learner testing |

## Evidence interpretation
The successful Avrea run establishes that the configured Python equation-atlas checks and baseline generation execute in the repository CI environment at the recorded revision. It does not establish empirical correctness of the models, universal dimensional correctness across the atlas, or Lean proof success. Keep each claim at its actual evidence level.

## Next completion gates
1. Close specialist-source gaps and attach claim-level citations to every equation and model assumption.
2. Normalize RWEA-021–100 with variable-level SI dimensions, coefficient dimensions, domain restrictions, initial/boundary conditions, and validity regimes.
3. Expand dimensional and symbolic tests from representative examples to all entries that admit executable checks.
4. Add numerical convergence, stability, sensitivity, uncertainty, and failure-regime sweeps; archive environment metadata and tolerances with each result.
5. Run the separate pinned Lean 4.34.0 / Mathlib v4.34.0 formal-qualification workflow; inspect logs and axiom output before promoting any theorem.
6. Add XMG serialization, transformation invariants, and generated multi-frame SVG/GLTF views, with coordinate-frame round-trip tests.
7. Add evidence receipts binding source snapshots, equation version, code commit, environment, tests, artifact hashes, and reviewer decisions.
8. Generate Math Kung Fu lessons only from entries meeting the declared evidence threshold; retain explicit uncertainty and counterexamples in lesson notes.

## Avrea / compute note
The existing self-hosted runner label is `avrea-ubuntu-latest-8-vcpu`. CI run 1271 confirms the configured equation-atlas checks and artifact publication completed on that runner. The formal-qualification workflow is separate and was not part of this CI run. Do not mark Lean candidates verified until that workflow's actual logs and theorem/axiom outputs have been inspected.
