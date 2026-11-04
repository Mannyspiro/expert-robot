# Merlin Equation Atlas — Research status v0.2

## Delivered to this branch
- Authoritative source register and an explicit equation-ID citation crosswalk.
- SI dimension algebra with eight representative homogeneity checks.
- Symbolic checks for constrained rectangle optimization, logistic equilibria, and least-squares gradient structure.
- Deterministic numerical baselines for constrained optimization, least squares, heat diffusion, logistic growth, and Fourier sampling.
- A normalized metadata tranche for entries RWEA-001 through RWEA-020.
- XMG typed multi-frame contract and examples.
- Lean theorem candidates for elementary inequalities and normalized logistic positivity.
- Math Kung Fu lessons generated from the supported model structures.

## Verification truth table
| Layer | Current state | What is not yet established |
|---|---|---|
| Source register | Added | Entries in the crosswalk marked as needing specialist references are not source-complete |
| Units/dimensions | Implemented starter checker | Only eight representative relations are currently executable; not all 100 entries |
| Symbolic | Implemented starter checks | Not a proof of physical adequacy |
| Numerical | Deterministic scripts and captured baseline values added | Remote CI execution and archived CI artifact have not yet been observed |
| Lean | Candidate theorems added | Not labelled FORMALLY_VERIFIED until pinned project toolchain compiles them |
| XMG | Typed design contract added | No interactive CAD/3D renderer or runtime integration has been executed |
| Learning | Lesson sequence added | Lessons need visual assets and adaptive learner testing |

## AVREA / compute note
The repository's existing GitHub Actions workflows use the self-hosted `avrea-ubuntu-latest-8-vcpu` runner. The equation-atlas Python test and artifact steps have been added to `.github/workflows/ci.yml`, and the Lean module is integrated into the existing `formal-qualification.yml` workflow, which also targets Avrea. The GitHub status query returned no check statuses at the time this note was written, so execution and successful completion are not yet confirmed. No Avrea run is claimed until workflow logs/artifacts are observed.

## Next completion gates
1. Add specialist primary sources for every crosswalk gap.
2. Normalize RWEA-021–100 with variable-level SI dimensions and assumptions.
3. Extend dimensional and symbolic tests to every supported entry.
4. Run Python tests and Lean proofs in the repository's pinned CI environment and attach logs/artifacts.
5. Add XMG serialization plus generated multi-frame SVG/GLTF views.
6. Generate lessons only after their supporting claims reach the declared evidence threshold.
