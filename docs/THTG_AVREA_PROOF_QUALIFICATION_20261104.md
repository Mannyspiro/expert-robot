# THTG mathematical proof qualification — 2026-11-04

## Avrea execution

- Repository: `Mannyspiro/expert-robot`
- Branch: `feat/avrea-thtg-conditional-proof-qualification-20261104`
- Commit checked: `73917d620b7f200596b96274ef6ebbc5522f353a`
- Runner: Avrea self-hosted runner (`avrea-exe-01a1a468337e7511b47bc57fa9141fae`)
- Workflow: Formal Qualification
- Run: [#455](https://github.com/Mannyspiro/expert-robot/actions/runs/41762355488)
- Result: success
- Pinned toolchain: Lean 4.34.0, Mathlib revision from `formal/lakefile.toml`

## Qualified theorems

### 1. Conditional finite maximum

File: `formal/THTGConditionalTheorems.lean`

`THTGConditionalTheorems.continuous_attains_finite_maximum` proves that a real-valued function continuous on a nonempty closed interval `[a,b]` attains a maximum.

Avrea compiled the file successfully. The printed axiom dependencies were:
`[propext, Classical.choice, Quot.sound]`.

This is conditional mathematics only. It does not establish that the THTG entropy expression is continuous or physically correct.

### 2. No positive-g fixed point for the printed beta system

File: `proofs/THTGPrintedBetaAudit.lean`

The four decimal beta functions in the uploaded THTG report are encoded as exact rational coefficients. Lean proves:
- the exact elimination identities for `omega` and `theta`;
- the unique expressions for those couplings when `betaOmega = betaTheta = 0` and `g > 0`;
- the reduced `betaG` is strictly positive for every `g > 0`;
- therefore the four printed beta functions have no simultaneous fixed point with positive `g`.

Avrea compiled the theorem successfully. The printed axiom dependencies were:
`[propext, Classical.choice, Quot.sound]`.
The workflow rejected `sorryAx` and `admitAx`; the theorem source contains no proof escapes.

This result applies only to the coefficients as printed in the report. It does not prove that those approximate, scheme-unspecified functions are the correct FRG flow of THTG. It contradicts the report's proposed positive-`g` fixed point for that printed system.

## Research conclusions retained

- The reported Page-curve branch is strictly increasing on its stated interval and diverges as `t → T⁻`; the conditional compactness theorem cannot repair this physical premise.
- The report's `omega = alpha/G5` and `theta = beta/G5` definitions are dimensionally inconsistent with its common-`1/G5` action normalization. Under the stated natural-unit dimensions, `alpha` and `beta` have dimension `M⁻²`, so the dimensionless variables would ordinarily involve `k² alpha` and `k² beta`, subject to a fully specified FRG convention.
- The generic five-dimensional curvature-squared basis requires an explicit Riemann-squared audit; Gauss–Bonnet is not topological in five dimensions.
- The source report does not specify the regulator, gauge fixing, ghost operators, projection prescription or derivation of the approximate coefficients.

## Next proof/research gates

1. Recover a source-defined generalized-entropy/island prescription before formalizing any finite Page peak.
2. Freeze the complete five-dimensional action, boundary terms and normalization.
3. Derive the independent 5D curvature-squared invariant basis under explicit field-redefinition and boundary assumptions.
4. Recover the exact FRG setup and derive beta functions from primary calculations; do not tune coefficients to restore the reported fixed point.
5. Only after those gates, certify a corrected fixed point and its stability matrix with interval methods.
6. Derive the full matter/source equations from the specified matter action and variational boundary conditions.

The two Lean results above are formal proofs of their stated mathematical propositions, not validation of THTG as a physical theory.


### 3. Printed Page-curve branch has no interior maximum

File: `proofs/THTGPageCurveAudit.lean`

For the expression printed in the report,

`S(t) = (c/6) log(sinh(a*t) / sinh(a*(T-t)))`,

Lean proves that, when `c > 0`, `a > 0` and `0 < t < T`, every interior point has a later point `u = (t+T)/2) with `S(t) < S(u)`. The proof establishes strict monotonicity of the sinh ratio and then uses strict monotonicity of the logarithm.

- Avrea run: [#460](https://github.com/Mannyspiro/expert-robot/actions/runs/41763911516)
- Result: success on runner `avrea-exe-01a1a47c51877642aedb584e321a8816`.
- Axiom dependencies: `[propext, Classical.choice, Quot.sound]`.
- The workflow now parses the complete multiline axiom report and enforces the full allowlist.

This proves there is no interior maximum for the printed branch. It does not yet formalize the endpoint limit `S(t) → +∞` as `t → T⁻`, and it does not validate a generalized-entropy/island replacement.
