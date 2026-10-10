# CACE variable-coefficient P1 assembler — qualification handoff

Research date: 2026-10-10. Status **experimental, not integrated into CACE**.

This is a new standalone assembly candidate in Expert Robot:
- `scripts/cace_variable_coefficient_p1.py` — exact triangular P1
  integration for affine-positive conductivity and bounded polynomial forcing
- `tests/cace_variable_coefficient_p1_smoke.py` — compare with
  **independently assembled** P1 quadrature and solver from
  `scripts/experiment_cace_chip_square_material_p1.py` on three meshes
- The CACE Avrea workflow executes this offline regression before any
  deploy-key access; **it does not install the module into CACE**.

## Mathematical contract

Input mesh: list of CCW oriented planar triangles and explicit rational
vertex coordinates. Numerators and denominators are limited to
10¹² in absolute value; mesh size is capped at 200 vertices / 400 triangles.
The implementation deliberately rejects high-precision decimal geometry that
exceeds these caps. Any later import of CACE floating-point coordinates
requires a **separately verified quantization/error contract**.

Material: \`k(x,y)=k0+kx*x+ky*y\`, strictly positive at **every**
mesh vertex. Since k is affine, this implies positivity in each included
triangle. The source is a finite polynomial list with terms
\`{x_power,y_power,coefficient}\` of total degree <=4, max 15 terms.
No evaluated code or executable expressions are permitted.

Assembly builds the P1 stiffness \`A_ij = sum_T integral_T
k grad(phi_i) dot grad(phi_j)\`, and \`b_i = sum_T integral_T f phi_i\`.
On each simplex, all integrals are evaluated as **exact Fractions** using
the reference barycentric identity

\[
\int_{\{s,t\ge0,\ s+t\le 1\}}s^a t^b\,ds\,dt
=\frac{a!\,b!}{(a+b+2)!}.
\]

Outputs are deterministic rational-valued CSR matrix arrays, explicit RHS,
total triangle area, and negative qualification flags. **No Dirichlet
boundary conditions, solver or continuum-error certificate** are applied
inside this assembly module.

## Manufactured-square qualification

For the unit-square reference, \`u=x(1-x)y(1-y)\`,
\`k=1+x\`, and \`f=-div(k grad(u))\`.

The forcing polynomial implemented independently is

\[
f(x,y)=2x-2x^3+y-y^2+4xy-4xy^2.
\]

The same three triangulations (5×5, 9×9, 13×13 grid nodes) agree with
a separate floating-point Gaussian-quadrature assembler to:
- maximum stiffness-entry disagreement: approximately
  4.44e-16, 4.44e-16, and 2.66e-15;
- maximum load-entry disagreement:
  1.25e-16, 3.47e-17, and 2.08e-17.

An independently solved reduced Dirichlet system reproduces the existing
benchmark center value within 1e-11. Local regression also checks
matrix symmetry, zero row sums, positive diagonal, sorted CSR columns,
exact domain area, deterministic output, and rejected mutant inputs.
No real-world silicon conductivity measurements were used.

## Boundary from research adapter to native CACE integration

The GitHub connection available when authored does **not** expose
\`morganaspim/Cace-app\`; its source tree cannot be modified here.
The pinned CACE \`PoissonAssemblyND\` contract exposes only a
constant source and cannot represent this material/source pair.

**Required future CACE-side review branch:**
1. Inspect the actual pinned \`SimplexMeshND\`, \`P1SimplexSpaceND\`,
   system and CSR output shapes, without guessing native object formats.
2. Implement a versioned, fail-closed, **opt-in**
   \`VariableCoefficientPoissonAssembly2D\` with validated geometry,
   coefficient positivity, forcing shape, source hashing and interface
   permissions. Keep unavailable from production capability registry
   until qualification.
3. Integrate exact-valued CSR under a documented Float/units/roundoff
   conversion contract, or use a separate verified rational numerical backend.
4. Enforce physical boundary and contact conditions separately, compare
   **actual CACE** A,b,u,residual against the independent oracle, then
   run mesh error, estimator and Lean assumption audits.
5. Preserve the one-job rule, free Avrea budgeting, deployment key
   isolation, rollback and same-or-less authority RSI collar.

Passing this offline assembler's tests is **not** evidence that native CACE
has executed a new FEM module, produced a continuum certificate,
modeled transistors or fabricated a chip. The result is a candidate
engineering component and a reproducible comparison target only.
