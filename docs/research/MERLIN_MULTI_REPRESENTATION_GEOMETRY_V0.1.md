# Merlin Research: Multi-Representation Geometry and Spectral Invariants v0.1

**Status:** candidate theory + exact finite prototype; not a general geometric theorem.
**Implementation:** `merlin/representation_graph.py`
**Tests:** `tests/test_merlin_representation_graph.py`

## Research question

Can Merlin represent one mathematical object simultaneously in multiple coordinate systems and prove that calculations performed in each system describe the same underlying object?

The initial tractable case is a finite-dimensional vector space over a fixed field, with invertible linear coordinate frames.

## Definitions

Let (V) be a two-dimensional vector space over a field (K). For each frame (i), let (P_iin GL(2,K)) map canonical coordinates to frame-(i) coordinates:

[
[x]_i=P_i[x]_0.
]

The transition from frame (i) to frame (j) is therefore

[
T_{i	o j}=P_jP_i^{-1}.
]

For three frames (i,j,k), exact composition gives

[
T_{j	o k}T_{i	o j}
=P_kP_j^{-1}P_jP_i^{-1}
=P_kP_i^{-1}
=T_{i	o k}.
]

For a closed cycle based at (i),

[
T_{k	o i}T_{j	o k}T_{i	o j}=I.
]

This identity follows because all transitions were derived from a common set of invertible frame maps. It is a consistency theorem for this construction, not a theorem that every independently supplied edge-labelled graph has trivial holonomy.

## Operators and eigenstructure

Let (A:V	o V) be a linear operator. Its matrix in frame (i) is

[
A_i=P_i A_0 P_i^{-1}.
]

Thus all frame matrices are similar. Over the same field, similarity preserves the characteristic polynomial, trace, determinant, eigenvalues with algebraic multiplicity, and Jordan structure. Eigenvectors change coordinates:

[
v_j=T_{i	o j}v_i.
]

A key caveat: the field matters. A real 2D rotation matrix can have no real eigenvectors while having complex eigenvalues after extending scalars to (mathbb C). A representation adapter must record the field, not silently change it.

## Exact prototype

The v0.1 implementation uses Python `Fraction` arithmetic and square n×n matrices. Tests include 2D and 5D examples. Avrea run 41888718729 passed the catalog validator, the representation graph test suite (including 5D), and module compilation. This is finite test evidence, not a proof for all dimensions. It checks:
- invertible frame transitions and round trips;
- direct versus multi-step transition composition;
- closed cycles generated from common frame maps;
- trace and determinant invariance under basis changes;
- eigenvector coordinate transformation;
- rejection of singular frames and unknown frame IDs.

The implementation is intentionally narrow. It is a reference experiment, not a general tensor, manifold, Clifford-algebra or nonlinear coordinate engine.

## Important distinction: consistency versus curvature

A coordinate-transition cocycle and parallel transport are different mathematical structures.

- Coordinate chart transitions satisfy overlap compatibility where all maps are defined.
- A connection defines transport along paths.
- Curvature measures infinitesimal path dependence; holonomy measures transport around loops.

A non-identity product of arbitrary graph-edge maps is not automatically curvature. It may simply be inconsistent edge data. Merlin must distinguish:
1. a failed algebraic consistency check;
2. a valid nontrivial group action;
3. connection-induced holonomy;
4. numerical error within a declared tolerance.

## Next research extensions

1. Replace 2x2 matrices with typed (n	imes n) matrices over (mathbb Q,mathbb R,mathbb C).
2. Add affine frames and homogeneous coordinates.
3. Add partial charts with explicit domains and singular loci; polar coordinates at the origin are a required negative test.
4. Add complex, dual-number and quaternion representations with declared algebraic laws.
5. Add tensor and covector transformation rules, including variance and metric dependence.
6. Add local connection coefficients, path-ordered transport, curvature tensors and holonomy experiments.
7. Add Clifford algebra adapters only after proving generator relations and metric-signature preservation.
8. Formalize the finite-dimensional transition and similarity lemmas in Lean.

## Evidence boundary

The exact Python tests establish only the finite cases they execute. They do not prove arbitrary-dimensional theorems, discover new physics, establish alien mathematics, or certify an engineering model. Candidate mathematical claims remain subject to literature review, counterexample search and formal proof.


## 18. Four linked representations of a 3D rotation

For a unit axis u and angle θ, a spatial rotation has several exact mathematical descriptions.

**Matrix view.** A rotation is R ∈ SO(3), with RᵀR=I and det(R)=1.

**Complex-plane view.** Decompose v into its component parallel to u and its orthogonal component. The parallel component is fixed. The perpendicular 2D plane can be identified with C, where the rotation acts by multiplication by e^{iθ}. This is a plane representation, not a lossless identification of all 3D vectors with one complex number.

**Quaternion view.** Let q=cos(θ/2)+u sin(θ/2) be a unit quaternion and encode a vector v as a pure quaternion. Then v'=qvq^{-1}. The quaternions q and -q induce the same 3D rotation, giving the double cover S³→SO(3).

**Geometric-algebra view.** In Cl(3,0), a unit rotor R is formed from the plane bivector and acts by v'=R v R̃. Under a convention-consistent identification of the even subalgebra with quaternions, the sandwich actions agree.

The current code implements and tests all four views: quaternion sandwich action, SO(3) matrix action, Cl(3,0) rotor sandwich action, and complex multiplication on the oriented plane perpendicular to each tested rotation axis.

This creates a concrete representation graph:

\[
SO(3)\;\longleftrightarrow\;\text{unit quaternions}\;\longleftrightarrow\;\text{Cl}(3,0)\text{ rotors},
\]

with a complex representation of the orthogonal plane attached to each fixed-axis rotation.

**Next experiment:** compare all four views on exact quarter/half-turn examples, verify orthogonality and determinant, and test q and -q equivalence. Preserve handedness, active/passive convention, axis orientation and scalar-field metadata.

