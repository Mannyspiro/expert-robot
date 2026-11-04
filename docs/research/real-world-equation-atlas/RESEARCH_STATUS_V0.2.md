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
- Avrea-backed CI completed successfully for the initial implementation and again for the canonical schema/receipt implementation (latest successful run #1289).

## Avrea execution evidence — 2026-11-04
- Initial baseline workflow: CI run #1271, run ID `41837021534`, commit `d2c786a7f2ad4b8dddbcca6316228ed7d23e439c`; full job completed successfully.
- Canonical migration and receipt workflow: CI run #1289, run ID `41838851056`, commit `e876f003c2762c69a4e964db83e56fe27be7a087`; full `build-and-smoke` job completed with conclusion `success`.
- The equation-atlas check step passed, including canonical migration, JSON Schema validation, dimensional checks, symbolic checks, deterministic numerical baseline generation, evidence-receipt generation, and the associated unit tests.
- The artifact publication step passed. Artifact: `merlin-equation-atlas-baseline`, artifact ID `13328235231`, ZIP SHA-256 `03c811b6d1af905bd0a6dd2605ce4055b71eec2f04e538542cca19b87aae42fb`.
- The downloaded artifact was inspected. It contains `equation-atlas-baseline.json`, `equation-atlas-normalized-entries-001-020.json`, and `equation-atlas-evidence-receipt.json`.
- The canonical output contains 20 entries, RWEA-001 through RWEA-020; every migrated entry is deliberately marked `UNVERIFIED`.
- The receipt records nine source-file hashes, the exact baseline artifact SHA-256 `6dd37180bc8ea1a20dfbb94b806d56aef202eb24512043f34224c086f8575a2a`, byte count, Python 3.12.3, Avrea Linux platform, and the checked-out pull-request merge commit.
- The full run also passed C++ build/tests, research/API contracts, engineering IR/persistence/CAD/coordinate-frame tests, CACE guardrails, Collar guardrails, Hermes/voice contracts, and independent smoke tests.
- Formal qualification remains a separate workflow and was not executed by CI run #1289.

## Verification truth table
| Layer | Current state | What is not yet established |
|---|---|---|
| Source register | Added | Crosswalk entries flagged for specialist references are not source-complete; not every equation has an individually verified primary source |
| Units/dimensions | Starter checker executed successfully in Avrea CI | Only eight representative relations are executable; not all 100 entries |
| Symbolic | Starter checks executed successfully in Avrea CI | Not a proof of physical adequacy |
| Numerical | Deterministic scripts executed successfully in Avrea CI; output artifact archived | Synthetic baselines are not independent empirical validation; no broad convergence or uncertainty study yet |
| Canonical schema | 20/20 legacy entries migrated and schema-validated in Avrea CI; 021–030 batch authored and queued for validation | Combined 001–030 Avrea run pending; 031–100 not yet normalized | 
| Evidence receipts | Receipt schema validated; content-addressed receipt generated and inspected in Avrea CI | Test-output digest, container image digest, and reviewer signature remain future extensions | 
| Lean | Candidate theorems and axiom audit source integrated | CI run #1289 did not execute formal qualification; theorem candidates remain unverified until the pinned Lean workflow compiles them |
| XMG | Typed design contract and examples added | No interactive CAD/3D renderer or runtime integration has been executed |
| Learning | Lesson sequence added | Lessons need visual assets and adaptive learner testing |

## Evidence interpretation
The successful Avrea run establishes that the configured Python equation-atlas checks and baseline generation execute in the repository CI environment at the recorded revision. It does not establish empirical correctness of the models, universal dimensional correctness across the atlas, or Lean proof success. Keep each claim at its actual evidence level.

## Next completion gates
1. Close specialist-source gaps and attach claim-level citations to every equation and model assumption.
2. Complete Avrea validation of RWEA-001–030, then normalize RWEA-031–100 with variable-level SI dimensions, coefficient dimensions, domain restrictions, initial/boundary conditions, and validity regimes.
3. Expand dimensional and symbolic tests from representative examples to all entries that admit executable checks.
4. Add numerical convergence, stability, sensitivity, uncertainty, and failure-regime sweeps; archive environment metadata and tolerances with each result.
5. Run the separate pinned Lean 4.34.0 / Mathlib v4.34.0 formal-qualification workflow; inspect logs and axiom output before promoting any theorem.
6. Add XMG serialization, transformation invariants, and generated multi-frame SVG/GLTF views, with coordinate-frame round-trip tests.
7. Extend evidence receipts with test-output digest, container image digest, per-entry experiment mapping, and reviewer decisions.
8. Generate Math Kung Fu lessons only from entries meeting the declared evidence threshold; retain explicit uncertainty and counterexamples in lesson notes.

## Avrea / compute note
The existing self-hosted runner label is `avrea-ubuntu-latest-8-vcpu`. CI run 1289 confirms the canonical migration for RWEA-001–020, receipt generation, equation-atlas checks, and artifact publication completed on that runner. The combined RWEA-001–030 validation is pending in the latest workflow run. The formal-qualification workflow is separate and was not part of this CI run. Do not mark Lean candidates verified until that workflow's actual logs and theorem/axiom outputs have been inspected.
