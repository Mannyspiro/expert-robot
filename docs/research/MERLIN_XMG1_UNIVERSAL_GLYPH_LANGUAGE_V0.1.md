# Merlin XMG-1: Universal Glyph Language

Version 0.1 — proposed specification, not yet compiler-verified.

## Purpose

XMG is a typed symbolic interface shared by mathematics, AI research, numerical computation, CAD, wiring, MCFC, and virtual engineering. A glyph is not merely a character: it identifies an operator family, a type signature, domain-specific implementations, assumptions, and an evidence contract.

The canonical glyph identifier and typed abstract syntax tree (AST) are authoritative. Glyph artwork is a rendering and may evolve.

## 1. Proposed universal glyph collection

| Glyph | Canonical ID | Operator family | Meaning |
|---|---|---|---|
| ⟐ | SEED | construction | introduce an object, value, hypothesis, or initial condition |
| ◉ | OBJ | reference | select or refer to a typed object |
| ⋈ | REL | relation | create or inspect a typed relationship |
| ↦ | MAP | mapping | translate between spaces or representations |
| ⤢ | FRAME | frame transform | change coordinate frame or viewpoint |
| ⊗ | COMPOSE | composition | compose maps, operations, or structures |
| ∇ | VAR | variation | derivative, sensitivity, variation, local change |
| ⌁ | SCALE | scaling | rescale, zoom, coarse-grain, change resolution |
| ⌬ | INV | invariant | compute or assert invariance under a declared transformation |
| ⊞ | ASSEMBLE | assembly | combine components subject to constraints |
| ⊖ | DIFF | difference | difference, residual, mismatch |
| ⊕ | SUPERPOSE | additive combination | add or superpose compatible states |
| ⌕ | SEARCH | search | enumerate a candidate space under a predicate |
| ⟲ | ITER | iteration | iterate, recurse, or seek a fixed point |
| ⊢ | PROVE | proof | create or discharge a proof obligation |
| ◌ | UNCERTAIN | uncertainty | annotate probability, interval, error, or unknown status |
| ⧖ | TIME | temporal | represent time-indexed state or evolution |
| ⌂ | BOUNDARY | boundary | define domain, interface, or boundary condition |
| ⧈ | ENCODE | encoding | serialize an object into a representation |
| ⧉ | DECODE | decoding | interpret a representation |
| ⛭ | EXEC | execution | run a permitted computation or simulation |
| ⛨ | QUALIFY | qualification | independently assess evidence against a policy |
| ⧗ | CACHE | caching | retrieve or store a content-addressed artifact |
| ⧁ | OPT | optimization | optimize objectives subject to constraints |
| ⌖ | COORD | coordinates | define or transform coordinate systems |
| ⫶ | SPLIT | partition | divide a structure into substructures |
| ⫷ | MERGE | merge | combine compatible structures, preserving lineage |
| ⊣ | CONSTRAIN | constraint | impose type, unit, domain, or admissibility constraints |
| ⊨ | SATISFY | satisfaction | evaluate a model against propositions or constraints |
| ⤳ | FLOW | dataflow | represent directed dependencies and processes |
| ⧫ | BRANCH | branching | create a hypothetical alternative state |
| ⊙ | MEASURE | measurement | estimate a declared quantity under a protocol |
| ⊚ | COMPARE | comparison | compare objects under an explicit rule |
| ⊘ | INVALID | invalidity | mark undefined, ill-typed, singular, or invalid operations |
| ⧬ | PROVENANCE | provenance | attach source, version, hash, lineage, evidence |
| ⧿ | LIFT | embedding | embed an object into a larger space |
| ⤺ | PROJECT | projection | project or reduce into a subspace or view |
| ⊛ | DUAL | duality | form a dual, adjoint, reciprocal, or paired construction |
| ⌗ | GLYPH | metasyntax | refer to an operator definition as a first-class object |

These forms are original proposed assignments for Merlin, not established universal notation. Their glyph shapes require font, accessibility, and parser-collision testing.

## 2. Abstract typed signatures

The glyph is syntax; its signature defines meaning. Initial signatures:

- SEED: Type × Parameters → Object
- OBJ: ObjectId → TypedObject
- REL: A × B × RelationType → Relation<A,B>
- MAP: A → B, with a declared map object and validity class
- FRAME: Frame<A> × A → A
- COMPOSE: (B → C) × (A → B) → (A → C)
- VAR: Function<A,B> × Direction<A> → Tangent<B>
- SCALE: ScaleAction × Object → Object
- INV: GroupAction × Quantity → InvariantQuantity
- ASSEMBLE: Components × Constraints → Assembly
- DIFF: A × A × MetricOrAlgebra → Residual
- SUPERPOSE: CompatibleState<A> × CompatibleState<A> → State<A>
- SEARCH: CandidateSpace × Predicate → RankedCandidates
- ITER: Endomap<A> × Initial<A> × StopRule → IterationTrace<A>
- PROVE: Context × Proposition → ProofResult
- UNCERTAIN: Value × UncertaintyModel → Uncertain<Value>
- TIME: State × Dynamics × TimeDomain → Trajectory
- BOUNDARY: Domain × BoundaryCondition → BoundedDomain
- ENCODE: Object × Codec → Representation
- DECODE: Representation × Codec → Object
- EXEC: Program × CapabilityToken × ResourceBudget → ExecutionReceipt
- QUALIFY: Claim × EvidenceBundle × Policy → QualificationResult
- CACHE: ContentHash × Artifact → CacheReceipt
- OPT: Objective × Constraints × SearchSpace → CandidateSet
- COORD: Space × ChartOrFrame → CoordinateRepresentation
- SPLIT: Object × PartitionRule → Components
- MERGE: CompatibleObjects × MergePolicy → Composite
- CONSTRAIN: Object × ConstraintSet → ConstrainedObject
- SATISFY: Model × Proposition → TruthAssessment
- FLOW: Nodes × DirectedDependencies → ProcessGraph
- BRANCH: State × Hypothesis → AlternativeState
- MEASURE: Object × Quantity × Protocol → Measurement
- COMPARE: A × B × ComparisonRule → ComparisonResult
- INVALID: Operation × Reason → InvalidResult
- PROVENANCE: Artifact × Lineage → ProvenancedArtifact
- LIFT: Object × Embedding → HigherSpaceObject
- PROJECT: Object × Projection → LowerSpaceObject
- DUAL: Object × DualityRule → DualObject
- GLYPH: GlyphId → OperatorDefinition

These signatures are abstract. Concrete overloads must declare domain-specific types, preconditions, units, and error behavior.

## 3. Expression model

A readable expression uses operator, operands, output type, assumptions, and domain:

    ⟦ OPERATOR ; operands ; output-type ; assumptions ; domain ⟧

Composition is explicit:

    ⊗( ↦(f), ↦(g) )

A research search and iteration:

    ⟲( ⌕(⟐(H), predicate), stopping-rule )

A proof with independent qualification:

    ⛨( ⊢(context, proposition), evidence-bundle )

A coordinate change:

    ↦( ⌖(space, frame-A), frame-B )

The parser must never silently infer units, coordinate frames, probability interpretations, or missing proof assumptions.

## 4. How the glyphs connect to mathematics

- Type theory and set theory: SEED, OBJ, REL, CONSTRAIN establish objects and admissible relations.
- Category theory: MAP, COMPOSE, OBJ represent maps, composition, and identity. Functors and natural transformations become higher-order maps.
- Higher category theory: transformations between transformations; coherence obligations attach to nested compositions.
- Linear algebra: SUPERPOSE, MAP, DUAL, INV, PROJECT, COMPOSE.
- Calculus and differential geometry: VAR, SCALE, FRAME, COORD, LIFT, PROJECT.
- Group theory: INV, MAP, COMPOSE, DUAL; the symmetry group must be named.
- Topology and homotopy: MAP, LIFT, PROJECT, INV, ITER with continuity and homotopy conditions.
- Graph theory: REL, SEARCH, SPLIT, MERGE, FLOW, MEASURE, COMPARE.
- Fractal analysis: SCALE, MEASURE, INV, UNCERTAIN, ITER. Dimension and lacunarity are descriptors, not universal quality scores.
- Logic and proof theory: PROVE, SATISFY, CONSTRAIN, INVALID.
- Probability and information theory: UNCERTAIN, MEASURE, SEARCH, COMPARE. Probability, fuzzy membership, measurement error, and logical truth remain different types.
- Numerical analysis: VAR, DIFF, ITER, OPT, UNCERTAIN, QUALIFY.
- Physics: TIME, VAR, INV, BOUNDARY, MEASURE, FLOW.
- CAD and engineering: ASSEMBLE, FRAME, COORD, BOUNDARY, CONSTRAIN, MEASURE, COMPARE, OPT.

## 5. One object, many mathematical representations

A mathematical object may have simultaneous Cartesian, polar, complex, matrix, tensor, graph, quaternion, and geometric-algebra representations.

Each representation edge is an explicit MAP object with:
- source and target types;
- domain of definition;
- inverse availability;
- information loss;
- singularities;
- preserved invariants;
- numerical error bounds;
- proof or test evidence.

A representation is not the underlying object. A translation may be exact, conditional, approximate, or lossy. Path consistency can be tested by comparing two transformation routes:

    T_BC ∘ T_AB  ?=  T_AC

Equality may be exact, conditional, or approximate under a declared tolerance.

## 6. AI-native mathematical workflow

XMG should let an AI reason through structured operations rather than requiring handwritten human-style derivations as its only interface:

1. Parse a problem into typed objects, relations, constraints, assumptions, and goals.
2. Generate multiple valid representations.
3. Enumerate candidate operators and compositions.
4. Apply symbolic rewriting for exact transformations.
5. Use numerical solvers for exploration and counterexample search.
6. Use graph search to find related definitions and theorems.
7. Send formal obligations to Lean or another proof assistant.
8. Preserve failed attempts and counterexamples as evidence.
9. Select the cheapest verification route that meets the required confidence.
10. Emit both a human-readable derivation and machine-readable execution trace.

This is an architecture proposal, not a claim that a model's hidden activations literally contain these glyphs. Actual activation analysis requires access to those activations; closed APIs permit behavioral experiments only.

## 7. Merlin adapters

- Merlin core: registry, type system, parser, AST, mathematical knowledge graph, ideonomy search.
- Hermes: route typed tasks to appropriate workers and return evidence receipts.
- Expert Robot: bounded code changes, simulations, and repository tasks.
- Avrea: reproducible numerical experiments, benchmarks, and proof-search jobs where configured.
- CACE: independent qualification of claims, assumptions, provenance, and evidence.
- Lean: formal definitions, invariants, and theorem obligations.
- Modeler: geometry, frames, constraints, transformations, and optimization.
- CAD: compile geometry and assembly glyphs into kernel operations.
- Wiring: compile typed connectivity, pin/net identity, signal direction, electrical constraints, and interface checks.
- MCFC: represent physical components, fields, boundary conditions, geometry, materials, and coupling constraints. Exact MCFC equations must come from its domain model, not be invented by glyph syntax.
- Virtualizer: compile the same IR into a digital model with explicit fidelity and uncertainty metadata.

## 8. Content-addressed cache

Cache deterministic artifacts only when all relevant inputs are known. Suggested cache key:

    SHA256(canonical-IR || glyph-registry-version || compiler-version ||
           adapter-version || dependency-lock-hash || input-hashes ||
           parameters || seed || precision-policy)

Artifact classes:
- parsed AST and normalized IR;
- symbolic simplifications;
- literature retrieval snapshots;
- numerical results;
- CAD geometry;
- simulation outputs;
- Lean build outputs;
- qualification receipts.

Every cache artifact records source commit, environment, input hashes, output hash, timestamp, random seed, numerical precision, and verification state.

Cache policy:
- exact deterministic outputs may be reused only when all key fields match;
- stochastic results require seed and uncertainty metadata;
- literature snapshots require retrieval time and source provenance;
- proofs require exact source, toolchain, and dependency hashes;
- cache hits are not fresh independent verification;
- invalidate on registry, compiler, adapter, dependency, assumption, or input changes.

If Avrea's cache API is not exposed to Merlin, implement a local content-addressed cache behind a cache interface, then add an Avrea adapter when its actual endpoint and credentials are available. This specification does not claim that Avrea has been accessed or written to.

## 9. Optimization plan

- Canonicalize and hash IR before dispatch to eliminate duplicate work.
- Run cheap type and unit checks before expensive simulation.
- Apply symbolic simplification before numerical evaluation.
- Use DAG common-subexpression elimination for shared transforms and geometry.
- Batch operations with compatible backend and device requirements.
- Use adaptive fidelity: coarse models for exploration, high-fidelity solvers for finalists.
- Use multi-fidelity uncertainty to decide whether refinement is worthwhile.
- Preserve alternative representations when one becomes singular or ill-conditioned.
- Use dependency-aware cache invalidation instead of clearing everything.
- Route tasks according to required proof strength, compute cost, and adapter capability.
- Keep model-generated proposals separate from independently verified results.

## 10. Execution and authority boundaries

EXEC is not a permission bypass. It requires a capability token, resource budget, declared target, and execution receipt. QUALIFY is separate from EXEC. A worker cannot qualify its own result as independent evidence. CAD and wiring changes remain previews until their applicable review and approval gates pass.

The invariant remains: **capability grows, authority never expands.**

## 11. Milestones

- XMG-1A: canonical glyph registry and schema; no execution.
- XMG-1B: parser and typed AST; reject invalid expressions.
- XMG-1C: algebra, graph, and coordinate adapters with unit tests.
- XMG-1D: local content-addressed cache and exact invalidation.
- XMG-1E: Lean definitions for composition, identity, and typed-map laws.
- XMG-1F: CAD and wiring preview adapters.
- XMG-1G: modeler/virtualizer adapters and multi-fidelity simulation.
- XMG-1H: Avrea cache/runner integration after actual endpoint and credentials are confirmed.
- XMG-1I: CACE independent qualification of end-to-end evidence receipts.

## 12. Open research questions

1. Which glyphs are primitive, and which should be compositions?
2. Can the registry be generated from typed algebraic signatures so glyphs are only renderings?
3. What is the smallest useful operator basis across the target mathematical domains?
4. Which algebraic laws are global, and which need domain-specific side conditions?
5. How does uncertainty propagate through exact, approximate, and lossy maps?
6. Can noncommuting representation paths reveal contradictions or missing assumptions?
7. Can adaptive computation choose among proof, numerical search, simulation, and literature retrieval while retaining calibrated evidence?
8. Which artifacts can safely be reused across compiler and adapter versions?

XMG-1 is a proposed universal interface and research language, not a proven universal foundation of mathematics. Its value must be demonstrated through coverage, compositionality, correctness, usability, and independent tests.
