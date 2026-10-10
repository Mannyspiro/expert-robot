# Full-square chip continuum milestone: variable-coefficient Poisson

Date: 2026-10-10 · Branch: research/evidence-conservation-gates-20261009

## Implemented numerical reference

- `scripts/experiment_cace_chip_square_material_p1.py` — stand-alone P1 FEM
  for a normalized **full square** representing a 200 μm × 200 μm synthetic
  chip region; *not* a semiconductor device simulation
- `tests/cace_chip_square_material_p1_smoke.py` — deterministic
  regression, boundary, symmetry, analytic-energy, independent
  finite-difference derivative and adversarial-mutant checks

Manufactured fields (unit-square coordinates):

\[
u(x,y)=x(1-x)y(1-y),\quad k(x,y)=1+x
\]
\[
-\nabla\cdot(k\nabla u)=f,\quad
f=2(1+x)[x(1-x)+y(1-y)]-(1-2x)y(1-y),
\qquad u|_{\partial\Omega}=0.
\]

The material coefficient is **dimensionless and synthetic**; physical
length scaling, carrier mobility, temperature dependence, dopants, contacts,
oxide, semiconductor statistics and foundry PDK data have NOT been applied.

Independent analytical checks:

- \(\int_\Omega f\,dxdy = 1\) exactly.
- \(\int_\Omega k|\nabla u|^2\,dxdy=1/30\) exactly.
- P1 triangle stiffness integrates the affine \(k\) exactly by triangle
  centroid evaluation; the load and energy-error integrals use a fixed
  5×5 tensor Gauss rule via a Duffy triangle transform.
- Full mesh stiffness is symmetric with zero row sums prior to imposing
  homogeneous Dirichlet boundary values.
- The reduced linear solver uses independent Gaussian elimination.
  Results are ordinary floating-point approximations, **not interval bounds**.

### Offline observed results

| P1 grid | Triangles | Interior DOFs | Max nodal error | H¹ energy-seminorm error |
|---:|---:|---:|---:|---:|
| 5×5 | 32 | 9 | 0.00291102748 | 0.07197772465 |
| 9×9 | 128 | 49 | 0.00075184785 | 0.03693796130 |
| 13×13 | 288 | 121 | 0.00033847496 | 0.02474686555 |

Local standalone tests passed using Python 3.13, without GitHub Actions or
CACE module imports. Numerical residuals of assembled equations were at
floating-point roundoff; exact symbolic analytical energy was independently
checked by numerical quadrature. These observations show a **bounded trend**
on three meshes; they do not prove a general error estimate or a physical
silicon performance prediction.

Mutations rejected: invalid/negative materials, missing conductivity-gradient
term in forcing, invalid polynomial forcing, inverted/degenerate triangles,
singular linear systems and unsupported mesh sizes. The test also compares
analytic \(-\nabla\cdot(k\nabla u)\) with a separate central-difference
calculation at three nontrivial interior points.

## Exact CACE integration blocker and qualification contract

Pinned CACE checkout in
`config/cace_fem_nd_contract_pin.json`:
`0e7aa229d3bb57174e281b883ee8af5445f15f75`.

The existing `PoissonAssemblyND` contract exposes a scalar
`source` parameter. This is NOT sufficient to represent both
\(k(x,y)=1+x\) and the nonconstant manufactured \(f\). Therefore the new
reference deliberately declares:

- `actual_cace_variable_coefficient_assembly_executed=false`
- `actual_cace_pde_solver_executed=false`
- `cace_continuum_bound_certified=false`
- `lean_kernel_checked=false`
- `rsi_promotion_authorized=false`

**Proposed, not implemented in CACE:** a narrowly scoped
`VariableCoefficientPoissonAssembly2D` module whose typed
inputs are the same pinned P1 mesh/space, plus an explicitly validated
affine-positive conductivity (coefficients [1,1,0]) and a structured
polynomial forcing definition. Require units and positivity on the full
domain, zero-Dirichlet enforcement, and a signed source/parameter hash.
Compare its stiffness/load and nodal solution against this reference
independently before attaching a residual, estimator or continuum
certificate. Do not change CACE API/module qualification visibility
before actual capability registry validation.

The **existing** CACE P1 manufactured disk probe can validate the constant-
coefficient Poisson path when Avrea/OCI budget gates and the exact CACE
checkout succeed. The variable-material square case MUST NOT be mislabeled
as a successful CACE run just because its stand-alone reference passed.

## Runner incident and compute accounting

CACE integration GitHub run #38053859438 attempt 2 acquired an Avrea
runner but was cancelled during the historical Avrea budget scan, after
roughly ten minutes; no physics modules or deploy keys executed.

To prevent long scans from wasting the allowed free runtime, the budget
script now uses a 75-second fail-closed deadline, a bounded 6-worker GitHub
metadata page-fetch pool, completeness/duplicate-ID checks, and more
complete workflow accounting. It **does not** bypass budget limits when
history is missing. The standalone budget regression was added under
`tests/avrea_usage_pagination_smoke.py`. A successful,
source-bound remote budget/test run remains pending and must be inspected
separately. These API changes do not certify or independently reconcile
provider-wide Avrea balance.

No paid deployment, hardware manufacturing, Cloudflare, Fjord or automatic
RSI promotion is part of this milestone.
