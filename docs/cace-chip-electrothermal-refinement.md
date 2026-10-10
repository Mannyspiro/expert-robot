# Exact chip-sheet electrothermal refinement (prototype)

Implementation: `scripts/experiment_cace_chip_refinement.py`.
Regression: `tests/cace_chip_refinement_smoke.py`.
Research branch: `research/evidence-conservation-gates-20261009`.

## Physical model and dimensions

A **synthetic** 200 μm × 200 μm conductive film, 1 μm thick, is
electrically contacted at 0.1 V on the left and 0 V on the right.
The substrate is represented as a **lumped** thermal sheet (effective
thickness 100 μm) and a vertical ambient heat-transfer sink, not a
calibrated 3D stack. Toy material properties: electrical conductivity
100,000 S/m, thermal conductivity 130 W/(m K), sink 225,000 W/(m² K).
One optional central 50 μm square has 1/5 the base film conductivity.

The bounded nodal finite-volume grids are 3×3, 5×5 and 7×7, all over
the **same physical dimensions**. Border control volumes have half/quarter
areas; edge conductances use harmonic-average conductivity and
face-width/distance weights.

- Electrical: discrete divergence of σ∇V = 0 at free nodes;
  fixed left/right contact potentials.
- Power: each edge produces g_e (Vᵤ−Vᵥ)² W and shares it equally
  between its endpoints; Σ power = contact voltage × current.
- Thermal rise θ = T−T_ambient: (graph conduction + ambient sink) θ
  equals nodal Joule heat in steady state.
- All arithmetic uses standard-library exact rational
  `fractions.Fraction` (no float tolerance in conservation tests).

## Locally executed checks

- Six grid/material cases; all nodal electrical KCL and thermal
  residual checks hold **exactly**.
- Analytic reference for a uniform sheet: V(x)=0.1(1−x/L) V and
  P=σ t (0.1)² = **0.001 W** on all three grids.
- Total current is **0.01 A**, and the idealized maximum thermal
  rise is **1/9 K** for this uniform toy under the stated sink.
- With the synthetic conductivity defect, total power is smaller:
  3×3: 1/1500 W; 5×5: 13/14500 W; 7×7: 1399/1469000 W.
  These *different coarse-graining results are not yet a mesh
  convergence theorem*. The defect is represented differently at
  each resolution; convergence must be evaluated separately.
- Open-trace mutation and malformed or disconnected passive networks
  are rejected/detected; every tested output is deterministic.

The optional `--cace-repo` mode checks *only* CSR
encode/decode fidelity against the exact pinned checkout declared in
`config/cace_fem_nd_contract_pin.json`. The existing
budget-gated Avrea workflow fetches CACE with its GitHub Actions secret,
runs the physics check **before key use**, and saves refined operator
evidence when actual CACE integration succeeds.

**Explicit limits:** no physical silicon calibration, CMOS transistor or
carrier drift/diffusion, doping profiles, quantum confinement, thermal
transients, real package/PDK, fabrication, thermal boundary validation,
Lean kernel proof, CACE FEM/PDE solve or certified continuum error bound.
A successful CSR round-trip is NOT a CACE solver qualification, and
nothing here authorizes RSI promotion. No paid compute required for the
standalone model.

## Next frontier toward actual chip TCAD

1. Separate validated material database with units, parameter ranges
   and provenance; no guessed semiconductor constants.
2. Pass the 2D geometry to the **actual pinned CACE mesh/P1 assembly**
   and compare independently assembled continuum operators.
3. Add calibrated contacts and electrostatic Poisson equation for
   dielectric and doped-semiconductor regions, then continuity equations
   for carriers with boundary-specific current and charge checks.
4. Add temperature-dependent conductivity and iterative electrothermal
   coupling, with existence/convergence and positivity gates.
5. Mesh-refine a manufactured solution with independent error norms,
   interval and a-posteriori certificates; only then contemplate 3D.

This prototype is one rigorous foothold, not a physically qualified chip
simulator.
