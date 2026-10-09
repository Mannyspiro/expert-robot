# Modeler-derived beam benchmark

`evaluate_research_object_beam.py` selects the modeler's single-edge
`complete_graph` candidate and models its circular centerline as a clamped-free
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
authority or continuum error certificate. Next qualification work must address
independent holdouts, model assumptions and certified error bounds before any
design qualification.

```sh
python3 tests/research_object_beam_smoke.py
python3 scripts/evaluate_research_object_beam.py config/examples/research_object_beam.json -o /tmp/beam-report.json
python3 scripts/run_cace_beam_benchmark.py /path/to/pinned/cace-app config/examples/research_object_beam.json -o /tmp/cace-beam-report.json
```
