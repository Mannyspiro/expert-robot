# Merlin Research: Lacunarity, Ideonomy, and the Hierarchy of Mathematical Structure
Version 0.1 — 2026-11-04

## Executive thesis

The common thread across Merlin's xenomathematics, multi-frame mathematics, FIND-N, Continuum / Nested Continuum Mathematics, Relational Continuum Architecture, Continuum Relationship Tensors, fractal engineering, and AI representation research is this:

**Study not only mathematical objects, but also the spaces of their representations, the relations between those representations, the transformations between mathematical systems, and the evidence by which those transformations are trusted.**

Lacunarity adds a missing measurement dimension: not merely how much structure exists or how it scales, but how unevenly it is distributed and where the gaps occur.

Ideonomy adds a discovery discipline: systematically enumerate the possible concepts, distinctions, relations, transformations, hypotheses, and tests in a research domain. It is a useful programmatic method, not a universally accepted formal science with a completed set of laws.

The proposed Merlin synthesis is a typed, evidence-bearing **Mathematical Structure Atlas (MSA)**. It should be treated as a research architecture, not a claim that a final or maximal mathematics has been discovered.

## 1. Lacunarity: the missing complement to dimension

For a pattern covered by boxes of a chosen scale s, let m_i(s) be the mass or occupancy of box i. Define

\[
\Lambda(s)=\frac{\mathbb E[m(s)^2]}{\mathbb E[m(s)]^2}
=1+\frac{\operatorname{Var}(m(s))}{\mathbb E[m(s)]^2},
\]

provided the mean box mass is nonzero.

Thus Lambda(s) >= 1. It equals 1 when all considered boxes have equal mass; larger values indicate more uneven occupancy at that scale. The precise numerical value depends on the windowing, domain, normalization, sampling, and treatment of empty boxes.

Lacunarity is not itself a fractal dimension. It can describe fractal, multifractal, clustered, periodic, and non-fractal patterns. It complements dimension by distinguishing patterns with similar scaling exponents but different gap distributions.

For finite engineered objects, estimate Lambda(s) only over declared observable scales. Record:
- box/window size and shape;
- grid origin and orientation;
- occupancy definition and units;
- treatment of boundary boxes and empty boxes;
- image/mesh resolution and segmentation;
- scale range, uncertainty, and sensitivity;
- whether mass, area, volume, intensity, graph degree, or another measure is used.

A lacunarity curve is more informative than a single summary scalar. Local transitions, plateaus, peaks, and crossovers may indicate characteristic length scales or changes in organization. Do not assume a universal monotonic shape.

## 2. Generalized lacunarity across Merlin's mathematical domains

The same statistical idea can be transferred to different domains, but each transfer needs a well-defined measure and partition.

### 2.1 Spatial / engineering lacunarity
Partition a geometry, voxel field, image, mesh, or material sample into windows. Measure material, void, pore, crack, feature, or field intensity.

### 2.2 Graph lacunarity
For a graph or hypergraph, define a family of neighborhoods or graph balls at radius r. Let m_v(r) be the number or weight of nodes/edges/hyperedges in the neighborhood of v. Compute the normalized second moment across centers v. This measures uneven local connectivity, not spatial porosity.

### 2.3 Semantic / ideational lacunarity
Represent concepts as nodes in a typed concept graph, or as points in an embedding space with a declared metric. Partition into semantic neighborhoods or graph communities. Measure uneven concept density and missing bridges between regions.

Important limitation: sparse semantic embedding regions are not automatically missing knowledge. Results depend on the model, corpus, embedding, distance metric, and sampling. Compare multiple encoders and graph constructions; retain source citations and human-validated concept definitions.

### 2.4 Proof / theory lacunarity
Represent a formal theory as a dependency graph of definitions, lemmas, theorems, assumptions, and imports. A “gap” may mean a missing lemma, an unproved implication, an unresolved dependency, or an absent connection between two formalized regions. This is a structural research-planning measure, not a truth measure.

### 2.5 Model / representation lacunarity
For accessible model activations or black-box-derived representations, measure occupancy and neighborhood heterogeneity across layers or tasks. Closed APIs permit behavioral analysis only; do not infer hidden activation geometry without access to it.

### 2.6 Temporal lacunarity
Partition time series into windows and measure the distribution of events, signal energy, state transitions, or failures. Distinguish burstiness from spatial clustering and account for nonstationarity.

## 3. Ideonomy as an explicit enumeration engine

The Ideonomy archive describes the study and organization of ideas and their relationships. Merlin should operationalize this as structured enumeration rather than simply generating long lists.

For a domain, enumerate dimensions such as:

1. Objects: entities, quantities, fields, spaces, processes, agents.
2. Attributes: continuous, discrete, categorical, probabilistic, fuzzy.
3. Relations: equality, order, adjacency, dependence, causality, similarity, containment.
4. Operations: compose, transform, differentiate, integrate, project, optimize, infer.
5. Structures: sets, graphs, hypergraphs, groups, rings, modules, algebras, categories, topoi.
6. Scales: local, mesoscopic, global, temporal, hierarchical, asymptotic.
7. Representations: coordinates, matrices, tensors, functions, diagrams, glyph programs, embeddings.
8. Invariants: norms, spectra, topology, dimension, conserved quantities, equivalence classes.
9. Uncertainty: measurement error, probability, fuzzy membership, model uncertainty, logical status.
10. Evidence: derivation, proof, experiment, simulation, observation, replication.
11. Failure modes: counterexamples, singularities, non-identifiability, instability, approximation error.
12. Applications: geometry, materials, mechanics, circuits, biological systems, information, AI.

The Cartesian product of these axes is a candidate idea space, not a list to exhaust naively. Most combinations are meaningless or redundant. Merlin should prune by type checking, mathematical compatibility, known equivalences, domain constraints, and evidence cost.

Represent an idea as:

\[
I=(O,A,R,T,S,Q,E,C)
\]

where O objects, A attributes, R relations, T transformations, S scale context, Q assumptions/uncertainty, E evidence, C constraints.

An idea is actionable only when it has:
- a precise question;
- a mathematical object and types;
- a candidate definition or model;
- a falsifiable consequence;
- a baseline or counterexample search;
- an experiment or proof obligation;
- provenance and uncertainty.

## 4. The unifying structure: Mathematical Structure Atlas

Proposed typed object:

\[
\mathfrak A=(\mathcal O,\mathcal R,\mathcal T,\mathcal S,\mathcal I,\mathcal U,\mathcal E)
\]

- O: objects and typed mathematical domains.
- R: relations, including higher-arity relations.
- T: transformations and their compositions.
- S: scale spaces, coordinate frames, and representations.
- I: invariants and equivalence relations.
- U: uncertainty and applicability conditions.
- E: evidence, proofs, experiments, counterexamples, provenance.

This unifies previous Merlin strands:

- Universal Representation Engine: S and T.
- Xenomathematics / XMG-S: new typed representations and executable operators.
- FIND-N: induction, abduction, deduction, fuzzy compatibility, and testing.
- CCM / NCM: continua, dependent continua, and nested spaces.
- RCA / CRT: relations, relation tensors, hypergraphs, and evolving dependencies.
- Fractal engineering: scale hierarchy, dimension, lacunarity, and finite cutoffs.
- Silicon mathematics: model representations and learned transformations.
- CAD / MCFC: geometric constraints, assemblies, physical fields, and simulation.
- Lean: formal propositions and proof dependencies.
- Avrea: reproducible experiments, CI, artifacts, and exact commit provenance.
- CACE: independent qualification and review.

## 5. From relations to relations-between-relations

A useful progression is:

0. Elements: points, numbers, objects.
1. Relations: maps, adjacency, order, dependence.
2. Relations between relations: transformations, natural transformations, constraint morphisms.
3. Structures of transformations: categories, groupoids, operads, double categories, higher categories.
4. Spaces of structures: moduli spaces, classifying spaces, stacks, higher topoi.
5. Foundations and semantics: type theories, logics, models, interpretation functors.
6. Transformations between foundations: translations, interpretations, equivalences, conservativity and consistency questions.

This is not a single linear ladder where each level replaces the previous one. Different structures solve different problems. Higher category theory is a language for coherent relationships among relationships; homotopy type theory and univalent foundations make equivalence and identity central to foundations. Neither is a proven “last mathematics.”

## 6. What could be the highest possible mathematical structure?

There is no established maximum. Any proposed “highest structure” can itself be studied as an object in a richer meta-theory. Mathematical foundations can be iterated, and there are multiple competing foundational viewpoints.

The most ambitious coherent target for Merlin is therefore not a final largest object, but a **reflexive, typed, multi-foundational mathematical research system**:

\[
\mathfrak M^* =
(\text{objects},
\text{relations},
\text{transformations},
\text{higher transformations},
\text{theories},
\text{models},
\text{interpretations},
\text{proofs},
\text{experiments},
\text{provenance}).
\]

It should be able to represent a mathematical theory, represent models of that theory, represent translations between theories, compare the translations, and record which claims are proved, empirically supported, conjectural, or unknown.

The strongest candidate conceptual foundations to study are:
- dependent type theory and univalent foundations;
- category theory and higher category theory;
- homotopy theory and infinity-groupoids;
- topos theory and higher topos theory;
- logic, model theory, and proof theory;
- set theory and alternative foundational systems;
- domain-specific mathematical structures such as differential geometry, operator algebras, probability, and computation.

The goal is interoperability and explicit assumptions, not forcing all mathematics into one formalism.

## 7. Cross-domain lacunarity research hypotheses

H1: Dimension and lacunarity together distinguish engineering structures that dimension alone groups together.

H2: Scale-dependent lacunarity transitions can identify characteristic structural scales that correlate with changes in mechanical or transport response.

H3: A graph/semantic lacunarity measure can identify underconnected regions in a research knowledge graph, but its usefulness must be tested against expert-labeled missing connections and random / degree-preserving graph baselines.

H4: Proof-dependency lacunarity can prioritize underdeveloped formal regions, but cannot measure theorem importance or truth by itself.

H5: Multi-frame lacunarity can expose representational artifacts: a gap seen in one coordinate system or embedding may disappear under a valid alternative representation.

H6: Combining lacunarity curves, multifractal spectra, topology, anisotropy, and relational tensors improves classification or prediction over any single descriptor on held-out datasets.

Every hypothesis needs a null model, held-out evaluation, uncertainty estimates, and a counterexample search.

## 8. Initial benchmark matrix

For each benchmark, compare:
- uniform / periodic baseline;
- clustered baseline;
- randomized baseline;
- hierarchical / self-similar candidate;
- multifractal or heterogeneous candidate.

Measure:
- dimension estimates;
- lacunarity curves at multiple scales;
- connectivity / topology;
- anisotropy;
- prediction of a domain-specific outcome;
- sensitivity to resolution, orientation, sampling, and segmentation.

Use separate datasets for fitting and evaluation. Report negative results.

### Benchmark A: synthetic patterns
Known shapes, Cantor-like sets, Sierpinski patterns, periodic grids, Poisson patterns, clustered patterns. This checks whether the estimator recovers expected behavior.

### Benchmark B: CAD / mechanical lattices
Matched geometry, material, density, envelope, loading, and boundary conditions. Outcomes: stiffness, energy absorption, stress localization, fatigue, and manufacturing sensitivity.

### Benchmark C: porous materials
3D micro-CT or public image volumes with validated segmentation. Outcomes: porosity, pore connectivity, permeability, and mechanical response. Do not infer physical performance from image lacunarity alone.

### Benchmark D: research concept graphs
Curated domain ontology and cited paper-concept graph. Outcomes: recovery of expert-identified missing bridges, precision of suggested links, and stability across embeddings.

### Benchmark E: Lean proof graph
Definitions, theorem dependencies, imports, unresolved proof obligations. Outcomes: usefulness of suggested lemmas and reduction in independently verified proof effort.

## 9. Merlin implementation architecture

Suggested modules:

\
merlin/
  mathematical_structure_atlas/
    typed_objects/
    relation_registry/
    higher_relations/
    transformation_graph/
    theory_registry/
    model_registry/
    interpretation_maps/
    invariant_registry/

  ideonomy/
    domain_axes/
    concept_enumerator/
    compatibility_pruner/
    idea_graph/
    hypothesis_generator/
    counterexample_search/
    coverage_metrics/

  lacunarity/
    spatial/
    graph/
    semantic/
    temporal/
    proof_dependency/
    scale_curves/
    uncertainty/
    benchmark_suite/

  foundations/
    set_theory/
    type_theory/
    category_theory/
    higher_categories/
    homotopy_type_theory/
    topos_theory/
    logic_and_models/

  verification/
    lean/
    numerical_tests/
    evidence_receipts/
    independent_review/

## 10. Avrea / Lean / CACE workflow

Avrea should run deterministic synthetic benchmarks, tests for estimator correctness, scaling sweeps, robustness tests, and the repository's Lean qualification workflow.

Every run records:
- repository and exact commit SHA;
- environment and dependency versions;
- random seeds;
- input dataset hashes;
- estimator settings and scale windows;
- output hashes;
- test results;
- Lean toolchain and Mathlib revision;
- theorem axiom reports;
- limitations and failed hypotheses.

Lean should prove definitions and conditional mathematical statements, such as:
- lacunarity >= 1 for finite nonnegative box masses with positive mean;
- equality conditions for uniform box mass;
- invariance under specified permutations of boxes;
- scaling identities for exact synthetic self-similar constructions;
- equivalence of alternate formulations under stated assumptions.

Lean does not prove that image segmentation is correct, that a measured sample follows an infinite power law, or that an engineered object is physically safe.

CACE should independently review the proof assumptions, experiment design, provenance, counterexamples, and evidence receipt. Do not automatically merge or promote a claim because Avrea CI passes.

## 11. Recommended research order

1. Implement lacunarity estimator for synthetic 1D/2D/3D patterns.
2. Validate against uniform, periodic, clustered, random, and self-similar controls.
3. Add multiscale graph lacunarity.
4. Build ideonomy typed-axis enumerator and pruning rules.
5. Create concept-graph lacunarity benchmark with human-labeled gaps.
6. Create Lean theorem file for finite mass distributions and basic lacunarity laws.
7. Add CAD lattice experiment and compare descriptors with mechanical outcomes.
8. Add proof-dependency lacunarity and evaluate whether it improves lemma discovery.
9. Integrate all representations into the Mathematical Structure Atlas.
10. Compare foundations through explicit translation maps and preserved invariants.

## 12. Epistemic status

Established mathematics:
- box-mass lacunarity as a normalized second moment;
- fractal dimensions and multifractal formalisms;
- graphs, hypergraphs, tensors, categories, type theory, homotopy theory, and topos theory.

Established research programs:
- ideonomy as a historical project for systematic study and organization of ideas;
- univalent foundations and higher categorical foundations as active mathematical programs.

Merlin proposals:
- generalized semantic, graph, and proof lacunarity;
- Mathematical Structure Atlas;
- typed ideonomy enumerator;
- cross-domain lacunarity benchmarks.

Open hypotheses:
- whether these generalized lacunarity measures improve discovery;
- whether the integrated atlas reveals useful mathematical structures not found by conventional workflows;
- whether a multi-foundational system improves mathematical interoperability.

**Governing principle: capability grows, authority never expands.**
