# THTG recovery and formalization checkpoint — 2026-10-28

## Executive result

The promised companion file `THTG_Mathematical_Status_Report.pdf` was not present in the accessible conversation/library search. The only recovered THTG artifact is `THTG_Lean_Handoff (1).md` (2026-10-27; 122 lines). It does **not** contain the claimed complete action, source equations, explicit beta functions, regulator, gauge fixing, ghost operators, projection prescription, or Lean source. It lists those as content supposedly present in the missing PDF. Therefore the complete THTG action and exact beta functions cannot honestly be “recovered” from the evidence currently available. No equations or coefficients have been invented to fill that gap.

## 1. What is actually recovered

The handoff labels THTG speculative and explicitly says no Lean 4 code or machine-checked residual proof exists. It records:
- (g=k^3G_5), (lambda=Lambda_{top}/k^2), (omega=alpha/G_5), (	heta=eta/G_5).
- A proposed fixed-point tuple ((g_*,lambda_*,omega_*,	heta_*)approx(0.41,0.19,-0.37,0.28)).
- A Page-curve expression (S(t)=\frac{c}{6}\log\left(\frac{\sinh(at)}{\sinh(a(T-t))}\right)), for (0<t<T), with (a=2\pi/\beta) and (T=t_{Page}).
- A proposed modified Friedmann contribution involving (alpha_4H^4+eta_4\dot H^2).
- Claimed 5D projection basis ({R,R^2,R_{\mu\nu}R^{\mu\nu}}).

It provides no full bulk/boundary action, no definition of the matter/source stress tensor, and no beta-function formulas. The coordinate tuple alone cannot determine a unique beta system.

## 2. Page-curve correction: rigorous disposition

For the recovered expression, assuming (c,a>0) and (0<t<T),
[
S'(t)=\frac{ca}{6}\left(\coth(at)+\coth(a(T-t))\right)>0.
]
Also (S(t)\to-\infty) as (t\to0^+) and (S(t)\to+\infty) as (t\to T^-). It is monotone increasing and singular at the proposed Page time. It has no finite maximum on that open interval. The claim in the handoff that this formula “rises then falls” is contradicted by its own equation.

A defensible repair is not to patch the expression by hand. Recover a source-defined generalized entropy, including the no-island and island saddle branches, their domains and boundary conditions; specify which saddle is selected (usually by a minimum prescription where applicable); then establish branch continuity/regularity and crossing conditions. If the resulting entropy (S:[0,T]\to\mathbb R) is continuous on a compact interval, the extreme-value theorem proves existence of a finite maximum. This is a **conditional mathematical theorem**, not yet a theorem about THTG or black-hole evaporation. A continuous function need not have a unique maximum or rise then fall; those require additional hypotheses such as branch monotonicity and a unique crossing.

## 3. 5D dimensions and action normalization

Use natural units (c=\hbar=1), dimensionless action, and ([x]=M^{-1}). Then ([d^5x]=M^{-5}), ([R]=[\Lambda]=M^2), and the Einstein-Hilbert coefficient requires ([G_5]=M^{-3}).

For the conventional normalization
[
\Gamma_k= -\frac{1}{16\pi G_5}\int d^5x\sqrt g\,(R-2\Lambda)
+\int d^5x\sqrt g\,[\alpha R^2+\beta R_{\mu\nu}R^{\mu\nu}]
+\Gamma_{boundary}+\Gamma_{matter},
]
the curvature-squared terms require ([\alpha]=[\beta]=M), so ([\alpha/G_5]=[\beta/G_5]=M^4). Thus the handoff's ω and θ are not dimensionless under this convention. A dimensionless alternative is to define ω and θ as coefficients *inside* a common (1/G_5) prefactor, e.g. terms (G_5^{-1}\,\omega R^2/k^2) and (G_5^{-1}\,\theta R_{\mu\nu}R^{\mu\nu}/k^2), subject to the chosen scale convention. This is an illustration of a possible normalization, **not a recovered THTG action**. The original convention must be supplied before translating fixed-point coordinates.

A matter source can conventionally be defined by (T_{\mu\nu}=-(2/\sqrt{|g|})\,\delta S_{matter}/\delta g^{\mu\nu}) (sign depends on the metric/action convention). THTG's source equations cannot be recovered without its actual matter action, field content, and sign convention.

## 4. Curvature-squared basis in five dimensions

In general (d=5), (R_{\mu\nu\rho\sigma}R^{\mu\nu\rho\sigma}) is an independent curvature-squared invariant. The Gauss–Bonnet combination is not a topological density in 5D, so the 4D argument that permits a topological simplification does not establish closure in 5D. A complete basis audit must account for at least Riemann-squared, Ricci-squared, scalar-curvature-squared, total derivatives, possible field redefinitions, and gauge/ghost contributions. Whether a particular truncation closes is a result to derive from the specified quantization and divergence calculation—not a consequence of power counting alone.

## 5. Exact beta functions and fixed point

The four functions βg, βλ, βω, βθ are absent. So are the regulator shape, gauge fixing, ghost operators, heat-kernel coefficients, projection, truncation, and renormalization scheme. There is no well-defined independent numerical reproduction to perform yet. The tuple is currently an unverified claim, not a root certificate. Do not encode the tuple as an axiom or assumption that silently turns it into evidence.

Required recovery inputs: the cited companion PDF or original derivation/source, the exact action and all normalizations, explicit beta functions, and calculation settings. Once recovered, compute residuals at the proposed point, solve independently, certify a root using interval methods, and compute the stability matrix/eigenvalues with explicit sign conventions.

## 6. Lean formalization and axiom audit

Added `formal/THTGConditionalTheorems.lean` with a general theorem: any real-valued function continuous on a nonempty compact interval ([a,b]) attains a finite maximum there. This theorem deliberately does not define THTG or assume the incorrect Page formula has the required shape.

Axiom audit policy for this module:
- No user-defined axioms.
- No `sorry` or `admit`.
- Expected dependency is the standard Mathlib compactness/extreme-value theorem and its ordinary foundational dependencies.
- This commit has not been compiled in a Lean environment in this execution, so build status is **unverified**, not “proof passed.” Run `lake env lean formal/THTGConditionalTheorems.lean` against the repository-pinned toolchain and inspect `#print axioms THTGConditionalTheorems.continuous_attains_finite_maximum` before promoting its status.

The theorem only closes the conditional compactness obligation. It does not prove continuity, finite-valuedness, branch crossing, or the Page curve for THTG.

## Acceptance status

- Complete THTG action/source equations: **not recovered; companion PDF missing from accessible sources**.
- Page expression in handoff: **contradicts claimed finite Page peak**.
- Conditional finite-maximum theorem: **source added; Lean compilation/axiom inspection pending**.
- 5D coupling dimensions: **resolved under explicitly stated conventional normalization; THTG normalization unresolved**.
- 5D curvature basis closure: **not established; current proposed basis incomplete absent further proof**.
- Exact beta functions/fixed point: **blocked by missing equations and scheme**.
- No training/benchmark runs; no paid compute; `main` unchanged.
