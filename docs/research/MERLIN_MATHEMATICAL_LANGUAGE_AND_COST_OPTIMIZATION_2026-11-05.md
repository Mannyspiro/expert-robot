# Merlin Mathematical Language Research and Cost-Optimization Plan

**Date:** 2026-11-05  
**Status:** research synthesis and implementation specification; not a claim of completed compiler integration  
**Target:** `Mannyspiro/expert-robot`, isolated branch `repair/merlin-full-integration-20261105`  
**Policy:** free-first; bounded CPU/RAM; reproducible Avrea/OCI runs; CACE independent qualification  
**Invariant:** capability grows, authority never expands.

## Executive decision

Do not try to invent one glyph alphabet that replaces every programming language. Build a **typed Mathematical Intermediate Representation (MIR)** with multiple front ends and back ends:

- XMG glyphs are a compact visual and textual surface syntax.
- A canonical typed AST/DAG is the semantic source of truth.
- A small functional core gives deterministic composition and evaluation.
- Domain adapters supply algebra, geometry, tensor, graph, physics, CAD, wiring, simulation, and proof semantics.
- A bounded e-graph/rewrite layer discovers equivalent representations.
- Lean verifies selected algebraic laws and proof obligations.
- The compiler extracts the cheapest valid execution plan under measured CPU, RAM, time, precision, and verification costs.
- CACE independently checks receipts; it does not trust a worker's self-reported success.

This is a universal *interchange and composition layer* in the practical engineering sense, not a claim that one finite notation is a universal foundation for every mathematical object or physical theory.

## Repository findings

The current Expert Robot branch already contains substantial foundations:

1. XMG-1 glyph registry JSON with roughly forty proposed operators and a canonical-ID-first rule.
2. XMG universal-language specification with typed signatures, explicit assumptions, domain adapters, and content-addressed cache design.
3. Glyph Foundry with typed immutable expression nodes, composition, pair/projection, constraints, fingerprints, bounded enumeration, and fail-closed promotion checks.
4. XMG-1C normalizer with a small finite rewrite set and explicit rewrite traces.
5. XMG-1E critical-pair/confluence explorer with bounded search and honest unresolved/truncated states.
6. Lean law source for composition, identities, projections, and integer examples; its own specification says compilation is not yet confirmed.
7. A separate eight-token `python/merlin/glyph_math_lab.py` grammar. This currently overlaps with, but is not the same registry as, the larger XMG JSON registry.
8. Ideonomy candidate generation and a multi-objective research optimizer.
9. A dynamic model-compression proposal covering quantization, specialist modules, conditional loading, and Pareto evaluation.

**Important integration gap:** the eight-token glyph lab, the XMG registry, the Foundry's primitive registry, the normalizer, Lean laws, and Hermes/CACE evidence are not yet demonstrated as one canonical compile-and-verify path. The next task is integration and measurement, not adding hundreds of new glyphs.

## Research comparison and ranked direction

| Rank | Candidate foundation | What it contributes | Merlin decision |
|---:|---|---|---|
| 1 | Typed, canonical DAG/IR + hash-consing | One representation shared by front ends and back ends; shared subexpressions stored once | Adopt as core |
| 2 | E-graphs and equality saturation | Retain equivalent forms without destructive rewrite ordering; extract by explicit cost model | Adopt in bounded, guided form |
| 3 | Lambda calculus / typed functional core | Small compositional semantics for functions, application, and execution | Use as semantic kernel, not the whole data model |
| 4 | Category-theoretic composition | Explicit objects, morphisms, composition, identity, functors and natural transformations | Use where the required structures exist; avoid empty category-theory decoration |
| 5 | Dependent/refinement types + units and effects | Encode dimensions, units, domains, preconditions, capabilities, and effect boundaries | Adopt incrementally; high value for CAD/physics/wiring |
| 6 | Graph rewriting / term rewriting | Transform diagrams and structured objects while retaining derivation paths | Adopt for geometry, circuits, workflows, and symbolic graphs |
| 7 | Tensor networks / multilinear representations | Efficient contractions and structured representations in quantum, physics, and scientific computing | Domain-specific backend |
| 8 | ZX-calculus and other diagrammatic calculi | Graphical rewrite systems with semantics; useful for quantum circuits and compositional diagrams | Domain-specific module; not the universal core |
| 9 | N-ality / representation-theoretic invariants | Center-charge and representation labels can classify sectors and constrain transformations in gauge/representation theory | Add as a domain adapter and invariant family, not a universal opcode |
| 10 | Ideonomy and combinatorial enumeration | Generate cross-domain hypotheses from typed slots and relation templates | Use as discovery front end, with aggressive pruning |

### Why this ranking

**The DAG plus typed IR is the most practical starting point.** It avoids repeating identical subexpressions, gives every downstream tool a stable contract, and supports deterministic serialization and hashing. Recent symbolic-computation work on hash-consing reports workload-dependent memory and runtime gains, including up to 2× lower memory and up to 100× faster numerical evaluation in selected large models; these are external results, not Merlin performance claims. Hash-consing can also cost extra lookups for short-lived nodes, so Merlin must benchmark its own workload mix.

**E-graphs are the most promising optimization layer**, because they can retain many equivalent expressions and choose a low-cost form later. But unconstrained equality saturation can consume enormous memory: published work reports multi-gigabyte growth and failed searches on complex optimization tasks. Merlin must therefore use cost-guided rules, budgets, sketches, and early extraction—not unbounded saturation.

**Lambda calculus is a compact computational foundation**, but real Merlin objects also include graphs, arrays, geometry, circuits, probability distributions, proof terms, and effectful jobs. Represent those as typed data structures with functional transformations, rather than forcing all data into nested lambda terms.

**Category theory provides compositional semantics**, not a magic speedup. Use it to state which maps compose, what identities and products mean, and when adapters preserve structure. Require concrete types and laws.

**N-ality is important but specialized.** In gauge and representation theory it labels representations by their transformation under a group's center (for example, SU(N) center charge modulo N). It can support symmetry-sector indexing, selection rules, and invariant checks in the relevant physics modules. It should not be generalized into a generic notion of “N-dimensionality” or used as an unexplained universal mathematical token.

## Proposed MIR layers

### 1. Surface syntax

- XMG glyph notation for compact human expression.
- Plain text / JSON / Python / Lean importers.
- Stable textual aliases so users do not need special fonts or Unicode input.
- A glyph is only a rendering of a canonical operator ID; the glyph shape never carries semantic authority.

Example (illustrative):

```text
⟦ COMPOSE ; MAP(f), MAP(g) ; A → C ; assumptions ; domain ⟧
⟦ PROVE ; composition_associative ; Prop ; typed_maps ; Lean ⟧
⟦ OPT ; equivalent_forms ; constraints ; cost_model ; compiler ⟧
```

### 2. Canonical typed AST/DAG

Each node must carry:
- stable operator ID and schema version;
- type variables, input/output types, units, and coordinate frames;
- assumptions and side conditions;
- exact/approximate/partial/undefined semantics;
- purity/effect classification;
- child-node content hashes;
- source and provenance links.

Use hash-consing: identical canonical nodes map to one stored node. Preserve DAG sharing rather than expanding into duplicate trees. Canonical serialization must be deterministic and independent of display glyphs.

### 3. Type, unit, and effect system

Initial type families:
- scalar, vector, matrix, tensor, function, product, sum, finite set, graph, hypergraph;
- group, ring, field, module, algebra, category, representation;
- manifold, chart, frame, geometric object, mesh, circuit, netlist;
- probability distribution, interval, uncertainty, measurement;
- proposition, proof term, evidence receipt, execution plan.

Units and dimensions must be explicit. Coordinate-frame changes must be explicit. Pure transformations are distinct from file writes, network access, code execution, simulations, and hardware actions. Effectful operators require a separate capability and resource-budget check.

### 4. Rewrite/equivalence engine

- Start with the existing size-decreasing, type-preserving XMG-1C rules.
- Add declarative patterns only after rule semantics and matching are specified.
- Attach a Lean theorem or explicit finite-test status to every rule.
- Track assumptions and side conditions with each rewrite.
- Use XMG-1E critical-pair analysis for overlaps.
- Use e-graphs for equivalence classes only with per-task node, iteration, time, and memory budgets.
- Extract a result only after verifying type preservation and all applicable side conditions.

Never equate “same normal form under current rules” with universal mathematical equivalence.

### 5. Cost-aware extraction

Select an implementation using a transparent cost vector:

`cost = (peak_RSS, CPU_time, wall_time, bytes_read, bytes_written, precision_error, verification_cost)`

Hard constraints come first. Then retain a Pareto frontier rather than hiding quality tradeoffs in one score. The cost model is calibrated from real Avrea and OCI measurements, not guessed constants.

### 6. Execution backends

- Lean: formal obligations and theorem checking.
- Python/SymPy: symbolic algebra and prototypes.
- NumPy/SciPy: numerical linear algebra and scientific routines.
- C++: hot paths, sparse data structures, graph kernels.
- ngspice: circuit simulation.
- FreeCAD/OpenSCAD: geometry and assemblies.
- Tensor/quantum adapters: tensor contractions and diagrammatic rewrite systems.
- Avrea: bounded build, benchmark, and simulation workers.
- OCI: independent verification and persistent services.
- CACE: separate evidence qualification.

No backend may self-qualify its own output.

## RAM and CPU reduction: ranked implementation sequence

1. **Canonical DAG + hash-consing.** Store repeated subexpressions once; fingerprint canonical nodes; measure memory per unique node.
2. **Content-addressed result cache.** Key on IR hash, schema, compiler, adapter, dependency lock, input hashes, parameters, seed, precision, and environment. Cache only deterministic results or seed-bound stochastic results.
3. **Incremental dependency invalidation.** Recompute only nodes whose actual inputs or relevant versions changed; never clear a whole cache as a routine workaround.
4. **Bounded e-graph search.** Limit e-nodes, iterations, wall time, and RSS; use sketches and task-specific rule sets; stop when marginal improvement falls below cost.
5. **Cheap-first pipeline.** Type/unit checks → exact symbolic simplification → small counterexample search → numerical estimate → high-fidelity simulation → Lean proof where applicable.
6. **Sparse and lazy structures.** CSR/CSC for sparse matrices/graphs; lazy views for large tensors/meshes; avoid materializing dense intermediates unless required.
7. **Batch and locality-aware scheduling.** Batch compatible work; minimize repeated serialization and movement; keep small hot caches in memory and spill cold immutable artifacts to disk.
8. **Model routing and dynamic loading.** Use the smallest sufficient model/module; load specialists on demand; unload by measured memory pressure; escalate on low confidence or failed verification.
9. **Precision ladder.** Start with cheap precision for exploration; refine only candidates that survive filters; retain error bounds and validate final candidates at required precision.
10. **Prompt/context compression.** Retrieve only relevant canonical nodes, definitions, proofs, and artifacts instead of repeatedly injecting entire project history.

No optimization is accepted merely because it looks elegant. Each must beat a baseline on the same pinned workload and retain task-quality and verification gates.

## N-ality and other mathematical structures: research protocol

Create explicit, separately typed modules for:
- finite-group and Lie-group actions;
- center, center charge, representation labels, characters, and tensor-product decomposition;
- symmetry and conserved quantities;
- invariant rings and polynomial invariants;
- category/functor/monoidal structure;
- graph homology and topological invariants;
- tensor-network contraction order and complexity;
- geometric algebra and Clifford representations;
- hypergraphs and higher-order relations;
- scale-space, fractal descriptors, and lacunarity.

For each structure:
1. define its mathematical object and exact assumptions;
2. state its domain-specific use case;
3. enumerate known equivalent representations;
4. derive candidate rewrite rules;
5. test small finite examples and counterexamples;
6. prove algebraic laws in Lean when tractable;
7. compare resource use and predictive value on held-out tasks;
8. keep failed and negative results in the evidence ledger.

Do not assume that a new glyph, unusual notation, or visual pattern is a new mathematical discovery. Novelty requires literature comparison, precise definitions, and a falsifiable distinction from known structures.

## Ideonomy enumeration design

Use typed idea slots rather than unconstrained Cartesian-product enumeration:

`(domain, object, relation, transformation, invariant, scale, assumptions, experiment, proof_route)`

Generation pipeline:
1. enumerate only type-compatible tuples;
2. reject unit/domain mismatches;
3. normalize against known definitions and equivalences;
4. retrieve literature and prior Merlin claims;
5. generate a minimal counterexample search;
6. ask a skeptic agent to find hidden assumptions and known results;
7. estimate information gain, reproducibility, verification cost, and compute;
8. send only high-value survivors to Avrea/OCI;
9. require CACE to check exact evidence before status changes.

Novelty, feasibility, truth, and utility remain distinct fields. Scores prioritize investigations; they do not establish truth.

## Benchmark program: prove that the language saves resources

Build a pinned benchmark corpus with:
- arithmetic and polynomial rewrite tasks;
- typed function-composition and diagram-rewrite tasks;
- sparse matrix and graph workloads;
- coordinate and geometric transformations;
- tensor contraction planning;
- small circuit/netlist transformations;
- Lean proof-obligation generation;
- repeated multi-domain subexpressions to test DAG reuse;
- ideonomy enumeration with known positive and negative controls.

Compare these implementations on identical inputs:
A. baseline Python trees; B. canonical DAG without rewriting; C. DAG + memoization/cache; D. bounded e-graph; E. guided e-graph + cost-aware extraction; F. C++ sparse backend where appropriate.

Record:
- exact output and proof equivalence;
- peak RSS and bytes allocated;
- CPU time and wall time;
- unique nodes versus expanded nodes;
- cache hit rate and invalidation correctness;
- e-graph node count and rewrite count;
- serialization size and transfer time;
- numerical error and precision;
- verifier time and proof success;
- quality on held-out tasks.

Use warm and cold cache runs separately. Fix seeds and versions. Run repeated trials and report distributions, not just best-case timings. The acceptance gate is no correctness or verification regression and a measurable Pareto improvement on at least one target workload without unacceptable regressions elsewhere.

## Implementation milestones

### P0 — reconcile the existing language sources
- Treat `MERLIN_XMG1_GLYPH_REGISTRY_V0.1.json` as the current proposed canonical registry.
- Mark `glyph_math_lab.py` as a legacy/minimal experimental grammar until it consumes the canonical registry or is explicitly retired.
- Reconcile operator names and glyph collisions across XMG, Foundry, normalizer, and Lean.
- Generate registry documentation and tests from one canonical source.
- Add schema validation and stable registry digest tests.

### P1 — typed canonical DAG
- Introduce immutable canonical node records and deterministic serialization.
- Add structural hash-consing and DAG-aware fingerprints.
- Preserve provenance and exact type/unit/frame information.
- Add tree-to-DAG and DAG-to-display adapters.

### P2 — verified rewrite pipeline
- Connect existing Foundry and normalizer to canonical DAG nodes.
- Export rewrite derivations to Lean obligations.
- Add explicit status for proposed, tested, formally proved, independently qualified.
- Add critical-pair and bounded e-graph integration.

### P3 — measured cost optimizer
- Implement benchmark harness and baseline corpus.
- Calibrate extraction costs from Avrea and OCI runs.
- Add resource budgets and early-stop policy.
- Verify cache correctness under schema, dependency, and input changes.

### P4 — domain adapters
- Algebra/linear algebra and units first.
- Geometry/coordinate frames and CAD next.
- Circuits/netlists/ngspice next.
- Tensor, quantum ZX, and N-ality/representation-theory adapters as specialized research tracks.

### P5 — CACE and dashboard integration
- Register each language version, rewrite rule, proof, benchmark, and backend receipt as canonical artifacts.
- Bind receipts to exact commit, source digest, toolchain, input hash, and verifier identity.
- Display resource savings and epistemic status separately.
- Do not automatically promote a hypothesis or authorize execution.

## Evidence status and next executable tasks

This document is a research synthesis and implementation plan. It does **not** claim that:
- XMG is a proven universal language;
- the glyph registry is already the only runtime registry;
- the existing Lean law file compiles;
- e-graph optimization is integrated;
- any RAM/CPU savings have been measured;
- Avrea or OCI has run these new benchmarks;
- CACE has independently qualified this proposal.

Next ranked implementation tasks:
1. Add canonical-registry schema validation and detect divergence from `glyph_math_lab.py`.
2. Implement immutable typed DAG with hash-consing and deterministic canonical hashes.
3. Add tree-vs-DAG benchmark fixtures and memory/CPU measurement.
4. Connect current size-decreasing rewrites to the DAG and emit proof-obligation manifests.
5. Build a small bounded equality-saturation prototype with a strict node budget and guided extraction.
6. Run identical benchmark jobs on Avrea and the separate OCI verifier; store raw logs and manifests.
7. Have CACE independently verify hashes, toolchain, test reports, Lean receipts, and benchmark manifests.

## Research references

- Tate, Stepp, Tatlock, Lerner, **Equality Saturation: A New Approach to Optimization**, POPL 2009. https://www.cs.cornell.edu/~lerner/papers/popl09.html
- Willsey et al., **egg: Fast and Extensible Equality Saturation**, Communications of the ACM. https://doi.org/10.1145/3815481
- Nandi et al., **Rewrite Rule Inference Using Equality Saturation**, OOPSLA 2021. https://doi.org/10.1145/3485496
- Arbore, Cheung, Willsey, **Optimism in Equality Saturation**, PLDI 2026. https://doi.org/10.1145/3808302
- Merckx et al., **E-Graphs as a Persistent Compiler Abstraction**, arXiv 2026. https://arxiv.org/abs/2602.16707
- **The Lambda Calculus**, Stanford Encyclopedia of Philosophy. https://plato.stanford.edu/entries/lambda-calculus/
- Lehmann et al., **Vy ZX: Formal Verification of a Graphical Quantum Language**, TOPLAS 2026. https://doi.org/10.1145/3807780
- Patrick Gunkel / MIT, **Ideonomy: The Science of Ideas**. https://ideonomy.mit.edu/

The e-graph literature also documents a critical caveat: unguided saturation can consume tens of gigabytes on difficult workloads. Merlin's design therefore treats search budgets and guided extraction as first-class semantics, not optional tuning.

---
**Design rule:** the canonical typed structure is the language; glyphs are its notation; adapters are its reach; proofs and measurements are its credibility.
