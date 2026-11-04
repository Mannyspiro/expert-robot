# Merlin Mathematical Idea Ledger v0.1

**Purpose:** durable index of the mathematical research program discussed across Merlin/XMG work. This is a research ledger, not a claim that speculative ideas are established results.

**Status vocabulary:** `candidate`, `literature_checked`, `counterexample_checked`, `finite_tested`, `formalized`, `supported`, `refuted`, `unresolved`. Status is attached to a specific claim, not an entire topic.

## 1. Core research thesis: representation-first mathematics

A mathematical object should be representable in several coordinate systems and algebraic languages at once. A representation is a typed map, not an informal relabeling.

For each map record:
- source and target types, dimensions, domain and codomain;
- frame, basis, units, orientation and conventions;
- inverse or partial-inverse availability;
- singularities, branch cuts and information loss;
- invariants preserved and quantities changed;
- numerical error model and provenance;
- proof, test or measurement receipts.

For composable maps, test path consistency:
\[
T_{BC}\circ T_{AB}\stackrel{?}{=}T_{AC}.
\]
Classify equality as exact, conditional, approximate-with-bound, or false. A commuting diagram is evidence only when its domains, assumptions and map definitions agree.

Example: compare a Cartesian transformation with its complex-plane counterpart:
\[
T_{\mathbb C}\circ\Phi \stackrel{?}{=} \Phi\circ T_{\mathbb R^2},
\]
where \(\Phi(x,y)=x+iy\), with explicit orientation and convention assumptions.

## 2. Coordinate systems and simultaneous frames

Explore one point or object represented in multiple systems simultaneously:
- Cartesian, polar, cylindrical and spherical;
- homogeneous/projective coordinates;
- complex plane and split-complex/dual-number variants;
- matrices, vectors, covectors and tensors;
- quaternions and geometric/Clifford algebra;
- graph, manifold, local chart and frame bundles;
- 3D, 4D, 5D and higher-dimensional embeddings.

A coordinate tuple is not the geometric point itself. Record transition maps and equivalence relations. Track coordinate singularities (for example, polar angle at the origin) separately from singularities of the underlying object. Multiple frames are useful only when frame transforms and synchronization conventions are explicit.

Research questions:
1. What minimal typed interface lets one object expose multiple valid representations?
2. Which invariants survive each transition?
3. Can Merlin discover commuting diagrams or detect inconsistent paths?
4. How should uncertainty and measurement error propagate across representations?

## 3. Complex, trigonometric and geometric number systems

Treat \(i\), sine/cosine, polar form, rotations and matrix representations as connected encodings of structure:
\[
e^{i\theta}=\cos\theta+i\sin\theta,
\qquad
(x,y)\leftrightarrow x+iy.
\]
Extend comparisons to quaternions for 3D rotations, dual numbers for first-order infinitesimal structure, and Clifford/geometric algebra for unified treatment of scalars, vectors, bivectors and higher-grade objects.

Do not assume every algebra is interchangeable: record multiplication rules, signature, commutativity, associativity, norm, conjugation and geometric interpretation. Build conversion operators only where a well-defined homomorphism or explicitly lossy map exists.

## 4. Eigenstructure, matrices and higher-dimensional transforms

Model linear maps by matrices relative to declared bases. Enumerate eigenvalues/eigenvectors, eigenspaces, invariant subspaces, Jordan structure, singular values, spectral decompositions and matrix functions. Distinguish real/complex spectra and diagonalizable/nondiagonalizable cases.

For transformations across dimensions, define embedding, projection, restriction and quotient maps. Preserve the distinction between an eigenvalue of a represented matrix and an invariant of the abstract operator.

Candidate research:
- multi-frame eigenstructure and frame-invariant spectra;
- coupled coordinate representations of the same operator;
- tensor contractions and invariant scalars;
- geometric meaning of complex eigenpairs in real systems;
- higher-order and nonlinear analogues (Jacobian, tangent map, Koopman operator).

## 5. Space-time, block spacetime and time-dependent structure

Explore spacetime as a geometric object with coordinate charts, metric, causal structure and observer frames. A projection of a 4D spacetime object into 3D space or a time slice is a map with information loss; it is not the full object.

Time crystals and periodic dynamics should be treated with precise definitions of symmetry, observable, driving protocol, stability and measurement. Distinguish equilibrium time-translation symmetry breaking claims from driven discrete time-crystal behavior. Use dynamical systems, Floquet operators, spectral properties and correlation functions as candidate mathematical tools.

Questions:
- How do frame transformations affect spacetime projections?
- Which features are invariant under coordinate changes?
- Can a 4D world-tube or trajectory be represented consistently in several chart systems?
- What is lost when a temporal process is rendered as a static CAD model?

## 6. Xenomathematics and glyph-native formalism (exploratory)

The xenomathematics program asks how a mathematical language might be designed without assuming familiar human symbol conventions. This is a design/research exercise, not evidence of extraterrestrial mathematics.

Core idea: glyphs denote typed operations or structured operators, rather than being decorative symbols. Glyphs can be composed into higher-order glyphs; the glyph AST is semantic authority and the drawing is only a rendering.

Candidate notation:
\[
\langle\!\langle operator; operands; output\ type; assumptions; domain\rangle\!\rangle
\]
Each operator needs a type signature, domain constraints, semantics, canonical ID, rendering metadata and proof/test status. The language should support variable arity, higher-order operators, explicit assumptions, units, dimensions and effect/authority annotations.

The XMG-1 glyph engine currently has a small typed expression language, a bounded candidate generator, a finite rewrite normalizer and a critical-pair explorer. It is not yet a general mathematical discovery engine.

## 7. Ideonomy and mathematical idea-space exploration

Represent ideas as a typed hypergraph:
\[
G=(V,E,\tau_V,\tau_E,\sigma,\pi),
\]
where vertices are concepts/objects/claims and hyperedges encode multi-way relations, transformations, dependencies and evidence.

Useful gap classes:
- knowledge gap: missing definition, fact or source;
- connection gap: untested relationship between known concepts;
- representation gap: missing or costly encoding;
- proof gap: conjecture without derivation;
- measurement gap: claim lacks suitable empirical test.

Never infer novelty from absence in the local graph. Use explicit literature search, counterexample search and provenance. A null-model anomaly score may be explored:
\[
Z=(C_{obs}-E[C_{null}])/SD(C_{null}),
\]
but only with a declared null model, constraints, seed, sample size, uncertainty and multiple-testing correction. If variance is zero, report `not_calibrated`; do not manufacture a score.

## 8. Fractals, lacunarity and engineering morphology

For window masses \(m_i(s)\) at scale \(s\):
\[
\bar m_s=|U_s|^{-1}\sum_i m_i(s),\quad
q_s=|U_s|^{-1}\sum_i m_i(s)^2,\quad
\Lambda(s)=q_s/\bar m_s^2
=1+Var(m_i(s))/\bar m_s^2\geq1
\]
when the mean is positive; undefined at zero mean. Lacunarity measures distribution/heterogeneity of mass across windows and is not a universal performance score. Record scale, window, mask, grid, boundary and sampling metadata. Similar fractal dimensions can coexist with different lacunarity.

Engineering representation:
\[
\mathcal E=(\mathcal G,\mathcal H,\mathcal R,\mathcal M,\mathcal B,\mathcal Y,\mathcal U),
\]
for geometry by scale, hierarchy, frames, materials, boundary/loading, response and uncertainty/provenance.

Candidate feature vector \(F(E)=(D_B,\Lambda,r,n,A,K,H)\) is a descriptor, not a universal quality metric. Compare designs under matched material, mass/density, envelope, loading and boundary conditions. Evaluate stiffness/mass, peak load/mass, energy absorption/mass, stress localization, failure, fatigue and manufacturing sensitivity.

## 9. Superorganism and collective mathematics

Explore collective systems as interacting agents, cells, modules or subsystems. Candidate formalisms include graph dynamical systems, coupled oscillators, network control, information theory, statistical mechanics, reaction-diffusion systems and multiscale models.

Distinguish:
- local rules from emergent global behavior;
- correlation from causal influence;
- descriptive analogies from mathematically specified models;
- collective optimization from stability, robustness and fairness constraints.

A useful model must specify agents, state, interaction topology, update rule, boundary conditions, observables and falsifiable predictions.

## 10. CAD, wiring, MCFC and physical engineering bridge

Map mathematical representations to engineering artifacts through explicit contracts:
- geometry and coordinate frames;
- connectivity graph and typed ports;
- electrical/thermal/mechanical fields;
- materials, tolerances and constraints;
- boundary conditions and loads;
- simulation configuration and solver provenance;
- manufacturability, safety and verification constraints.

A wiring diagram is a graph plus physical layout, not merely a picture. A CAD transform must preserve declared constraints and units. Simulation results are conditional on model assumptions and require independent validation before engineering use.

## 11. XMG rewrite and proof research

Current implementation areas:
- Glyph Foundry: typed expression construction, bounded candidate generation and evidence-gated promotion.
- XMG-1C: finite rewrite rules for integer double negation/absolute value, pair projections and composition identities.
- XMG-1D: Lean source for composition laws, pair projections and integer identities; a natural-valued strict-decrease theorem was added to support termination arguments.
- XMG-1E: bounded critical-pair exploration and a deliberately divergent positive control.

For a rewrite relation \(\to\), a natural-valued measure \(m\) satisfying \(t\to t'\Rightarrow m(t')<m(t)\) establishes termination. The implementation currently uses AST node count as a candidate measure. Formalize the AST, each rule's type preservation and measure decrease in Lean. Newman's lemma then gives confluence from termination plus local confluence. Finite exploration is not a proof of global confluence.

Next proof milestones:
1. Compile the actual project Lean root with the pinned toolchain.
2. Define AST size in Lean.
3. Prove each rewrite preserves typing.
4. Prove each accepted rewrite strictly decreases size.
5. Generate symbolic critical pairs from rewrite-pattern overlaps.
6. Prove joinability for each critical pair or record a counterexample.
7. Apply a formally stated Newman theorem only after hypotheses are discharged.
8. Export proof obligations and evidence receipts to CACE.

## 12. Research evidence and source hygiene

Each idea/claim must record:
- stable ID and concise title;
- exact claim, definitions and assumptions;
- source chat, document, paper or experiment;
- status and rationale;
- related ideas and typed relations;
- counterexamples or unresolved objections;
- next proof, experiment or literature search;
- source revision/hash where applicable.

Relevant literature leads already noted in the project:
- Allain & Cloitre (1991), lacunarity, DOI: https://doi.org/10.1103/PhysRevA.44.3552
- Kovács & Erdélyi (2024): https://link.springer.com/article/10.1007/s10044-024-01332-6
- MIT Ideonomy archive: https://ideonomy.mit.edu/
- Rudan & Sheikh (2025), DOI: https://doi.org/10.7189/jogh.15.04360

These are leads, not proof that every claim in this ledger is supported by those sources.

## 13. Roadmap

1. Validate the structured idea catalog and enforce stable IDs/typed links.
2. Wire idea intake into Merlin's research ingestion path.
3. Connect Avrea experiments to immutable source/config/seed receipts.
4. Re-run XMG-1E benchmark after the import-path correction.
5. Compile Lean with the repository's real toolchain and resolve failures.
6. Formalize AST termination and rewrite correctness.
7. Extend representation graph with typed coordinate/algebra transitions.
8. Add CAD/MCFC mappings and constrained simulation experiments.
9. Promote only with independent CACE qualification; preserve rollback and authority boundaries.

**Governance:** capability grows, authority never expands. Candidate generation and search do not grant execution or merge authority. No result is promoted solely because a model generated it.


## 14. Multi-representation transition graph (new v0.1 research slice)

For a vector space V and invertible frame maps P_i from canonical coordinates into frame i, define

\[
T_{i\\to j}=P_jP_i^{-1}.
\]

Then

\[
T_{j\\to k}T_{i\\to j}=P_kP_j^{-1}P_jP_i^{-1}=P_kP_i^{-1}=T_{i\\to k}.
\]

The companion prototype `merlin/representation_graph.py` implements this for exact rational 2x2 matrices. Its tests cover transition round trips, path composition, closed cycles, trace/determinant invariance under similarity, eigenvector coordinate transformation and invalid frames.

For an operator A, the matrix in frame i is A_i=P_iAP_i^{-1}. Similarity preserves the characteristic polynomial over the same field. This does not mean eigenvalues are independent of scalar-field extension: a real rotation matrix has no real eigenvectors but has complex eigenvalues over C.

**Boundary:** this is a finite exact implementation of standard linear algebra, not a claim of novel mathematics or a general coordinate engine.

## 15. Distinguish transition consistency from geometric holonomy

Coordinate-chart transition maps obey overlap compatibility where their domains overlap. A connection defines parallel transport along paths. Curvature and holonomy concern that transport, not arbitrary products of graph-edge labels.

A non-identity product around a graph cycle can mean inconsistent edge data. It is not, by itself, evidence of curvature. The next research stage must define a connection, path transport and loop comparison before using holonomy terminology.

## 16. Audit findings from the uploaded Master Handoff

The recovered archive's mathematical-core files contain useful candidates, but three claims require correction:

1. The archived ODE condition f(I)≥1 for dI/dt=f(I)I does not imply finite-time blow-up. A positive regular scalar model requires the separation integral \(\int_{I_0}^{\\infty} dI/(f(I)I)\) to converge, together with a properly stated maximal-solution argument. The archived Lean theorem also has a vacuous conclusion containing `True`.
2. The archived Parrondo demo sets operator A to a positive capability increment (+0.15), so it does not demonstrate two individually losing operators producing net gain under alternation.
3. The archived PGA/CGA/QGA claims require explicit generator-relation and metric-signature preservation. The exterior product of blades is not generally the algebraic-geometric intersection ideal of arbitrary quadric zero sets.

See `MERLIN_ARCHIVED_MATH_CLAIM_AUDIT_V0.1.md`. These findings are recorded as corrections, not silently deleted from historical provenance.

## 17. Immediate mathematical work queue

1. Generalize the exact frame graph to n×n rational matrices and then typed real/complex matrices.
2. Add characteristic-polynomial equality and generalized eigenspace transport.
3. Add partial coordinate charts, domains and singular loci.
4. Formalize transition composition and similarity invariance in Lean.
5. Build a separate connection/holonomy experiment on a known curved manifold.
6. Reconstruct geometric-algebra embeddings from metric-preserving generator maps.
7. Replace the archived blow-up sketch with a non-vacuous theorem based on the integral criterion.
8. Rebuild the Parrondo experiment using an explicit stochastic transition model, paired seeds and equal resource budgets.

