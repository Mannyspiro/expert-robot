# Literature target triage — 2026-10-28

This file records source-level target selection. It does not claim a completed reproduction.

## Lattice Page curve: concrete candidate selected

**Primary source:** Ebner, Schäfer, Seidl, Müller, and Yao, “Entanglement entropy of (2+1)-dimensional SU(2) lattice gauge theory on plaquette chains,” *Physical Review D* 110, 014505 (2024), DOI [10.1103/PhysRevD.110.014505](https://doi.org/10.1103/PhysRevD.110.014505). An accessible author/institution-hosted PDF is available at https://epub.uni-regensburg.de/74880/1/PhysRevD.110.014505.pdf.

The paper's abstract states that ground- and excited-state entropies follow Page curves; it defines entropy as S_A = -Tr(rho_A ln rho_A), uses a link-cutting partition compatible with local gauge symmetry, and reports exact diagonalization for a finite electric-flux-truncated Hilbert space. In the Ising-limit mapping, the paper gives a periodic-chain Hamiltonian in Eq. (2), with dimensionless coupling terms parameterized by g and a.

**Decisive implementation sequence**
1. Transcribe Eq. (2), the definition of its site-dependent coefficient, and the chosen truncation directly from the PDF (not text extraction alone); preserve a source note with equation/page numbers.
2. Start with the Ising-limit periodic chain and the smallest size with a nontrivial bipartition; choose and label a dimensionless parameter point explicitly as a reproduction setting, not a phenomenological estimate.
3. Build the Hamiltonian matrix and verify Hermiticity, periodic boundary indexing, eigenvalue residuals, and normalization.
4. For each eigenstate, compute the reduced density matrix using the paper's specified partition convention; verify trace one, positivity within numerical tolerance, entropy nonnegativity, and S(A)=S(complement) for pure states.
5. Compare the subsystem-size trend and fitted crossover against the published plot/equation. Record truncation, Hilbert dimension, all parameters, code revision, and numerical tolerance.
6. Only then extend to higher electric-flux truncation. The paper reports that scar-like low-entanglement excited states in the Ising-limit truncation disappear when higher representations are included; reproducing the truncated model alone must not be generalized to the full SU(2) theory.

**Current status:** source target selected; actual lattice Hamiltonian reproduction not yet executed. The eight-qubit Haar formula remains a separate sanity benchmark only.

## FRG numerical confirmation: concrete methodology target selected

**Primary methodology source:** Zorbach, Stoll, and Braun, “Optimization and stabilization of functional renormalization group flows,” *Physical Review D* 111, 096022 (2025), DOI [10.1103/PhysRevD.111.096022](https://doi.org/10.1103/PhysRevD.111.096022).

The paper studies the Wetterich equation and a scalar-field theory in the local-potential approximation; it compares regulator-dependent flow stability and documents its numerical setup, including an LSODA-based solver. It is suitable as a numerical-method reproduction target, but it is not automatically the user's intended physical beta function.

**Decisive implementation sequence**
1. Extract the paper's flow equation, regulator definitions and normalization, initial potential, dimension, grid, and solver tolerances from the PDF.
2. Reimplement one specified regulator case with independent code, matching the published dimensionless setup.
3. Check convergence under tighter tolerances/grid resolution and compare the reported breakdown/stability ordering across at least two regulator choices.
4. Keep the original target physics distinct from the scalar LPA method test.

**Current status:** methodology target selected; equation transcription and independent reproduction pending.

## Cosmological MCMC: public baseline target selected

The NASA/IPAC IRSA Planck PR3 archive lists `COM_CosmoParams_base-plikHM-TTTEEE-lowl-lowE_R3.00.zip` (approximately 62–63 MB). Official archive index:
https://irsa.ipac.caltech.edu/data/Planck/release_3/ancillary-data/cosmoparams/

**Decisive first action:** retrieve and verify the archive; inventory chain files, parameter-name companions, weights, likelihood columns, and GetDist metadata; then reproduce weighted marginal summaries from existing chains. This is post-processing verification, not independent likelihood reproduction. A fresh sampler run is a separate phase and must pin the Planck likelihood release, priors, nuisance parameters, cosmological model, and sampler configuration.

**Current status:** exact archive target selected; archive retrieval, checksum capture, and chain post-processing remain pending.

## Standard-Model-shifted fixed-point coordinates

No source has yet been identified that uniquely specifies the intended coupled beta-function system and scheme. Generic quantum-gravity FRG literature is not sufficient to infer the intended coordinates.

**Decisive action:** do not solve an arbitrary system and label it Standard-Model-shifted. Find the exact paper/model and transcribe its coupled beta functions, couplings, input values, threshold treatment, regulator/scheme, and truncation. Then solve numerically, verify the residual and Jacobian independently, and compare to the source's table/figure.

**Current status:** still blocked on target-model identification and complete equations.

## Evidence policy

Each task must separately report: source equation/data provenance; independent code and environment; raw numerical output; convergence/residual checks; comparison with published values; and limits on physical interpretation. No promotion based only on toy tests or a plausible-looking curve.
