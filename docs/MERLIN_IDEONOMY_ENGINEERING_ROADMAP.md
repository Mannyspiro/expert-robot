# Merlin: integrated research, ideonomy, CAD and engineering roadmap

**Status:** architecture and implementation backlog, 2026-11-03  
**Execution target:** Avrea `avrea-ubuntu-latest-8-vcpu`; retain OCI `cace-oci-a1` as a separate verifier.  
**Cost posture:** free-first; no new paid services or routine runner churn.  
**Evidence rule:** discovered metadata, hypotheses, simulations, proofs, and approved engineering artifacts are distinct states.

## 1. What Merlin is meant to become

Merlin is a research-to-engineering workbench. Its core loop is:

`observe -> retrieve -> normalize -> enumerate -> hypothesize -> challenge -> model -> simulate -> verify -> design -> review -> release`

The system should connect ideas to source evidence, mathematical models, CAD geometry, wiring, test results, and reproducible build artifacts. It must never silently convert an interesting pattern into a fact or a proposed design into a fabrication-ready design.

## 2. Current verified software foundation

- AcademicSpider v0.1: institution/topic query generator.
- Public source store v0.2: canonical URLs, provenance, deduplication and review states.
- OpenAlex adapter v0.3: opt-in public scholarly metadata search.
- Academic graph v0.4: works, researchers, institution labels and authorship relationships.
- Engineering IR v1: typed parts, pins, nets, dimensions, deterministic OpenSCAD and JSON netlist exports; local validation for identity, connectivity and declared ratings.

OpenAlex works can link to topics, authors, institutions and citations. Its topic labels are model-assigned classifications, useful for discovery but not ground truth. Sources: OpenAlex Works and Topics documentation (see links below).

## 3. Architecture: one source of truth

### A. Core typed model
1. Project and experiment identity.
2. SI/unit-aware quantities and coordinate frames.
3. Geometry primitives, transforms and constraints.
4. Components, part revisions, materials and tolerances.
5. Pins, ports, nets, harnesses and connector pinouts.
6. Power domains, voltage/current envelopes and signal classes.
7. Simulations, measurements, assumptions and uncertainty.
8. Evidence records, source provenance, approvals and signatures.
9. Versioned schemas and deterministic serialization.

### B. Research knowledge graph
1. Works, authors, institutions, topics, datasets and software.
2. Claims and the exact passages/data supporting them.
3. Mathematical objects: groups, rings, fields, manifolds, graphs, tensors, operators, spectra and invariants.
4. Relations: generalizes, specializes, equivalent-to, maps-to, bounds, contradicts, uses, implements.
5. Hypotheses in a separate namespace from source facts.
6. Counterexamples, replications, negative results and unresolved assumptions.
7. Formal proof objects and verifier/toolchain hashes.

### C. CAD/EDA pipeline
1. Parametric mechanical model generation.
2. Coordinate frames and transformations across 2D/3D/4D state spaces.
3. Component placement and keep-out zones.
4. Wiring/netlist generation from the same engineering IR.
5. Connector, pin, gauge, insulation, thermal and current-rating metadata.
6. Export adapters: OpenSCAD first; KiCad schematic/PCB integration next.
7. Manufacturing exports only after DRC/ERC, tolerance and human review.
8. Revision diffs and traceability from requirement -> part -> net -> test.

### D. Execution and governance
1. Avrea is the primary build/test target when its runner is actually available.
2. OCI `cace-oci-a1` remains a separate formal-verification lane.
3. Branch isolation, immutable run IDs, pinned dependencies and content hashes.
4. Budgets, idempotent leases, bounded retries and cancellation.
5. No unapproved production writes; preview diff and explicit approval.
6. Evidence-carrying results and rollback records.
7. Capability growth never silently expands authority.

## 4. Ideonomy: enumerated idea space

Treat this as a navigable taxonomy, not a claim that every possible idea has been exhausted.

### 4.1 Mathematics and computation
- Algebra: groups, rings, fields, modules, algebras, category theory.
- Geometry: Euclidean, affine, projective, hyperbolic, elliptic, symplectic, contact, discrete and computational geometry.
- Topology: point-set, algebraic, differential, knot/link, persistent and computational topology.
- Analysis: real, complex, functional, harmonic, stochastic, variational and nonlinear analysis.
- Discrete mathematics: graph theory, combinatorics, matroids, coding and design theory.
- Number systems: real, complex, quaternions, octonions, Clifford/geometric algebra, dual numbers, hyper-dual numbers, p-adics, tropical and modular systems.
- Linear systems: eigenvalues/eigenvectors, singular values, tensor decompositions, spectral graph theory, matrix pencils and operator spectra.
- Coordinate systems: Cartesian, polar, cylindrical, spherical, barycentric, projective, curvilinear, local charts, manifold atlases, spacetime coordinates and learned latent coordinates.
- Transformations: rotations, reflections, translations, affine/projective maps, conformal maps, Fourier/Laplace/wavelet transforms, gauge transformations and coordinate changes.
- Physics mathematics: differential geometry, tensors, Lie groups/algebras, variational principles, PDEs, statistical mechanics and quantum information.
- Formal methods: type theory, dependent types, Lean, proof assistants, SMT, model checking and verified numerics.

### 4.2 Physical sciences and engineering
- Mechanical design, mechanisms, kinematics, dynamics, materials and tolerances.
- Electrical/electronic design, analog/digital circuits, power, signal integrity and embedded systems.
- Control theory, robotics, estimation, sensor fusion and actuation.
- Thermal, fluid, acoustic, optical and electromagnetic modelling.
- Manufacturing, assembly, metrology, reliability and lifecycle analysis.
- Biological systems, biomimicry, soft robotics and multiscale morphology.
- Energy systems, storage, conversion, power electronics and thermal management.

### 4.3 AI, research and information systems
- Literature discovery and evidence extraction.
- Ideonomy and combinatorial idea generation.
- Knowledge graphs, ontologies and provenance.
- Multi-agent role separation: proposer, critic, verifier, implementer and auditor.
- Active learning, experiment selection and value-of-information ranking.
- Causal inference, uncertainty quantification and Bayesian model comparison.
- Program synthesis, code generation, test generation and formal verification.
- Human-in-the-loop review, reproducibility and audit trails.

### 4.4 Visual and interaction systems
- Multiscale 2D/3D visualization.
- Time-dependent and animated geometry.
- Linked views: equations, graphs, CAD, netlists and simulation plots.
- Interactive coordinate-frame switching.
- Glyph/operator notation as a reversible visual language.
- Accessibility, compact mobile UI and explainable state transitions.

## 5. Research programme: high-value cross-links

Each item should become a hypothesis card with supporting papers, counterexamples, an executable experiment and a formal statement where feasible.

1. Spectral graph theory <-> geometry: relate graph Laplacians, curvature notions, embeddings and diffusion.
2. Eigenstructure <-> coordinate systems: compare invariants under basis changes and nonlinear maps.
3. Clifford algebra <-> robotics/CAD: compact rotations, reflections and rigid-body transforms.
4. Lie groups <-> mechanisms: represent configuration spaces and constrained motion.
5. Topology <-> engineering: detect connectivity changes, holes, routing obstructions and shape classes.
6. Information theory <-> research strategy: rank experiments by expected information gain per compute cost.
7. Category theory <-> model interoperability: map objects and transformations between CAD, circuit and simulation domains.
8. Differential geometry <-> control: use manifold-aware state estimation and motion planning.
9. Combinatorics <-> circuit design: enumerate bounded topologies and component arrangements.
10. Formal methods <-> numerical simulation: prove invariants around a numerically explored model.
11. Multiscale biology <-> mechanical design: test structural motifs across scales without assuming biological function transfers directly.
12. Spacetime geometry <-> time-dependent systems: distinguish coordinate transforms, physical dynamics and visualization projections.
13. Geometric algebra <-> signal processing: investigate multivector representations for rotations and coupled signals.
14. Graph rewriting <-> CAD evolution: express design edits as typed, reversible graph transformations.
15. Uncertainty <-> tolerancing: propagate manufacturing variation into fit, stress, thermal and electrical margins.

## 6. Engineering IR v1: current contract

- Geometry unit is explicitly millimetres.
- Parts have reference designators, names, dimensions and positions.
- Pins carry optional maximum voltage/current ratings.
- Nets declare endpoints, nominal voltage, maximum current and class.
- Validation checks duplicate IDs, unknown endpoints, pin reuse across nets, and declared pin-rating exceedance.
- Exports: deterministic OpenSCAD box assembly and JSON netlist.

**Limitations:** no electrical directionality, transient analysis, wire gauge/temperature derating, creepage/clearance, impedance, fuse coordination, connector mating rules, 3D routing, mechanical collisions or KiCad ERC/DRC integration yet. Current validator is an early consistency checker, not a safety certification tool.

## 7. Next implementation increments

### v0.5 — Research graph enrichment
- Add OpenAlex topic IDs, labels and scores to works.
- Add topic nodes and work-topic edges.
- Preserve topic source and retrieval timestamp.
- Never treat automated topic assignment as a verified claim.

### v0.6 — Hypothesis ledger
- Claim text, formalized relation, supporting work IDs, counterexamples, assumptions and test plan.
- Status: proposed, literature_checked, computationally_tested, refuted, conditional, formally_verified.
- Require independent evidence for every promotion; proof and simulation statuses remain distinct.

### v0.7 — Engineering project persistence
- Versioned JSON schema and SQLite store for engineering projects.
- Stable IDs, schema migrations, canonical hashes and deterministic diffs.
- Import/export fixtures and round-trip tests.

### v0.8 — Mechanical CAD
- Parametric OpenSCAD primitives, transforms, constraints, assemblies and clearances.
- Generate a preview and geometry report.
- Add collision and bounding-box tests.

### v0.9 — Wiring and EDA
- Connector libraries, pin maps, wire/harness objects and net classes.
- KiCad adapter and native ERC/DRC invocation where installed.
- Add current/voltage/thermal calculations with explicit assumptions and component datasheet provenance.

### v1.0 — Research-to-design loop
- Requirement -> literature -> hypothesis -> model -> simulation -> CAD/netlist -> verification -> reviewed release.
- Reproducible run manifests, compute budgets, artifact hashes and human approval.

## 8. Avrea execution contract

Preferred target: `avrea-ubuntu-latest-8-vcpu`. The current chat integration does not expose an Avrea control tool, so this commit prepares the project for that runner but does not claim to have started an Avrea job.

Recommended runner job:
1. Checkout the isolated feature branch.
2. Set Python version and install only project-declared dependencies.
3. Run `python -m unittest discover -s tests` with `PYTHONPATH=python`.
4. Run static checks if configured.
5. Generate engineering fixtures in a temporary directory.
6. Upload test logs, JSON netlist and OpenSCAD output as artifacts.
7. Do not deploy or promote automatically.

## 9. Public research sources

- OpenAlex works and linked entities: https://help.openalex.org/data/works/
- OpenAlex entity endpoints, including topics: https://help.openalex.org/api/endpoints/
- OpenAlex authorship structure: https://help.openalex.org/data/authorships/
- KiCad project scope (schematic capture and PCB layout): https://www.kicad.org/about/kicad/
- KiCad Python schematic/netlist model: https://docs.kicad.org/kicad-python/schematic.html

## 10. Definition of “real Merlin”

Merlin is real when a user can:
1. enter a research question or engineering requirement;
2. inspect sourced records and provenance;
3. browse the idea graph and clearly labelled hypotheses;
4. run a bounded mathematical/computational experiment;
5. create or modify a typed CAD/electrical project;
6. generate geometry and netlist artifacts from one source of truth;
7. run independent validation and view failures;
8. reproduce the exact result from a pinned manifest;
9. approve a revision with an auditable diff.

The present branch advances the foundations; it does not yet satisfy the full end-to-end definition.


---

## Implementation update — v0.5 and v0.6

### v0.5 topic-aware scholarly graph
Implemented in `openalex_public.py` and `academic_graph.py`:
- Public OpenAlex work metadata now requests topic IDs, labels and classification scores.
- Graph store adds `topics` and `work_topics` tables.
- Topic IDs are stable entity keys; topic labels remain descriptive metadata.
- Re-ingestion rebuilds a work's topic edges, removing stale assignments.
- `topic_works()` provides a local query path for a topic.
- Topic scores are range-checked and explicitly treated as classifications, not confidence in a scientific claim.

### v0.6 evidence-gated hypothesis ledger
Implemented in `hypothesis_ledger.py`:
- Hypotheses are stored separately from scholarly facts.
- Each hypothesis records a claim, mathematical objects, relation, assumptions and status.
- Evidence records are append-only and categorized as source, counterexample, experiment, proof or assumption.
- Status transitions require matching evidence:
  - `literature_checked` requires a source record.
  - `computationally_tested` requires an experiment record.
  - `refuted` requires a counterexample record.
  - `conditional` requires an assumption record.
  - `formally_verified` requires a proof record with a content/artifact hash.
- No automated promotion occurs.

### Current limitations
- Topic graph stores OpenAlex's supplied classifications; no independent topic inference or citation-network traversal is implemented.
- Hypothesis evidence records are local metadata; this version does not execute experiments, run Lean, or independently verify cited sources.
- A proof artifact hash records identity, not correctness. A trusted Lean build and theorem dependency audit are still required before accepting formal verification.
- All network acquisition remains explicit and public-API-only.

## v0.7 — versioned engineering project persistence

Implemented in `python/merlin/engineering_project_store.py`:
- Canonical schema-versioned serialization for the typed EngineeringProject model.
- Stable SHA-256 content hashes over canonical JSON.
- SQLite append-only revision snapshots with parent-hash chaining.
- Idempotent saves: identical content does not create a new revision.
- Historical loading, revision history and deterministic path-level diffs.
- History verification checks content hashes and parent links.

### Scope and limitations
- This is local project persistence, not a multi-user collaboration or cloud sync service.
- Hash chaining detects accidental or unauthorized history changes only when the stored history is independently trusted; it is not a signed audit log.
- Schema migrations beyond version 1 are not implemented.
- Canonical ordering intentionally treats part, pin, net and endpoint order as non-semantic for this IR version.
- The CAD exporter remains a simple box-based OpenSCAD output; no parametric constraints, transforms, collision detection, KiCad export or engineering sign-off is implied.

### Tests added
- Round-trip serialization and stable hashes.
- Canonical hash stability under reordered parts/nets.
- Idempotent saves and append-only revision increments.
- Deterministic diffs and historical diff retrieval.
- Schema rejection, invalid project rejection and missing revision behavior.