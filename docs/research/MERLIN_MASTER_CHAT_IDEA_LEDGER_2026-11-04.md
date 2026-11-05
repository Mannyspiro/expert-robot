# Merlin Master Chat-Idea Ledger — 2026-11-04

**Purpose:** durable, deduplicated register of Merlin-relevant ideas recovered from project conversations and inspected repository artifacts. This is a research and implementation ledger, not a claim that every idea is implemented or validated.

**Guiding principle: capability grows, authority never expands.**

## 0. Evidence labels

- **IMPLEMENTED / EVIDENCED:** corresponding code, document, commit, proof receipt or test evidence is present and inspectable. The status is limited to exactly what that evidence establishes.
- **DESIGNED / UNQUALIFIED:** architecture or partial implementation exists, but required qualification is incomplete.
- **RESEARCH HYPOTHESIS:** candidate idea, analogy, model or research direction requiring definition, literature review, falsification, experiment or proof.

A chat mention is provenance for an idea, not evidence that the idea is true. A citation establishes provenance, not correctness. A Lean theorem proves only its exact statement under its assumptions. A simulation establishes only a result for its declared model and inputs. A CAD render is not manufacturing approval.

This ledger excludes unrelated conversation topics and consolidates Merlin, CACE, Expert Robot, Hermes, MCFC, Avrea, mathematics, formal verification, public research discovery, CAD/wiring and scientific-engineering threads.

## 1. Product identity and system boundaries

### 1.1 Merlin as a research-to-engineering workbench
**Status: DESIGN with substantial IMPLEMENTED foundations.**

Merlin's core loop is:

observe → retrieve → normalize → enumerate → hypothesize → challenge → model → simulate → verify → design → review → release.

Merlin owns the research workspace, ideonomy, knowledge graph, equation atlas, hypothesis generation, experiment planning, visualization and project memory. It may propose code, proofs, models and engineering artifacts. It does not self-approve, self-merge or expand its own authority.

### 1.2 Component responsibilities

| Component | Responsibility | Boundary |
|---|---|---|
| Merlin | Research, ideonomy, knowledge graph, equation atlas, hypotheses, visualization, project memory | Candidate generator and integrator; not sole verifier |
| Expert Robot | Execution/runtime, bounded tool broker, repository work, model serving, sandbox and verification orchestration | Executes only granted capabilities |
| Hermes | Optional coding/research worker and agent runtime | Inherits Expert Robot's tool broker and sandbox constraints |
| CACE | Typed contracts, policy/capability registry, evidence verification, formal methods and qualification | Independent checks; promotion requires explicit authority |
| MCFC | Virtual compute fabric: CPU/RAM/GPU inventory, budgets, scheduling, leases and telemetry | Resource admission, not geometry or result qualification |
| Avrea | Preferred reproducible build/test worker when available | A receipt is tied to a specific revision and environment |
| OCI verifier | Separate verification lane when configured | Not presumed active |
| Academic Spider / Research Miner | Public-source discovery, provenance, metadata extraction and deduplication | Discovery is not endorsement or truth |

Do not conflate MCFC compute-resource leases with XMG coordinate-frame transforms; Merlin candidate generation with CACE qualification; agent review with independent verification; citations with proofs; or visual CAD with engineering release.

### 1.3 Governance invariants
- Least privilege, typed capabilities, explicit approvals and bounded execution.
- Candidate changes occur in isolated branches/sandboxes.
- Preview diffs, immutable receipts, commit hashes, rollback references and human approval.
- Fail closed when resource capacity, evidence, permissions or assumptions are unknown.
- Failed and inconclusive results remain visible.
- Never silently convert unknowns into defaults.
- No autonomous production writes, merge, deployment or promotion.

## 2. Mathematics and representation research

### 2.1 Multi-representation mathematics
**Status: IMPLEMENTED foundation; broader generalization DESIGN / HYPOTHESIS.**

Represent one mathematical object through multiple simultaneous views rather than forcing every problem into one coordinate system. Candidate views include Cartesian, polar, cylindrical, spherical, barycentric, homogeneous/projective, affine, local coordinate charts, curvilinear frames, manifold atlases, spacetime coordinates, algebraic, matrix, tensor, graph, spectral and learned latent representations.

A view transition is a typed map with domain/codomain, units, assumptions, lossiness, invertibility, preserved structure and evidence. Multiple coordinate descriptions of one object share a stable object identity.

Candidate object-view graph: Object → View → Map → Invariant → Evidence.

Preservation is never assumed: each map declares what it preserves (distance, angle, incidence, orientation, topology, metric, spectrum, energy, etc.) and tests or proofs are attached.

### 2.2 Number systems and geometric algebra
**Status: RESEARCH HYPOTHESIS, with rotation/representation foundations IMPLEMENTED.**

Enumerate and compare real and complex numbers; split-complex and dual numbers; quaternions and dual quaternions; octonions (respect non-associativity); Clifford/geometric and projective geometric algebras; hyper-dual numbers; p-adics; modular and tropical systems; matrices, tensors and exterior algebra.

Separate algebraic dimension, geometric dimension, embedding dimension and representation dimension. Do not assume eigenvalues, determinants, inverses or multiplication properties exist in every algebra. State the algebra and operator domain before applying spectral concepts.

Existing repository foundations include representation graphs, rotation representation comparisons and spherical holonomy work. Preserve exact assumptions and tested equivalences; do not generalize a verified 3D result to arbitrary dimensions without proof.

### 2.3 Geometry, topology, transformations and spacetime
**Status: IMPLEMENTED slices plus HYPOTHESES.**

Research Euclidean, affine, projective, hyperbolic, elliptic, symplectic, contact and discrete geometry; algebraic, differential, computational, knot/link and persistent topology; rotations, reflections, translations, affine/projective/conformal maps; Fourier, Laplace and wavelet transforms; Lie groups/algebras, tensors, differential forms and gauge transformations; eigenvalues, eigenspaces, singular values, tensor decompositions and spectral graph theory; 2D/3D/4D/5D coordinate systems and mappings.

Distinguish frame changes from physical time evolution. Treat block-spacetime projections, time crystals and higher-dimensional spacetime analogies as hypotheses until the physical model, equations, observables and falsifiers are explicit.

### 2.4 Xenomathematics and glyph systems
**Status: RESEARCH HYPOTHESIS with XMG-1 implementation slices.**

Explore notation systems that do not assume conventional human symbols:
- glyphs as typed operators, operands, transformations, constraints or composable programs;
- grammar, typing, operational semantics, evaluation and error rules;
- composition, identity, inverse, associativity where applicable, equivalence and rewrite systems;
- glyph families encoding multi-operation structures or geometric transformations;
- visual/spatial mathematical writing where placement itself has formal semantics.

A glyph is not meaningful merely because it looks geometric. Define syntax, semantics, type, domain, codomain, evaluation rule and laws. Build parsers, normalizers and proof obligations from the same grammar.

Current XMG-1 work includes typed expression structures, bounded candidate generation, finite rewrite normalization, critical-pair exploration, a glyph registry and Lean laws. This is not yet a universal mathematical language or general discovery engine.

### 2.5 Ideonomy and lacunarity
**Status: DESIGN with implementation foundations; novelty scoring remains HYPOTHESIS.**

Represent ideas as a typed hypergraph. Vertices include objects, claims, models, methods, definitions, datasets and open questions. Hyperedges include uses, generalizes, specializes, contradicts, maps-to, equivalent-under-assumptions, bounds, implements and supported-by.

Gap categories:
1. knowledge gap — missing definition, result or source;
2. connection gap — relationship not yet investigated;
3. representation gap — inefficient or missing formal representation;
4. proof gap — precise claim lacks derivation;
5. measurement gap — claim lacks an adequate observable or experiment;
6. translation gap — no reliable bridge from mathematical model to simulation/engineering;
7. verification gap — no independent reproduction or proof receipt.

Enumerate concepts, relations, constraints, alternative representations and candidate combinations. Literature search and counterexample search must precede novelty claims. A missing local graph edge does not imply a novel discovery.

Lacunarity is a measure of spatial heterogeneity under a declared window/scale procedure, not a universal quality score. Record window, scale, mask, grid, boundaries, sampling and uncertainty. Compare designs under matched materials, mass/density, envelope, loading and boundary conditions.

### 2.6 Superorganism / collective mathematics
**Status: RESEARCH HYPOTHESIS.**

Model collective systems as explicit graphs and dynamical systems: agents, cells, modules, tasks and resources; local interaction/update rules and global objective functions; distributed optimization, consensus, network flow and network control; coupled oscillators, synchronization, phase changes and stability; information theory, statistical mechanics, reaction-diffusion and multiscale feedback. Compare ant-colony, microbial, neural and engineered swarms only through sourced operational definitions.

Distinguish emergence from analogy, correlation from causation, and optimization from stability/robustness. Specify agents, state, topology, update rules, boundaries, observables and falsifiable predictions.

## 3. Formal mathematics and Lean

### 3.1 Proof Strategy Observatory
**Status: DESIGNED / UNQUALIFIED; research atlas and strategy config committed on PR #75.**

Merlin should learn how to prove, not merely collect proof scripts. For every candidate tactic sequence record theorem ID and normalized statement hash; assumption hash and domain tags; tactic sequence, simp set and Aesop rules/priorities; success/failure stage; elapsed time, heartbeats, peak memory; Lean and Mathlib versions, import closure and environment; source commit and proof hash; axiom dependencies and sorry status.

Keep failed attempts. Require multiple observations and a held-out set before adaptive ranking. Compare strategies on identical theorem statements, assumptions, toolchains and environments. Preserve the original proof as rollback.

Initial goal profiles: structural equality; closed numerics; polynomial identities; integer/natural linear arithmetic; ordered inequalities; nonlinear inequalities; coordinate geometry; theorem reuse; bounded proof search.

### 3.2 Large-scale formalization architecture
**Status: DESIGN / RESEARCH, informed by recent public projects.**

Use theorem dependency DAGs and proof blueprints; separate stable theorem statements from proof bodies; natural-language theorem summaries linked to Lean declarations; semantic/global premise retrieval; task leases and bounded parallelism; build-aware module boundaries; exact statement comparison; proof/source provenance; and integration testing through successor theorems, not compilation alone.

Recent research inputs:
- AutoformBot reports a multi-agent Lean 4 pipeline and an open textbook-scale library: https://ai.meta.com/research/publications/autoformbot-formalizing-mathematics-at-scale/
- LeanSearch v2 studies global premise retrieval for whole theorem proofs: https://arxiv.org/abs/2605.13137
- TheoremGraph links informal and formal theorem dependencies: https://arxiv.org/abs/2606.25363
- T² evaluates generated theorems through dependent successor-theorem compilation: https://aclanthology.org/2026.acl-industry.150/
- M2F separates statement compilation from proof repair: https://arxiv.org/abs/2602.17016
- NanoProof studies reproducible, compute-efficient Lean proving: https://arxiv.org/abs/2610.11605
- Goedel-Architect uses iteratively refined proof blueprints: https://goedelarchitect.github.io/
- LeanArchitect synchronizes blueprint metadata with Lean declarations: https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ITP.2026.25

These systems are research inputs, not automatically superior components. Merlin should reproduce a small controlled comparison before adopting them.

### 3.3 Formal integrity gates
Classify each result independently:
1. statement parses/elaborates;
2. proof term kernel-checks;
3. no sorry/sorryAx;
4. axioms and dependencies enumerated;
5. theorem assumptions match intended claim;
6. source and toolchain pinned;
7. dependent theorems compile;
8. independent review/reproduction status recorded;
9. empirical/model adequacy assessed separately when relevant.

Do not reject standard axioms automatically; report them and evaluate whether they match intended foundations.

### 3.4 Existing mathematical proof tracks
- Exact rational geometry: dot products, cross products, squared distances and vector extensionality.
- Multi-representation rotations: complex, matrix, quaternion and geometric-algebra comparisons.
- Spherical holonomy: preserve exact domain and assumptions.
- XMG composition and rewrite termination/confluence.
- THTG/UFT: reconstruct action/source equations; correct Page-curve derivation; establish finite maximum only under exact hypotheses; resolve 5D coupling dimensions and curvature-invariant basis; derive beta functions from fixed setup; independently reproduce fixed point and stability matrix; formalize conditional theorems and audit axioms.
- Numerical FRG, lattice Page curve, Standard-Model-shifted fixed-point coordinates and cosmological MCMC remain distinct research tasks.

A conditional theorem is not validation of a physical theory. Do not tune equations to preserve a desired fixed point.

## 4. Physics and cross-disciplinary science
**Status: RESEARCH PROGRAM.**

Candidate areas: classical mechanics, variational principles, PDEs and continuum mechanics; general relativity, differential geometry, black-hole thermodynamics and quantum information; statistical mechanics, stochastic systems and non-equilibrium dynamics; electromagnetism, optics, signal processing and control; biological complexity, reaction networks, brain/gut/vagus models and multiscale physiology; biomimicry, evolutionary systems and morphology; material behavior, thermal/fluid/acoustic models and energy systems.

For every model, record equations, units, assumptions, boundary/initial conditions, parameter sources, solver, discretization, uncertainty, observables and validation data. Do not promote a biological or medical simulation to a clinical claim or wet-lab instruction.

## 5. Equation Atlas and simulation
**Status: IMPLEMENTED foundation; broad research coverage unqualified.**

Each equation entry should contain stable ID/title; normalized and source notation; variable definitions, units and dimensions; assumptions/domain; invariants, symmetries and limiting cases; derivation/source and citation; proof status/dependencies; numerical method, solver and parameters; expected observables and falsifiers; limitations/uncertainty; XMG glyph/operator mapping; linked engineering realization; experiment/evidence receipt and revision hashes.

Equation pipeline: source → extract → normalize → dimensional-check → symbolic-check → prove → simulate → compare → receipt.

A simulation receipt binds exact source, model, solver, parameters, seed, code revision and outputs.

## 6. CAD, wiring, MCFC and physical engineering

### 6.1 Shared Engineering IR
**Status: IMPLEMENTED foundation; full qualification incomplete.**

Use one typed source of truth for project/revision identity; parts, instances, materials and tolerances; dimensions, units, coordinate frames and transforms; faces/topology, constraints, joints and degrees of freedom; pins, ports, nets, connector pinouts and harnesses; voltage/current/power/signal domains; thermal/mechanical fields and boundary conditions; simulations, measurements and evidence receipts.

Generate geometry, drawings, wiring/netlists and simulation inputs from the same revisioned IR. A diagram is not a substitute for a connectivity graph.

### 6.2 Mechanical CAD and kinematics
**Status: DESIGN with current geometry/assembly foundations.**

Next work: multi-instance assembly with stable instance IDs; rigid/articulated joints; constraint graph and degrees of freedom; forward/inverse kinematics and frame-chain validation; collision broad phase then exact geometry; tolerance stack-up and uncertainty; parametric OpenSCAD export, then other adapters; visual drafting linked to exact geometry and constraints.

AABB interference is conservative screening, not exact collision or proof of fit.

### 6.3 Electrical wiring and harness routing
**Status: IMPLEMENTED structural routing/IR foundations; engineering qualification incomplete.**

Use typed parts/pins/nets; transform pin locations through explicit frames; route a net as a graph embedded in 3D; attach geometry and evidence hashes. Current deterministic orthogonal routing and AABB keep-outs are candidate generation only.

Before real hardware/fabrication, independent qualified processes must validate authoritative datasheets, pinout, wire gauge, insulation, ampacity/derating, voltage domains, creepage/clearance, impedance/return paths, EMC, thermal/fault behavior, bend radius, strain relief, tolerances, manufacturability and applicable standards. Missing data blocks qualification.

### 6.4 MCFC virtual compute fabric
**Status: IMPLEMENTED reference contracts and scheduler; durable distributed execution remains unqualified.**

MCFC handles typed CPU/RAM/GPU capacity, workload requests, budgets, bounded admission, expiring/revocable leases and telemetry. It does not handle geometry transforms or result approval.

Keep unknown GPU capacity unknown. Refresh capacity for each environment. A lease grants bounded execution only. Future work: durable multi-process leases, heartbeats, worker execution, preemption, fairness/aging, queue persistence and cancellation.

### 6.5 CAD ↔ simulation ↔ evidence loop
One project revision and geometry hash must flow through CAD, netlist, route, simulation and evidence. CACE independently verifies the artifact, inputs, constraints and tests. A successful compute lease does not qualify the engineering result.

## 7. Academic Spider / public-source research
**Status: IMPLEMENTED metadata discovery foundations; broad crawl and professor inventory incomplete.**

Index public professor and laboratory sites across mathematics, physics, engineering, computer science, materials, biology and interdisciplinary science. Collect public lecture notes, preprints, papers, software, datasets, open problems and research pages. Normalize canonical URLs, DOI/ORCID/OpenAlex IDs where available. Link works, researchers, institutions, topics and citation relations. Extract claims only with provenance, passage/section, retrieval timestamp and rights metadata. Connect source records to equation atlas, theorem graph, hypotheses and project tasks.

Existing AcademicSpider v0.1 query generation, public source store v0.2, OpenAlex adapter v0.3 and Academic graph v0.4 are present in the repository. OpenAlex topic labels are discovery metadata, not ground truth. Professor-page crawling must be explicitly public and respect site terms, robots rules, rate limits and licenses. Search indexing does not grant redistribution rights; do not bypass authentication or paywalls.

Seed categories: mathematics (geometry, topology, algebra, analysis, number theory, combinatorics, applied math); physics (mathematical physics, GR, QFT, condensed matter, statistical mechanics, computational physics); engineering (robotics, control, continuum mechanics, CAD, computational mechanics, electrical systems); cross-domain (materials, biophysics, information theory, scientific computing, formal methods).

## 8. AI models, local-first inference and compute efficiency
**Status: DESIGN with selected infrastructure implemented; model quality claims must be benchmarked.**

Architecture: local-first replaceable core model; specialists/adapters loaded on demand; model and adapter manifests with hashes, license, base-model compatibility and resource estimates; quantization, structured sparsity, low-rank compensation, context/KV compression, retrieval and bounded context; capability-aware router estimating expected benefit against load/switching cost; deterministic fallback/escalation when confidence is low or verification fails; clean unload and memory-pressure handling.

Do not assume quantization or sparsity improves speed on a given CPU. Benchmark quality, latency, memory, disk, load overhead and fallback. Keep Pareto alternatives visible.

CPU compute research: cache-aware matrix/tensor kernels; runtime SIMD detection; vectorization/cache tiling; bounded thread pools and scheduling; quantized integer dot products and attention primitives; correctness/numerical error before throughput; ideonomy over tile sizes, worker counts, precision and data layout; MCFC/CACE promotion only after reproducible measurements.

### Parrondo-inspired strategy selection
Treat switching between strategies as an empirical hypothesis, not a guaranteed effect. Compare A, B, fixed alternation, randomized alternation and context-conditioned routing on identical tasks/seeds. Include switching overhead, p50/p95 latency, memory, failures and quality. Promote only if the hybrid beats the best standalone baseline by a predeclared margin without quality or authority regression.

## 9. Research Council and independent challenge
**Status: DESIGN with council/runtime foundations.**

Use a small heterogeneous council: implementer (minimal proposed patch); independent challenger (separate review and adversarial tests); performance analyst (cost/quality measurements); verifier (tests, proofs and invariants); integrator (reconcile and record dissent); human maintainer (merge/promotion authority).

Provider/model diversity may reduce correlated errors but does not establish correctness. Count independently reproduced findings, not votes. Council debate is a hypothesis-generation and review mechanism; it cannot waive failed gates.

## 10. Visualization, learning and interaction
**Status: DESIGN / IMPLEMENTED slices.**

UI should connect equation, proof, dependency graph, coordinate views, CAD, netlist and simulation plots; interactive 2D/3D/4D/5D transformations and time-dependent frames; multiscale graphs and geometry; glyph/operator visualizations with inspectable semantics; compact mobile-friendly control room and evidence states; accessible labels and short explanations.

The educational pathway is also relevant: first-principles mathematics tutor with adaptive progression, short explanations, visual/interactive demonstrations, retrieval practice, mistake tracking and spaced repetition. Separate lessons from quizzes; avoid advancing notation before the learner has acquired it. This is a product module, not evidence for research claims.

## 11. Research problem reframing protocol
1. State the original question precisely.
2. Identify mathematical objects, domains, variables, assumptions and constraints.
3. Enumerate analogous formulations in other disciplines.
4. Build an explicit mapping: source concept → target concept → preserved invariants → lost information → boundary conditions.
5. Search for counterexamples and known impossibility results.
6. Test a small exact case before generalization.
7. Formalize the mapping and its conditions.
8. Record what was learned and where the analogy breaks.

An analogy is useful only when the mapping is explicit. Do not transfer a theorem across domains merely because diagrams look alike.

## 12. Repository and PR status snapshot

Inspected on 2026-11-04 from GitHub:

| PR | Branch | State | Contents | Evidence boundary |
|---|---|---|---|---|
| #67 | feat/merlin-hermes-kokoro-qualified-20261102 | Open draft, unmerged | Hermes/Kokoro/model/compute integration foundation | Prior handoff reports specific Avrea/C++/Kokoro passes; NousCoder inference and full council playback remained unqualified |
| #70 | feat/merlin-academic-spider-v01-20261103 | Open draft, unmerged | Research graph, hypothesis, CAD/electrical foundation | Preserve individual test/run evidence; do not infer full system qualification |
| #72 | feat/merlin-real-world-equation-atlas-v01-20261104 | Open draft, unmerged | Equation Atlas 001–080, XMG simulation and multi-frame contracts | Earlier report: 001–030 Avrea validated; 031–040 awaiting validation; 40 authored entries were not verified scientific claims; Lean/empirical validation absent at that report |
| #75 | feat/merlin-lean-proof-optimization-atlas-20261104 | Open draft, unmerged | Lean optimization atlas and tactic profiles | Profile JSON parsed; GitHub Actions pushes failed and no job detail was returned; no new proof or benchmark claimed |

The inspected #75 repository tree contains Python Merlin modules for academic graph/spider, source store, idea/hypothesis ledger, equation atlas, simulations, geometry/frames, CAD assemblies, wiring/netlist, MCFC/CPU fabric, telemetry, council, Lean receipts and research; Lean sources for geometry, equation atlas, fractal engineering, wire qualification, XMG composition and audit; C++ research engine, strategy discovery/planning/qualification, route memory, benchmark executor and math service; and extensive docs for ideonomy, lacunarity, glyphs, CAD/wiring, MCFC, compute, equation atlas and orchestration.

This is an inventory observation, not proof that every module builds or every documented capability is live. PR #75 descends from #72; #72 descends from #70; #70 descends from #67. Keep this chain visible and do not merge or overwrite earlier branches without reconciliation.

## 13. Consolidated implementation priorities

### P0 — Reconcile and establish one source of truth
Inspect PR ancestry, changed files, conflicting versions and default-branch state; identify duplicate/parallel implementations; map every documented capability to code, tests and receipts; reconcile failed PR #75 CI; generate a current project inventory and status matrix.

### P1 — Proof Strategy Observatory
Theorem/proof dependency DAG; statement and assumption hashes; theorem search/premise retrieval; tactic-attempt observation store; benchmark harness with fixed toolchain; successor-theorem integration tests; axiom and sorry audit; independent baseline comparison.

### P2 — Typed object-view / coordinate graph
Canonical object identity; multiple typed coordinate/algebra views; transformations with explicit invariants and lossiness; numerical/property-based tests and Lean laws; link to CAD frame graph and equation atlas.

### P3 — Research graph and Spider Mine completion
Merge public academic metadata with manually curated public professor sites; attach source passages, license and retrieval provenance; link papers to claims, equations, theorems and hypotheses; avoid unverified site-count claims; start with a small reviewed seed set and expand by evidence.

### P4 — Mathematical-to-engineering bridge
One revisioned Engineering IR; exact frame transforms and constraints; assembly joints/kinematics; CAD/netlist/simulation shared hashes; independent CACE evidence checks; qualification blockers explicit.

### P5 — Bounded agent and compute orchestration
Durable worker leases and heartbeats; idempotent tasks and cancellation; resource-aware scheduling; isolated proposals and independent review; measured local model routing and CPU kernels.

### P6 — Visual research workbench and learning
Linked graph/equation/proof/CAD views; interactive multi-coordinate exploration; glyph explorer; adaptive first-principles mathematics learning.

## 14. Cross-cutting acceptance contract

Every project artifact should identify stable ID/schema version/owner; source chat/document/paper/code origin; status and evidence level; assumptions, units, constraints and uncertainty; source revision/hash and retrieval time; dependencies and related idea IDs; tests, proof receipts or experiment receipts; unresolved objections and counterexamples; next falsification/verification step; reviewer and approval state; rollback reference if executable.

Promotion is evidence-specific:
- source discovered is not claim verified;
- claim formalized is not proof complete;
- proof compiles is not statement faithful;
- simulation runs is not model validated;
- CAD exports is not manufacturing qualified;
- worker lease issued is not result approved;
- tests pass is not permission to merge.

## 15. Chat-origin index (deduplicated)

1. Merlin as local-first research and engineering workbench; recursive improvement with explicit authority boundary.
2. CACE/Expert Robot/Hermes separation, typed capabilities, sandboxing and independent verification.
3. MCFC CPU/RAM/GPU compute fabric, resource probing, leases, scheduling, telemetry and budget-aware work.
4. Avrea as preferred free/self-hosted compute; avoid paid services, card trials and unnecessary hosted model costs.
5. Academic Spider: public professor websites, lecture notes, preprints, software, datasets and open problems across mathematics, physics and engineering.
6. Ideonomy: enumerate concept spaces, connections, gaps, analogies, counterexamples and testable hypotheses.
7. Equation Atlas: equations, units, assumptions, invariants, sources, methods, limitations, proof status and applications.
8. Math learning engine with first-principles visual explanations, adaptive practice, spaced repetition and mistake tracking.
9. Xenomathematics: nonstandard notation, glyphs as operators/programs, formal grammar and semantics.
10. Multi-coordinate objects: one point/object represented simultaneously in multiple coordinate systems and frames.
11. Complex, split-complex, dual, quaternion, dual-quaternion, octonion and Clifford/geometric algebra.
12. Eigenvalues, spectra, invariant subspaces, tensors, matrices and geometric transforms across dimensions.
13. Geometry/topology/transformations in 2D, 3D, 4D, 5D and higher, with explicit domain and map semantics.
14. Spacetime, block-universe projections and time-dependent structures as testable mathematical/physical hypotheses.
15. Superorganism mathematics: collective dynamics, networks, distributed optimization, synchronization and emergence.
16. Fractal engineering and lacunarity as morphology descriptors under declared scales and constraints.
17. THTG/UFT mathematical reconstruction, Page curve, 5D couplings, curvature invariants, FRG beta functions, fixed points and Lean conditional theorems.
18. Lean proof search optimization, theorem DAGs, reusable lemmas, axiom audit, exact statement comparison and performance benchmarks.
19. XMG rewrite rules, normalizers, critical pairs, termination and confluence proofs.
20. CAD engineering: parametric geometry, assemblies, constraints, coordinate frames, collision and kinematics.
21. Wiring engineering: typed pins/nets, physical connectivity, harness routing, connector metadata and independent qualification.
22. MCFC ↔ CAD/wiring workloads and CACE evidence receipts.
23. Shared mathematical/engineering representation feeding equations, simulation, CAD, wiring and visualization.
24. Local model architecture: quantization, adapters, hot-swapping, compression, retrieval and specialist routing.
25. Parrondo-inspired strategy switching, with controlled ablation against standalone baselines.
26. Research Council: implementer, skeptic, performance researcher, verifier and integrator with human approval.
27. CPU-native compute optimization, cache tiling, SIMD, quantized kernels and bounded parallel scheduling.
28. Research-to-design workflow with evidence provenance, revisions, reproducibility and rollback.
29. Mobile-friendly visual workbench, animated graphs, multi-frame inspection and compact evidence status.
30. Open-source/public-resource reuse with attribution, license review, provenance and no access-control circumvention.

## 16. Immediate next work

Do not expand the feature surface until P0 reconciliation is complete. Then:
1. Reconcile PR #67 → #70 → #72 → #75 ancestry and CI outcomes.
2. Build an inventory mapping each module to its tests and latest qualified receipt.
3. Implement theorem statement/dependency graph ingestion and proof-attempt records.
4. Add premise retrieval and theorem successor tests to the Proof Strategy Observatory.
5. Connect the object-view graph to existing coordinate-frame and CAD IR.
6. Ingest academic sources into the same typed graph with evidence labels.
7. Run focused Avrea qualification on exact commits; record real run IDs and results.
8. Only then propose promotion/merge candidates for human review.

**Non-negotiable:** preserve dissent, failed experiments, unknowns, source provenance and rollback. Merlin may discover and recommend; independent systems verify; the human maintainer authorizes.
