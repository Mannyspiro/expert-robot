# Modeler-derived beam benchmark

`evaluate_research_object_beam.py` selects the modeler's single-edge
`complete_graph` candidate and models its straight centerline with a circular cross-section as a clamped-free
Euler–Bernoulli beam. The illustrative fixture is 1 m long, 20 mm in diameter,
with E = 200 GPa and a local transverse distributed load of -1 N/m.
The root clamp and free tip are benchmark assumptions, not inferred mounting
conditions. A rotated XY centerline uses the same local load convention.

The solver uses cubic Hermite bending elements and consistent distributed loads.
An independent closed-form cantilever field checks tip motion, support force and
moment, and interior displacement and curvature. The five-point quadrature
integrates squared field errors. Meshes of 1, 2, 4, 8 and 16 elements must reduce
displacement L2 error by approximately 16 and curvature L2 error by approximately
4 on each doubling. Tip-only agreement is insufficient: the tip can be exact
on the first mesh while the interior field still has error.

The Hermite formulation follows the [TU Delft Euler–Bernoulli derivation](https://teachbooks.tudelft.nl/computational-modelling/structural_linear/euler_bernouilli.html).
Regression checks also use independent tip-force and tip-moment formulas,
support equilibrium, rotation invariance and invalid-input rejection.

The bounded experiment accepts 3–6 doubling meshes, at most 32 elements,
L/d >= 10, finite material/load inputs and named material provenance. It rejects
responses exceeding 1% of span or 0.05 rad rotation. These limits define the
benchmark envelope; they do not establish the accuracy of a real beam model.
Curvature-derived stress is an FE approximation and is reported separately
from the analytic root stress. Material provenance is illustrative.

The modeler workflow retains the report for 30 days with the input digest,
topology digest, source head, execution SHA and producer run. The result has
no promotion authority. It is neither a CACE continuum certificate nor a
manufacturing qualification. Shear deformation, axial behavior, buckling,
joints and 3D solid stresses are outside this experiment.

`run_cace_beam_benchmark.py` reuses the actual pinned CACE `LinearSolverND` and
`AlgebraicResidualND` modules with an explicit reduced beam-system adapter.
It checks the source pin and module digest, round-trips the CSR encoding through
CACE's decoder, checks clamp reconstruction, requires both CACE verification
records to pass, and compares every solve with the independent stdlib backend.
The existing Poisson assembly, estimator and continuum gates are not used for
the beam. Both the analytic fields and convergence checks run on the actual
CACE solution. Rotations are scaled to length times angle; equations then have
consistent force units. A common scalar normalization keeps CACE's absolute
algebraic residual tolerance well-scaled. The original beam equations also
receive an independent normalized residual check.

The existing CACE integration workflow retains the beam report and bounded
source-contract inspection for 30 days. Its results still have no promotion
authority or continuum error certificate.

## Prespecified coverage and exact discrete solver-error witnesses

The integration also runs six fixed cases with 18 additional solves: positive
and negative distributed loads, a tip force, a tip moment, mixed-sign loads,
and a zero-load control. They vary synthetic Young's modulus, span, diameter
and XY orientation. Every centerline passes through the modeler geometry gate.
Distributed-load cases check interior convergence; cubic/zero cases check field
agreement. The report retains the case parameters and manifest SHA256. These
are public, prespecified regression holdouts from the original baseline, not
a statistically blind study or measured-material validation.

Every CACE solve now receives an exact rational certificate for its original
stored binary64 beam matrix, right-hand side and returned solution. The
producer factors the stored matrix as L D L^T and solves for the exact
correction delta. A separate checker reconstructs the entire matrix from that
witness, checks positive diagonal entries, checks A delta = b - A u, and
checks the squared energy error delta^T A delta. It never calls the factorizer
or a linear solver. This proves the correction to the exact solution of that
stored SPD system. Tests include a system whose tiny residual hides an error
of one unit, plus tampered corrections, factors, endpoints and digests.

Residual, maximum scaled DOF error and energy-norm upper endpoints are binary64
numbers checked with exact rational inequalities. Square-root enclosure uses
power-of-two scaling to handle underflow and overflow; `nextafter` only chooses
a candidate endpoint, and exact arithmetic decides whether it encloses the
bound. The certificate includes the exact witnesses and a SHA256 binding to
the matrix, load and solution. The artifact also embeds those inputs as
canonical binary64 hex strings. A standalone replay reads the saved report,
checks every witness without factoring or solving, and retains its own report
digest and source/run binding. Work is bounded to 32 free DOFs, 8192-bit
rationals and a 1 MiB certificate. Baseline meshes and coverage meshes stay
inside this bound.

This certificate covers algebraic solver error relative to the stored matrix.
It excludes coefficient/assembly rounding, continuum discretization error,
material uncertainty, buckling, shear and manufacturing. Its checker is Python
exact arithmetic, not a new Lean theorem. Next qualification work is a beam
continuum error theorem and measured-model applicability before design
qualification. [Python's Fraction documentation](https://docs.python.org/3/library/fractions.html)
describes exact float conversion; [Stanford's factorization notes](https://ee263.stanford.edu/lectures/cholesky.pdf)
describe positive-definite factorization.

```sh
python3 tests/research_object_beam_smoke.py
python3 scripts/evaluate_research_object_beam.py config/examples/research_object_beam.json -o /tmp/beam-report.json
python3 scripts/run_cace_beam_benchmark.py /path/to/pinned/cace-app config/examples/research_object_beam.json -o /tmp/cace-beam-report.json
```
