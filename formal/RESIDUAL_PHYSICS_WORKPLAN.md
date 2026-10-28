# Residual physics tasks: executable starting points

This file turns the four missing-evidence items into concrete, falsifiable work packages. These are **minimal validation baselines**, not claims about the intended physical models and not replacements for published scientific specifications. A result from a toy baseline must never be relabelled as a result for quantum gravity, the Standard Model, black-hole evaporation, or real cosmological data.

## 1. Numerical FRG confirmation

### Baseline model (sanity test only)
Use the dimensionless scalar flow
\[
\partial_t g=\beta(g)=-g+g^2.
\]
Its fixed points solve \(g(g-1)=0\), hence \(g_*=0,1\). The linearized eigenvalue is \(\beta'(g_*)=-1+2g_*\): it is \(-1\) at zero and \(+1\) at one. These statements are exact algebra, independent of a numerical solver.

### Reproducible numerical check
- Integrate from declared initial values on a declared finite \(t\)-interval using at least two step sizes.
- Compare with the exact solution of \(g'=g(g-1)\), or use a separately specified regularized/truncated flow if testing a solver.
- Record method, step size, tolerances, initial conditions, floating-point precision, residuals, and convergence table.
- Do not call this a physical FRG confirmation until the target beta functional, regulator, truncation, conventions, and boundary conditions are pinned.

## 2. Lattice Page curve

### Baseline model (finite qubit circuit only)
Specify a finite chain of \(2n\) qubits initially arranged into \(n\) Bell pairs, with an explicit bipartition and a deterministic sequence of local gates. At each time step, compute the reduced density matrix \(\rho_A=\mathrm{Tr}_B |\psi\rangle\langle\psi|\) and von Neumann entropy \(S(A)=-\mathrm{Tr}(\rho_A\log\rho_A)\).

### Evidence to retain
- Gate matrices, qubit ordering, initial state, gate schedule, subsystem indices, and numeric precision.
- Check trace one, Hermiticity, positive semidefiniteness within a stated numerical tolerance, and eigenvalue normalization.
- Validate against exact small-system cases; keep finite-size data separate from any thermodynamic/continuum claim.
- The basic pure-state identity \(S(A)=S(B)\) and the dimension bound \(S(A)\leq\log\min(\dim A,\dim B)\) are candidate formal targets once the entropy and state model are represented in Lean.

## 3. Standard-Model-shifted fixed-point coordinates

### Baseline model (linear system only)
For a fully specified finite-dimensional beta system \(\beta(x)=Ax+b\), solve \(Ax_*=-b\). If \(A\) is invertible, the candidate is unique; the Jacobian is exactly \(A\), and local linear stability is determined by its eigenvalues under the declared RG-time convention.

### Evidence to retain
- The actual beta functions, renormalization scheme, truncation, coordinate normalization, units, parameter values and uncertainties.
- Solver version, starting points, residual norms, Jacobian, eigenvalues, and sensitivity to parameter perturbations.
- The current affine rational Lean theorem proves uniqueness for a one-dimensional affine equation only. It does **not** establish an actual Standard Model fixed point or numerical coordinates.
- Next formal target: existence and uniqueness for a specified affine system under a proved invertibility hypothesis; then interval-certified claims only if the interval arithmetic and input bounds are also verified.

## 4. Cosmological MCMC

### Baseline model (Gaussian toy posterior only)
Use a one-dimensional Gaussian target with declared mean and variance and a symmetric proposal. Compare the sampler's empirical moments and autocorrelation/acceptance diagnostics with analytic target moments. Use fixed seeds and independent chains.

### Evidence to retain
- Likelihood, priors, data release/version, nuisance parameters, proposal, initialization, random-number generator and seed, chain length, warm-up, and diagnostic thresholds.
- Preserve raw chains and code/config hashes; report effective sample size, split-chain convergence diagnostics, acceptance rates, and sensitivity to initialization.
- Posterior summaries are empirical estimates, not deductive proofs.
- A formal sampler theorem should target a precisely defined finite-state or measure-theoretic transition kernel and prove its invariance/detailed-balance assumptions. Do not infer correctness of a real cosmological posterior from the toy sampler.

## Promotion gate

A task can move beyond status not_yet_formalized only when its actual scientific specification is pinned and a result is independently reproducible. Keep separate statuses for (1) exact theorem, (2) numerical artifact, (3) independent reproduction, and (4) physical interpretation. A successful Lean build certifies only the compiled proposition under the audited axioms; it does not certify an unencoded scientific model.

**Resource rule:** first run deterministic low-cost checks and analytic comparisons. Do not start a second Avrea benchmark while the current paired benchmark is still active. Keep main unchanged until all required qualification gates pass.
