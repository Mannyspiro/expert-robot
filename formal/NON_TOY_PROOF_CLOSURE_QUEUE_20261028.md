# Non-toy proof-closure queue — 2026-10-28

## Governing rule

No toy equations, random synthetic data, or generic algebra facts count as physical proof closure. Every result must identify the physical model, equations, conventions, source dataset, reproducible command, and independent acceptance criterion. No training/benchmark runs are authorized. Do not change `main`.

## Finding that controls the whole programme

The current repository evidence does **not** specify one candidate unified field theory. It does not pin a single action, complete field content, gauge group, symmetry-breaking pattern, quantization/regularization prescription, or theorem connecting the gravity, gauge, matter, and cosmological sectors. Therefore a global unified-field proof cannot honestly be closed yet. The first global blocker is theory specification, not compute.

## Ordered queue

### P0 — Freeze the candidate theory before further physics computation

Create a versioned specification with:
- action or axioms, field representations, spacetime/signature/conventions;
- gauge group and transformations; constraints and gauge fixing, if any;
- classical equations and boundary/initial conditions;
- quantization and regulator/scheme; renormalization conditions;
- map from each claimed sector to observables and established limiting theories;
- exact theorem statements, assumptions, and falsifiers for each claimed connection.

Acceptance: an independent reader can derive the equations without guessing any missing conventions. Until this exists, do not label a result “the unified theory's prediction.”

### P1 — Lattice SU(2) paper: reproduce the actual gauge-invariant link-cut result

Primary source: Ebner et al., Phys. Rev. D 110, 014505 (2024), DOI 10.1103/PhysRevD.110.014505; corrected published version at https://epub.uni-regensburg.de/74880/1/PhysRevD.110.014505.pdf.

The paper defines the Kogut–Susskind Hamiltonian (Eq. 1), the j_max=1/2 Ising-limit Hamiltonian (Eq. 2), and a gauge-invariant cut through links. Its Eq. 9 establishes equality of all integer Rényi traces for the two reduced density matrices; finite-dimensionality then gives equal spectra and equal entanglement entropy (PDF pp. 2–3, lines 187–216 in the parsed source).

Required next work:
1. Implement the *link-cut electric-basis reduced density matrix* from Eqs. 4–9, including dangling-link labels and Gauss-law constraints. Do not substitute a plain tensor-product spin-site cut.
2. Verify gauge invariance under the paper's time-independent vertex gauge transformations and verify the analytic Rényi-trace identity for the constructed physical states.
3. Reproduce at least one published point and then a full published subsystem-size curve using the paper's exact basis, boundary conditions, coupling, symmetry sector, and energy labels. The paper's periodic N=17, j_max=1/2 result is in the k=0 sector; the main-text discussion uses g^2 a=1.2 for the Page curve, while Appendix B uses g^2 a=1.6 for level statistics/scars. Do not mix those configurations.
4. Add j_max>1/2 as a separate basis with correct SU(2) recoupling/Wigner-6j matrix elements; do not extrapolate the Ising mapping to it.
5. Record numerical tolerances, basis dimensions, eigenpair residuals, gauge-constraint leakage, entropy convention (nats), and source-to-result comparison.

Acceptance: a source-pinned reproducibility report with matched published data and independent checks of gauge invariance. This is a lattice-gauge result, not by itself a unified-field proof or a black-hole evaporation result.

### P2 — FRG: reproduce the actual published scalar-field flow before applying it to the candidate theory

Primary method source: Zorbach, Stoll, Braun, Phys. Rev. D 111, 096022 (2025), DOI 10.1103/PhysRevD.111.096022.

Required:
1. Transcribe the paper's LPA flow equation, threshold functions, regulator families and constraints, initial potential, dimension, field normalization, and infrared stopping criterion from the published equations.
2. Reproduce a published regulator comparison and flow-breakdown/stability result with convergence under grid/time-step refinement.
3. Preserve the paper's regulator-specific conventions and test the conditions on the regulator explicitly.
4. Only after reproducing the published scalar result, derive the FRG truncation from the frozen candidate action in P0. Report truncation error and regulator dependence; do not transfer scalar-LPA conclusions directly to gravity or the Standard Model.

Acceptance: numerical results match a source-defined figure/table within a predeclared tolerance and are stable under refinement. The previous scalar beta-function example is excluded from evidence.

### P3 — Standard-Model-shifted fixed point

Blocked until P0 pins the action and P2-level methodology pins the RG scheme. Then derive the coupled beta functions from that action, pin thresholds and Standard Model inputs with uncertainties, state dimensionless coupling definitions and stability-matrix sign convention, solve the actual coupled system, and report regulator/truncation sensitivity. A generic root-existence theorem is not evidence for a physical fixed point.

Acceptance: the fixed point is a root of the specified coupled beta functions, has a reported stability spectrum, and survives documented scheme/truncation robustness checks.

### P4 — Planck PR3 cosmology

Official archive index: https://irsa.ipac.caltech.edu/data/Planck/release_3/ancillary-data/cosmoparams/
The baseline chain archive is listed as `COM_CosmoParams_base-plikHM-TTTEEE-lowl-lowE_R3.00.zip` (~62 MB). The current execution environment failed to download the archive; no local chain analysis or checksum is claimed.

Required:
1. Retrieve the exact archive from the official source; record URL, byte size, SHA-256, archive inventory, parameter columns, and chain weights.
2. Recompute weighted posterior summaries from the *existing* chains and compare to the official parameter table; compute ESS and chain diagnostics where the chain format permits.
3. Do not launch a new likelihood/MCMC run until the exact candidate cosmology, likelihood, priors, nuisance parameters, and sampler configuration are pinned.
4. Treat this as observational baseline validation, not evidence for unification unless P0 makes a discriminating prediction that can be tested against the likelihood.

Acceptance: checksum-verified data, a reproducible post-processing command, and summary/diagnostic agreement with the official release.

## Formal proof obligations (not yet closed)

- A Lean theorem for the exact finite-dimensional Schmidt/Rényi-trace argument used by the gauge-invariant cut, with assumptions made explicit. This theorem must not claim the physical SU(2) basis construction until that construction is formalized.
- A formally specified bridge from the candidate action to the actual FRG beta functions and fixed-point equations.
- Theorems establishing the proposed sector maps/limits and their compatibility, including anomaly/constraint consistency where applicable.
- A final theorem can only be stated after the preceding definitions exist. No placeholder theorem, axiom, `sorry`, or `admit` counts as proof.

## Current status and stop conditions

- The prior small-N Ising-spin calculation is implementation testing only and is not accepted as physical reproduction.
- The generic affine-root Lean theorem is excluded from physical proof evidence.
- The Planck archive was not retrieved in the current environment.
- The CACE external runner timed out without a returned execution record; no external regression pass is claimed.
- No new training or benchmark run was started; `main` remains unchanged.
- The global proof remains blocked at P0 until a single candidate theory and explicit sector-connection claims are pinned.
