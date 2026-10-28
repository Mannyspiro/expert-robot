# THTG source-recovery audit — uploaded status report, 2026-10-28

## Source recovered

Reviewed the user-uploaded `THTG_Mathematical_Status_Report 2.pdf` (4 pages). This report is now the primary source for this audit. It explicitly calls THTG speculative, its fixed point approximate/truncation-dependent, and says no machine-checked formalization exists.

## 1. Recovered action and equations (transcribed in substance)

The report's ambient geometry is stated as ℝ × S³ × S¹ with
`ds₅² = −dR² + R² dΩ₃² + Lφ² dφ²`.
The embedded hypersurface is parameterized by `R=a(τ)`, `φ=φ(τ,xᶦ)`, with induced metric written
`ds² = −N²dτ² + a²dΩ₃² + Lφ²(dφ + Aᵢdxᶦ)²`
and `N = √(Ṙ² − Lφ² φ̇²)` (the PDF text extraction corrupts some symbols; original typesetting should be checked before formal transcription). Operational time is `t=(Lφ/2π)∫dφ`.

Bulk action:
`S_bulk = (1/(16πG₅)) ∫ d⁵x √(−g₅) [R₅ − 2Λ_top + α R_{μν}R^{μν} + β R₅²] + S_matter[φ,g₅]`.

Boundary action:
`S_boundary = (1/(8πG₅))[∫_{Σ_f}√h K − ∫_{Σ_i}√h K] + S_trans`,
with the claimed absorber condition `(advanced free field)|_{Σ_f}=0`. The report does not define the advanced field precisely or derive the condition from `S_trans`.

Two-boundary path integral:
`⟨φ_f,g_f|φ_i,g_i⟩ = ∫ Dφ Dg exp(iS[φ,g]/ℏ)`,
over configurations obeying the stated boundary condition. The source equations for matter and the full higher-derivative metric Euler–Lagrange equations are not actually written out in the report; they remain to be derived from this action and specified boundary data.

FRG equation:
`∂ₜΓ_k = (1/2) STr[(Γ_k^(2)+R_k)^{-1} ∂ₜR_k]`, `t=ln(k/k₀)`.

Truncation:
`Γ_k=(1/(16πG₅(k)))∫√g[R−2Λ_top(k)+α(k)R_{μν}R^{μν}+β(k)R²]+boundary terms`.

Dimensionless variables claimed in the report:
`g=k³G₅`, `λ=Λ_top/k²`, `ω=α/G₅`, `θ=β/G₅`.

The report's approximate beta functions are:
`β_g ≈ 3g + 1.27g²(1 − 0.41ω + 0.18θ)`
`β_λ ≈ −2λ + 0.63g(1 + 0.22ω − 0.09θ)`
`β_ω ≈ −2ω + 0.85g(1 − 1.12ω + 0.47θ)`
`β_θ ≈ −2θ + 0.71g(1 + 0.33ω − 0.95θ)`.
The report says these are cutoff-scheme dependent and gives no regulator shape, gauge fixing, ghost operators, explicit heat-kernel coefficients, projection details, or derivation of these numerical coefficients.

## 2. Independent fixed-point check: claim contradicted by the printed beta system

At the report's proposed point `(g,λ,ω,θ)=(0.41,0.19,−0.37,0.28)`, direct substitution into the printed functions gives approximately:
- `β_g = 1.4866327227`
- `β_λ = −0.14923478`
- `β_ω = 1.278781`
- `β_θ = −0.38187591`.

These are not near zero on a scale that could support the claimed simultaneous root.

More strongly, solve `β_ω=β_θ=0` algebraically for `ω,θ` as functions of `g` and substitute into `β_g`. The resulting expression is
`β_g = g(900879453 g³ + 10432590900 g² + 29678000000 g + 24000000000) / [100(10970423 g² + 65060000 g + 80000000)]`.
For every `g>0`, the denominator is positive and every term in the cubic numerator is positive. Therefore `β_g>0` whenever `g>0` and `β_ω=β_θ=0`. Consequently **the four beta functions as printed admit no non-Gaussian fixed point with positive g**. This is an algebraic contradiction, not a failed numerical search.

The nonzero simultaneous roots found from the printed system have negative g (approximately `g=-1.4816238347, -2.3079033177, -7.7909244443`), with corresponding couplings determined by the remaining equations. These do not validate the report's positive-g ultraviolet fixed-point claim.

Next action: recover the actual derivation or correct the beta coefficients from primary calculations; do not alter them merely to reproduce the claimed tuple. Recompute the stability matrix only after the beta system is corrected and justified.

## 3. Dimensional audit using the recovered action's actual normalization

Use ℏ=c=1, dimensionless action, `[x]=M⁻¹`, `[R]=[Λ_top]=M²`, `[G₅]=M⁻³`. In the uploaded action, `αR_{μν}R^{μν}` and `βR²` are inside the same square bracket as `R`, under a common `1/G₅` prefactor. Thus `[α]=[β]=M⁻²`. The stated definitions `ω=α/G₅` and `θ=β/G₅` then have dimension `M¹`, not dimension zero. The earlier audit's `M⁴` result applied to a different convention with curvature-squared coefficients outside the common `1/G₅` prefactor; it does not apply to this uploaded action.

Natural dimensionless curvature couplings for this exact bracket convention would ordinarily be `α̃=k²α`, `β̃=k²β` (subject to a fully specified FRG convention). Accordingly, either the reported definitions or the action normalization is inconsistent. The claimed fixed-point tuple cannot be interpreted as a dimensionless point until this is resolved.

## 4. Five-dimensional invariant basis and boundary variation

In five dimensions, the generic curvature-squared basis includes `R²`, `R_{μν}R^{μν}`, and `R_{μνρσ}R^{μνρσ}`, modulo integrations by parts, field redefinitions, and any explicitly stated restrictions. The Gauss–Bonnet combination is not a topological density in 5D. The reported truncation omits Riemann-squared without supplying a closure argument. The assertion that the listed couplings render the theory power-counting renormalizable is also not established by the report.

The Gibbons–Hawking–York term is the familiar boundary term for the Einstein–Hilbert action; the higher-derivative terms generally require a separately specified variational treatment and additional boundary data/terms. The report does not provide those. The transactional absorber condition is asserted but not operationally defined sufficiently to derive its contribution to the flow.

## 5. Page curve

The report gives
`S_rad(t)=(c/6)log[sinh(2πt/β)/sinh(2π(t_Page−t)/β)]` for `t<t_Page`, then merely says “the complementary expression” applies after the Page time. Let `a=2π/β>0`, `T=t_Page`. On `0<t<T`,
`S′(t)=(ca/6)[coth(at)+coth(a(T−t))]>0` for `c>0`.
Moreover, `S(t)→+∞` as `t→T⁻`. Thus the pre-Page branch as printed cannot be part of a finite continuous entropy curve on `[0,T]`, and no unspecified complementary branch for `t>T` fixes this left-side divergence. The report's claim that this formula already yields the required Page-curve shape is contradicted by its displayed expression.

Do not invent a replacement formula. Recover the source derivation and its island/no-island generalized-entropy branches, saddle-selection rule, time domains, and normalizations. Only then can continuity, finite maximum, or a rise-and-fall theorem be proved. The generic Lean compact-interval maximum theorem is conditional on continuity and does not prove those physical premises.

## 6. Lean and axiom policy

The existing `formal/THTGConditionalTheorems.lean` only states the compact-interval maximum theorem under a continuity assumption. No THTG-specific equation, fixed point, or Page curve is assumed as an axiom. Compilation and `#print axioms` remain unverified until run with the repository's pinned Lean/Mathlib toolchain. The algebraic contradiction above should be added as a Lean theorem only after the beta functions and their decimal coefficients have been represented exactly (e.g. rational constants) and the proof has been compiled.

## Status

- Action: recovered from uploaded report; source equations and boundary variation still incomplete.
- Fixed point: **contradicted by the beta functions as printed**.
- Coupling dimensions: **the report's ω,θ definitions are dimensionally inconsistent with its own action convention**.
- Curvature basis/closure: **not established; generic 5D basis is incomplete**.
- Page curve: **pre-Page expression diverges at Page time and is strictly increasing**.
- Lean: conditional compactness theorem committed, but build/axiom audit pending.
- No training/benchmark runs, no paid compute, and `main` unchanged.
