# Notebook geometry claim audit

Status: research intake, 2026-09-26. Derived from a user-provided NotebookLM
conversation export; its numbered citations do not identify an independently
replayable source snapshot. No claim here is promoted to the verified theorem
registry by this document.

## Reuse now

1. CGA distance identity. With `e_o^2=e_inf^2=0`,
   `e_o . e_inf=-1`, and both null vectors orthogonal to Euclidean
   vectors, define `X(x)=e_o+x+(x.x/2)e_inf`. Direct expansion gives
   `X(x).X(y)=-(x-y).(x-y)/2`. This is an exact rational candidate for
   formalization using the existing `MathAI.Geometry` exact geometry layer.
2. CGA translation. `T(a)=1-(a e_inf)/2` is nilpotent in the stated
   metric, and its sandwich action on normalized conformal points gives
   `X(x+a)`. Check reverse, normalization, and basis conventions explicitly.
3. Specialized representations are promising. Keep PGA for rigid motions,
   CGA for round primitives, and a specified quadric representation for
   genuinely quadratic constraints. Require typed conversions and an
   operation-preservation proof or test at every boundary. See the published
   [PGA-in-CGA construction](https://arxiv.org/pdf/2002.05993) and
   [geometric algebra for quadrics](https://zenodo.org/records/22042923).

## Counterexamples that block promotion

| Claim in export | Exact witness or defect | Required correction |
| --- | --- | --- |
| The stated PGA-to-CGA basis map is an algebra embedding | PGA(3,0,1) has four generators, but the map lists `e1,e2,e3,e0,e_inf` (five). Its images `e_o,e_inf` also have inner product -1, whereas the PGA null generator is orthogonal to the Euclidean generators. | Choose one null generator, define both models' conventions, and verify all Clifford relations, duality, and motor action. The published construction distinguishes two PGA copies within CGA. |
| The proposed sphere projection preserves quadric incidence | For `A=J=1` and all other coefficients zero, the export's QGA expression at the origin is `+1`; its projected `A e_o + J e_inf` expression is `-1`. Their zero sets differ. | Correct the constant-term sign (the candidate is `-J e_inf` under these conventions), then prove the identity for all inputs in the stated sphere subspace. This alone does not validate the full QGA embedding. |
| `Q1 ^ Q2 != 0` detects a real collision | Concentric spheres of radii 1 and 2 have dual vectors `e_o - e_inf/2` and `e_o - 2 e_inf`. Their wedge is `-3(e_o ^ e_inf)/2 != 0`, though the surfaces have no real common point. | Distinguish constraint representation from real feasibility and metric contact/penetration calculations. |
| The sample sphere-ellipsoid check is exact | Axes `(100,1,1)`, center `(101,0,0)`, sphere radius `1/10`: true separation is 1, but `((101/100)^2-1)*min(axes)=201/10000 <= 1/10`, so the sample reports a collision. | Validate against a reference closest-point or certified bound solver on interior, exterior, tangent, and extreme-aspect cases. |
| The sample IK solver is singularity-free and operational | `c_circle[15]` is out of range for a 3-vector; `d=0` divides by zero; clamping a negative radicand can turn an unreachable target into a fake solution. | Require explicit reachability `|l1-l2| <= d <= l1+l2`, handle degeneracy and swivel basis, verify both link-length residuals. |
| A 9D QGA vector encodes the displayed general quadric basis as written | The displayed expression names three spatial directions, six `e_inf` quadratic directions, six matching `e_o` directions, and a constant direction. These cannot all be independent vectors in a 9D generating space. | Specify the actual metric and independent basis; distinguish axis-aligned QGA surfaces from more expressive quadric models. |
| Sparse/JIT guarantees 16-64 products or polynomial general quantum simulation | A pairwise sparse product costs in terms of *current* active support; repeated products can densify. Stabilizer simulation applies to Clifford circuits, while the sample per-qubit string tracker has no entangling gates or phase tracking. | Benchmark support growth and compare against a plain baseline. Keep quantum claims scoped to stabilizer circuits with valid tableaux; see [Aaronson and Gottesman](https://arxiv.org/abs/quant-ph/0406196). |

## Acceptance order

1. Add typed, explicit signatures for CGA and PGA and a small exact rational
   reference evaluator; independently check the distance and translation
   identities. Keep the existing theorem registry unchanged until Lean
   checks the new statements and the usual axiom audit passes.
2. Formalize one PGA-to-CGA motor/flat correspondence using the published
   convention. Include a failed relation test for the exported map.
3. Select one quadric model and prove its point-incidence identity. Test the
   sphere projection against independent polynomial evaluation, including
   the constant-term witness above, before any lossless claim.
4. Test real intersection, clearance, and IK reachability against independent
   Euclidean reference solvers, with exact cases and bounded numerical
   tolerances where irrational roots are unavoidable.
5. Only then profile sparse routing/JIT on fixed seeds with operation counts,
   active blade support, wall time, peak memory, and correctness residuals.
   Compare with the simplest existing representation for each workload.
6. Keep quantum stabilizer work in a separate benchmark lane. No claim about
   non-Clifford gates, magic-state distillation, or general state simulation
   follows from a rotor notation alone.

Promotion rule: a derivation, counterexample, paper citation, unit test, or
agent agreement is evidence, not a kernel-checked theorem. Only the project's
existing Lean qualification and registry binding can mark a formal statement
verified. No change here expands authority or triggers an RSI promotion.
