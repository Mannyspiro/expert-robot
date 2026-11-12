# Paired-State Continuum Simplex — First Executable Slice

Status: experimental mathematical implementation, not a claim of a new established mathematical field.

## Model

The first laboratory fixes a two-channel real state at each point of an oriented edge:

\[
F_e(t)=(u_e(t),v_e(t)),\qquad t\in[0,1].
\]

The triangle uses the orientation convention

- \(AB:A\to B\),
- \(BC:B\to C\),
- \(CA:C\to A\).

Each edge is a sampled, piecewise-linear field. The endpoint values at a shared vertex must agree. This is the minimum gluing condition for a single-valued boundary field.

## What the current code implements

- finite, strictly ordered edge samples including both endpoints;
- piecewise-linear evaluation along an edge;
- shared-vertex compatibility checks;
- a classifier for the affine barycentric extension;
- affine extension evaluation in barycentric coordinates;
- typed 2-by-2 linear state transforms, determinant/invertibility checks, and explicit left-to-right composition;
- generic oriented simplex boundary chains with canonical orientation signs and integer coefficients;
- executable checks of boundary-of-boundary cancellation on triangles and tetrahedra;
- a provisional n-ality signature separating geometric dimension, state dimension, logical channels, and temporal parameters.

The state pair is deliberately **not** assumed to be a complex number. Complex semantics would require a separate algebraic type and operations.

## Extension semantics

The current implementation proves only that the supplied sampled boundary trace is compatible with the affine barycentric extension when all three edge traces are affine and shared endpoints agree.

If the vertices agree but an edge trace is nonlinear, the classifier returns
\`RequiresHigherOrderOrDifferentExtension\`. This is not a proof that no continuous
extension exists. A later finite-element / harmonic / PDE extension module must
state its function space, regularity, boundary conditions, and solver or proof
contract before reporting existence or uniqueness.

If shared vertex values disagree, no single-valued continuous boundary field
exists under the current gluing convention; the code reports
\`VertexIncompatible\`.

## Next mathematical increments

1. Replace sampled-only traces with a versioned function/representation IR.
2. Add polynomial and piecewise-polynomial edge bases with exact coefficient types.
3. Add tetrahedral and general oriented simplicial complexes using the same
   component/state-space representation.
4. Implement boundary and coboundary operators and verify
   \(\partial_{n-1}\partial_n=0\) on generated finite complexes.
5. Add loop transport and holonomy over typed edge maps, including non-invertible
   maps and explicit information-loss classification.
6. Add constrained interior-extension experiments (harmonic and finite-element
   baselines) with reproducible solver receipts.
7. Export the exact same mathematical IR to Lean, numerical experiments, the
   knowledge graph, and the research HUD.

## Verification boundaries

A C++ smoke test is executable regression evidence only. It is not a Lean proof,
not a numerical reproduction, not an independent CACE attestation, and not a
promotion decision. The CI result must be checked against the exact candidate
commit. The CACE verifier must independently bind the source commit and exact
artifact digest before evidence can be marked independently verified.

The existing Merlin governance invariant remains in force: capability grows,
authority never expands. No code in this slice can qualify skills, approve
candidate promotion, change CACE trust roots, or grant runner permissions.
