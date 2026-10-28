# THTG residual proof audit — 2026-10-28

## Scope and evidence rule

This audit checks claims in the available `THTG_Lean_Handoff` (dated 2026-10-27) against their stated mathematics and relevant published FRG literature. The handoff itself labels Toroidal-Hyperspherical Transactional Gravity (THTG) **speculative** and says no Lean verification exists. This audit does not promote it to an established physical theory.

## Finding 1 — The proposed Page-curve expression does not have the claimed shape

The handoff gives, for (0<t<t_{Page}),

[
S(t)=\frac{c}{6}\log\!\left[\frac{\sinh(at)}{\sinh(a(T-t))}\right],\quad a=\frac{2\pi}{\beta},\quad T=t_{Page}.
]

Assume (c>0), (a>0), and (0<t<T). Direct differentiation gives

[
S'(t)=\frac{ca}{6}\left[\coth(at)+\coth(a(T-t))\right]>0.
]

Both coth terms are positive on this interval. Further,
[
\lim_{t\to0^+}S(t)=-\infty,\qquad
\lim_{t\to T^-}S(t)=+\infty.
]

Therefore this expression is strictly increasing and diverges at the proposed Page time. It cannot by itself establish a finite Page peak followed by a decline. Appending an unspecified “complementary expression” after (T) does not repair the pre-(T) divergence or establish continuity, matching, or a maximum.

**Disposition:** BLOCKED / formula must be corrected from a source-derived island or generalized-entropy calculation before any Lean proof of Page-curve shape is attempted. Do not formalize the desired conclusion from this formula; its derivative contradicts that conclusion.

## Finding 2 — The stated 5D coupling coordinates need dimensional reconciliation

The handoff defines (g=k^3G_5), (lambda=\Lambda_{top}/k^2), (\omega=\alpha/G_5), and (\theta=\beta/G_5), while referring to a four-derivative action containing (R^2) and (R_{\mu\nu}R^{\mu\nu}).

Under the conventional normalization
[
\Gamma_k\supset\int d^5x\sqrt g\left[-\frac{R-2\Lambda}{16\pi G_5}+\alpha R^2+\beta R_{\mu\nu}R^{\mu\nu}\right],
]
with (c=\hbar=1), the action is dimensionless, ([R]=M^2), ([G_5]=M^{-3}), and the coefficients of the standalone curvature-squared terms have ([\alpha]=[\beta]=M). Thus ([\alpha/G_5]=[\beta/G_5]=M^4), not dimensionless. The proposed ω and θ are not dimensionless in this conventional action normalization.

This may be a notation mismatch rather than a physical contradiction: if α and β instead denote dimensionless coefficients multiplying curvature-squared terms with a factor of (1/G_5), the action must say so explicitly. The handoff does not specify that normalization.

**Disposition:** BLOCKED. Write the complete action with coefficient normalization and units before building beta functions or entering fixed-point coordinates. No numerical root can be qualified while the variables are dimensionally ambiguous.

## Finding 3 — The claimed 5D counterterm closure is not established by the handoff

The handoff proposes projecting onto ({R,R^2,R_{\mu\nu}R^{\mu\nu}\}) and proving that all one-loop divergences are absorbed by (G_5,\alpha,\beta,\Lambda_{top}). In five dimensions, (R_{\mu\nu\rho\sigma}R^{\mu\nu\rho\sigma}) is not generally reducible to those two Ricci-squared invariants plus a topological Euler density: the familiar four-dimensional Gauss–Bonnet/topological simplification does not eliminate the independent Riemann-squared operator in (d=5).

Published FRG work does derive flows for general curvature invariants in arbitrary dimension, and the higher-derivative literature explicitly treats dimension-dependent invariant bases. That supports the need for a careful basis audit; it does not prove the THTG-specific truncation is closed.

**Disposition:** BLOCKED pending an explicit invariant-basis derivation, field-redefinition analysis, total-derivative classification, gauge/ghost sector, and cited 5D one-loop divergence calculation. Do not claim renormalizability or counterterm closure before this is done.

## Finding 4 — The fixed-point coordinates cannot currently be independently reproduced

The handoff supplies approximate values ((g_*,\lambda_*,\omega_*,\theta_*)\approx(0.41,0.19,-0.37,0.28)) but does not include explicit functions (\beta_g,\beta_\lambda,\beta_\omega,\beta_\theta), regulator shape, gauge fixing, ghost operators, projection conditions, or truncation details. A coordinate tuple alone cannot establish that it is a root, and no stability matrix can be differentiated from missing functions.

Published sources show that FRG fixed points depend on the chosen truncation and regulator, and that higher-derivative gravity flows have been calculated in specific settings. Those papers cannot be silently substituted for the absent THTG-specific equations.

**Disposition:** BLOCKED. Recover the exact companion action/equations and source provenance; independently derive or transcribe the four beta functions; evaluate all residuals and the stability matrix; then use interval enclosures for root existence and eigenvalue classification. Do not encode the approximate coordinates as assumptions.

## Ordered next actions

1. Correct the Page-curve formula from a fully specified generalized-entropy/island prescription and prove continuity/finite maximum before proving monotonicity on each side.
2. Freeze the complete 5D action and resolve dimensions/normalizations.
3. Audit the independent curvature-squared operator basis in (d=5); do not assume closure.
4. Recover and pin the regulator, gauge, ghost operators, projection, and explicit beta functions from a primary source or reproducible derivation.
5. Only then perform a certified fixed-point calculation and formalize the resulting *conditional* theorem in Lean.
6. Treat Standard-Model matter shifts and Planck/Pantheon+/BAO comparisons as later tasks: neither can rescue a mis-specified action or beta system.

## Current evidence status

- Page-curve shape: **contradicted by the formula currently written**.
- Dimensionless fixed-point coordinates: **not well-defined under the conventional action normalization stated above; normalization missing**.
- 5D one-loop counterterm closure: **not established**.
- Numerical fixed point and critical exponents: **unverified; beta functions absent from the handoff**.
- THTG as a unified-field theory: **speculative; not proved**.
- No training/benchmark runs are requested or authorized by this audit.
