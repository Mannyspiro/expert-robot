# Inscribed chip patch — CACE P1 manufactured Poisson milestone

Updated 2026-10-10. Review branch `research/evidence-conservation-gates-20261009`.

**Target:** run the real pinned CACE `SimplexMeshND`, `P1SimplexSpaceND`,
`PoissonAssemblyND`, `LinearSolverND` and `AlgebraicResidualND`
on exactly the same synthetic geometry as an independently assembled P1
finite-element reference. It must produce a source-bound receipt and pass
a separately calculated residual and manufactured-solution error check.

Source: `scripts/experiment_cace_chip_p1_manufactured.py`
Regression: `tests/cace_chip_p1_manufactured_smoke.py`

## Why a circular test region inside a square chip?

The existing CACE P1 Poisson assembler's declared source parameter is
a scalar constant, so a manufactured solution satisfying *constant-source*
Poisson and homogeneous boundary values is a more honest first integration
than pretending to solve a spatially varying transistor PDE. The region is
an inscribed **100 micrometer radius disk in the 200 micrometer square** of
the earlier chip-sheet experiment, using triangles on polygonal approximations.

Normalize the radius to 1. The analytic reference is

    u(x,y) = 1 - x² - y²
    -Δu = 4
    u = 0 on the unit circle.

On a straight-edged polygon, that analytic solution vanishes at boundary
vertices, **not generally on boundary edges**. The geometric approximation
therefore contributes to the error; do not present the H1 numbers as
certified full-disk error bounds.

To restore physical dimensional scaling for radius R, write
`x_physical = R*x_normalized`. Physical forcing carries
a factor `1/R²` (and conductivity/material coefficients as appropriate).
This does **not** supply calibrated semiconductor materials or a foundry PDK.

## Independent numerical benchmark

A separate Python P1 assembler builds triangle stiffness
`Aᵢⱼ = Σ_K |K| ∇φᵢ·∇φⱼ` and source load
`bᵢ = Σ_K 4|K|/3`, applies zero Dirichlet conditions,
and solves the reduced system with partial-pivot elimination.

The manufactured nodal maximum error and H1 seminorm error are computed
independently of CACE's reported algebraic residual. The H1 integral
uses *exact polynomial moments on each triangle*, but the triangle
coordinates and linear solve use floating-point numbers. Thus the reported
error is a numerical estimate, not an interval enclosure.

| Angular segments | Radial rings | Vertices | Triangles | Nodal max error | H1 error |
|---:|---:|---:|---:|---:|---:|
| 8 | 2 | 17 | 24 | 0.0861251 | 0.6745169 |
| 16 | 4 | 65 | 112 | 0.0221303 | 0.3699874 |
| 32 | 8 | 257 | 480 | 0.0057367 | 0.1895372 |

All three local independent reference cases passed with free-node residuals
at floating-point roundoff. Errors decrease under this bounded refinement,
but monotonicity on three meshes is not a general convergence theorem.
The result changes with domain geometry, mesh design and assumptions.

## Pin and CACE execution requirements

The optional `--cace-repo` path requires exactly the
`config/cace_fem_nd_contract_pin.json` Git commit:
`0e7aa229d3bb57174e281b883ee8af5445f15f75`.
It checks Git HEAD and the committed FEM-ND source bytes, imports and
calls the **actual CACE five-module chain**, and requires:

- a typed full-node vector with finite numbers, zero boundary;
- CACE solver output within 1e-7 of independent P1 nodal values;
- actual CACE algebraic residual ≤ 1e-7;
- separately reconstructed algebraic residual of the CACE vector ≤ 1e-7;
- independent manufactured-solution nodal/H1 error and refinement trend.

Unexpected result layouts, module failures, missing pins, and mismatches
**fail closed**, rather than substituting a stand-in CACE implementation.
The related read-only Avrea workflow checks its half-month budget **before**
accessing the existing CACE deploy key and retains evidence. Actual CACE
execution is **pending** until a successful, independently inspected CI run;
standalone tests cannot assert it already happened.

## Important limits and next technical advance

No calibrated silicon material data, oxide contacts, dopants, electron/hole
drift diffusion, recombination, semiconductor statistics, time-dependent
thermal coupling, verified geometry regularity, interval bounds, Lean
kernel proof, or manufacturing/process validation. A P1 Poisson test alone
does not make this a production TCAD simulator or qualify RSI promotion.

Once the genuine pinned CACE P1 execution passes, the next meaningful step
is variable-coefficient diffusion and *nonconstant manufactured forcing*
on the **full square chip** with physically named contacts; then independent
residual-based and a-posteriori certified error bounds. Keep distinct:
algebraic solver residual versus continuum discretization error.

