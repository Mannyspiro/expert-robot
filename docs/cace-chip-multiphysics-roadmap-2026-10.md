# CACE chip simulation: model → physics → certificate

Date: 2026-10-10. **Research-stage, not fab-qualified or transistor TCAD.**

## Implemented first bridge

Files: scripts/experiment_cace_chip_electrothermal.py and tests/cace_chip_electrothermal_smoke.py. The existing .github/workflows/cace-biochemical-diffusion.yml is now wired to run the toy experiment, then validate both matrices through the **actual pinned CACE FEM CSR codec** using the existing read-only Cace-app deploy key, if the Avrea free-budget gate passes.

**Model:** 3 × 3 in-plane nodes, 12 resistive edges, 100 µm node spacing, 1 µm effective conductive film, and 100 µm effective thermal substrate thickness. The center region is less conductive than the surrounding film. Fixed 0.1 V at the left, 0 V at the right. Thermal coupling uses k=130 W/(m K) and a *hypothetical* lumped 0.001 W/K per-node heat sink. These are intentionally **illustrative/unvalidated material and thermal-boundary assumptions**, not claims about a fabricated silicon chip.

Exact rational finite-network equations:

- Electrical: sum over neighbors g_ij (V_i - V_j) = 0 for interior nodes; conductance g_ij = sigma_harmonic × film_thickness × width/edge_length.
- Joule power: P_ij = g_ij (V_i - V_j)^2, half assigned to each endpoint.
- Heat: sum k_ij (theta_i - theta_j) + h_i theta_i = Q_i.
- Consistency: sum node current = 0, P_total = applied_voltage × source_current, and sum h_i theta_i = P_total.

A standalone local exact-arithmetic prototype produced total power **7/6000 W (~1.17 mW)**, a ~0.132 K maximum rise over ambient, and balanced total generated/dissipated heat under these chosen boundary conditions. No physical measurements. The committed script tests conservation and deliberately perturbs a trace and conductivity to ensure the old solution fails validation.

**Critical limits:** this is a finite-volume-like lumped network, not actual 2D/3D FEM Poisson assembly, semiconductor carrier physics, calibrated thermal packaging, process-corner simulation, or a CACE certificate. The pinned CACE repository's _csr_from_dense/_dense_from_csr adapter verifies sparse representation only. The CACE live workflow has not yet passed; do not claim the actual CACE codec ran in this turn.

## Roadmap (ranked)

| Tier | Physics/model | Independent acceptance conditions |
|---|---|---|
| 0 | Exact network electrothermal toy + CACE sparse representation | KCL, power, local thermal residuals, mutation controls, exact source pin |
| 1 | Heterogeneous 2D/3D conductor and heat equation on actual CACE SimplexMeshND | Manufactured solution, material interface flux, mesh refinement, independent residual/error/interval checks |
| 2 | Time-varying temperature, Joule heat, contact and interface resistance | Energy balance per step, stability and time-step convergence |
| 3 | Doped semiconductor Poisson + electron/hole drift–diffusion + recombination | Calibrated material/boundary assumptions, PN diode reference, charge/continuity residuals |
| 4 | Parasitic RC, metal interconnect fields, Maxwell where relevant | Independent field/charge conservation and SPICE comparisons |
| 5 | Timing and switching/power versus geometry | Frozen circuits, independent ngspice timing/energy benchmarks |
| 6 | Fabrication constraints: PDK layers, DRC/LVS, statistical process variation | Pinned PDK, test structures, actual foundry signoff and silicon data |

A Poisson solver alone does not provide a semiconductor transistor solver. Nanometer device quantum effects require additional physics beyond classical drift–diffusion.

## Math for CACE to prove

1. Under positive edge conductance, B diag(g) Bᵀ is symmetric positive semidefinite; its kernel contains constants and consists of component-wise constants.
2. Grounding at least one node per connected component gives a positive-definite reduced operator.
3. Interior edge currents cancel in the global charge balance. Dissipated electrical power equals boundary-work input.
4. Internal thermal flux cancels; the ambient sink exactly removes total heat in steady state.
5. Sensitivity bounds on conductivity, geometry and thermal interfaces should be carried into interval/a-posteriori certificates, not inferred from finite toy examples.

These are **unproved Lean obligations** until exact pinned kernel replay. An optimization is only eligible for RSI after physical applicability, formal/numerical qualification, independent benchmarks, rollback, and authority nonexpansion.

## Deployment governance

The proposed CACE workflow is read-only, checks Avrea free usage before key access, pins the Cace-app source revision, and emits evidence artifacts only. It neither modifies production CACE nor authorizes automatic RSI promotion. This step depends on available free runners; no live run success has been established.
