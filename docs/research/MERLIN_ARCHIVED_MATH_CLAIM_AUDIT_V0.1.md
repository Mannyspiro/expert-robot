# Audit of Mathematical Claims Recovered from the Merlin Master Handoff

**Purpose:** prevent archive prose or prototype code from being mistaken for established mathematics. This audit records issues in the embedded `merlin_math_core` and readable-math documents. It does not invalidate all surrounding research ideas.

## A. Resource-aware finite-time blow-up sketch

The archived Lean theorem assumes an admissible rate with (f(I)\geq 1) above a threshold and sketches the ODE

[
\dot I=f(I)I.
]

That lower bound implies at least exponential growth while the solution exists; it does **not** imply finite-time blow-up. For a positive, sufficiently regular rate, the separation-of-variables blow-up criterion is

[
\int_{I_0}^{\infty}\frac{dI}{f(I)I}<\infty.
]

For example, (f(I)=1) gives exponential growth for all finite times, whereas (f(I)=I^\alpha), (α>0), yields a finite integral and finite-time blow-up for the idealized ODE. A rigorous theorem must specify local existence, regularity, positivity, maximal solution and the integral criterion. The archived theorem's existential conclusion containing `True` is vacuous and does not encode a solution trajectory.

**Status:** archived claim unresolved / theorem statement inadequate; replace rather than cite as proved.

## B. Parrondo-style capability demo

The archived Python demo labels both operators as non-positive in isolation, but sets operator A to `delta_I=+0.15`. Therefore it is not an example of two individually losing operators. Operator B also has a negative resource cost, which increases the resource balance under the implementation's subtraction convention. The example may demonstrate a chosen alternating update, but not the stated Parrondo phenomenon.

A valid experiment must define whether “losing” means deterministic state decrease, negative expected increment under a specified stochastic distribution, or negative long-run drift. It must compare A-alone, B-alone and the switching policy under identical initial-state distributions, budgets and stopping rules.

**Status:** original claim refuted as stated; a corrected Parrondo model remains a separate research task.

## C. PGA/CGA/QGA embeddings and quadric intersections

The archived readable-math document proposes embeddings between Clifford algebras, projections, and a claim that a quadric intersection is exactly the outer product of two quadric blades.

These statements require a generator-by-generator algebra homomorphism proof. A map must preserve every defining relation (e_i e_j+e_j e_i=2g_{ij}), not merely basis labels or grade. Dimensions, signatures, null-vector pairings and the chosen basis must be consistent. In particular, a degenerate projective metric and a nondegenerate conformal metric cannot be identified by an informal basis copy.

The outer product of blades describes a span/join operation in the represented exterior algebra; it is not, by itself, the algebraic-geometric intersection ideal of arbitrary quadric zero sets. Intersections of algebraic varieties require an ideal-theoretic or equivalent construction, with degeneracy and multiplicity handled explicitly.

**Status:** proposed embeddings/projection and exact-intersection claims unverified; do not use as established theorems. First construct small explicit counterexample tests and verify metric signatures and dimensions.

## D. New, narrower research result

The companion v0.1 representation-graph prototype uses invertible rational 2x2 frame maps. For maps (P_iin GL(2,K)), define (T_{i\to j}=P_jP_i^{-1}). Then path composition and cycle identity follow by cancellation. Similarity (A_i=P_iAP_i^{-1}) preserves trace and determinant, and the characteristic polynomial; eigenvectors transform by (v_j=T_{i\to j}v_i).

These are standard linear-algebra consequences, implemented as exact finite tests. They are not claimed as novel mathematics.

## E. Research queue

1. Formalize arbitrary finite-dimensional basis-change invariance in Lean.
2. Add exact characteristic-polynomial preservation, then eigenvalue and generalized eigenspace correspondence.
3. Add partial coordinate charts and domains.
4. Distinguish coordinate transition cocycles from connection holonomy.
5. Rebuild the geometric-algebra embedding claims from Clifford universal properties and signature-preserving generator maps.
6. Replace the finite-time blow-up sketch with the integral criterion and a non-vacuous ODE theorem.
7. Rebuild the Parrondo experiment with an explicit stochastic transition model and paired baselines.

**Governance:** archive provenance is not proof. Capability grows; authority never expands.
