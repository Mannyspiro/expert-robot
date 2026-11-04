# Merlin Master Build Specification — 2026-11-04

## Mission

Build Merlin as a persistent, modular research and engineering operating system. It should take a question or hand-drawn idea, enumerate the idea space, research public literature, construct mathematical models, simulate declared physical environments, generate exact CAD/wiring artifacts, commission independent review, and preserve every result as replayable evidence.

The target experience is a voice-first web app: the user speaks naturally to Merlin; a council of specialized agents investigates in parallel or staged rounds; the UI shows each role's reasoning summary, disagreement, evidence class, model/environment, current jobs and produced artifacts. The system can later be packaged into Avrea's cache with reproducible builds and pinned dependencies.

## Consolidated prior requirements

### Foundation and project inventory
- Canonical registry of all projects, modules, skills, artifacts, dependencies, versions and ownership.
- Universal artifact identity and content-addressed immutable storage.
- Typed knowledge graph for claims, equations, sources, evidence, assumptions, contradictions and project relationships.
- Bulk intake of the five supplied archives; preserve original bytes, archive paths, hashes and duplicate relationships.
- Reconstruct actual Merlin inventory before marking projects integrated. Current Foundation v0.2 inventory reported 13 projects and 1,452 artifacts; 16/16 tests passed in the packaged foundation snapshot. This is an earlier package checkpoint, not proof all projects are integrated.
- Read-only Git inspection first. User preference is Merlin-native virtual PRs rather than using GitHub PRs as the product's primary collaboration model.

### Research and ideonomy
- Enumerate candidate questions and representations; score novelty, relevance, tractability, evidence gap, compute cost and expected information gain.
- Literature spider for public sources: IEEE, Crossref, OpenAlex, arXiv, standards catalogs and public datasets. Preserve source URL/DOI, title, author, date, edition/status, license/access class, abstract, references, extracted claims and hashes. Respect access controls and publisher licenses.
- Cross-domain research realms: mathematics, physics, engineering, materials, photonics, chemistry, biology, computing, robotics, signal processing, neural systems and other typed disciplines.
- Xenomathematics: alternative glyph/operator systems, geometric numbers, multiple coordinate systems and frames, nonstandard algebraic representations, higher-dimensional geometry, transformations and spacetime models. Every novel formalism must define syntax, semantics, operations, invariants and testable consequences.
- Preserve competing hypotheses and disagreement; do not collapse them into one AI-generated consensus.

### Council and simulated substrates
- Roles: chair/controller, mathematician, physicist, engineer, coder, skeptic, literature librarian, experimental designer and independent verifier.
- Different model families may be assigned by role, but model IDs, revisions, prompts, quantization, context limits, seeds and hardware are pinned in each run manifest.
- Simulated chips are virtual resource models unless transistor-level or device-level physics is explicitly implemented and validated. Track cores, memory, bandwidth, compute, energy/power estimates, latency and communication costs.
- Physics environments are pluggable: classical mechanics, electromagnetics, thermal, quantum, relativistic, fluid, materials and abstract axiomatic systems. Each has explicit equations, assumptions, boundary conditions, units and numerical method.
- A council vote is not proof. The skeptic must be able to reject unsupported claims and record counterexamples.

### CAD, wiring and generative media
- Engineering IR is the only authoritative geometry/connectivity source.
- Exact drafting is generated deterministically from dimensions, transforms, frames, pin positions and netlists.
- Native CAD/EDA adapters are required: FreeCAD/OpenSCAD and KiCad; ERC/DRC and import/export netlist equivalence.
- Electrical, thermal and manufacturing qualification must bind manufacturer data, applicable standards, uncertainty, model-correlation and test evidence.
- Image/video models are presentation-only unless an extracted result is converted to explicit typed geometry and independently validated.
- Coder prompts must carry source facts, assumptions, constraints, unit systems, acceptance tests and forbidden inferences. Require editable outputs, deterministic tests, hashes and assumption ledger.
- Generate CAD views first, then image/video renders and animations from those exact views; detect geometry drift between video keyframes.

### Integrations and execution
- Hermes: research routing, context assembly and agent coordination.
- CACE: typed experiments, proof/claim registry, graph execution, verification records and certificates.
- MCFC: bounded worker scheduling, leases, capacity evidence and execution provenance.
- Avrea: preferred CI/build/cache compute where available; pin toolchain and cache identity.
- Git adapter: read-only source inventory initially; later Merlin-native virtual branches, commits, diffs, reviews, virtual PRs, approval gates, controlled merges and rollback.
- Workers: capability-scoped, leased, idempotent, resource-bounded and independently observable.
- Cache only reproducible outputs with exact source/dependency/model/parameter identity. A cache hit is not a new verification.

### RSI governance
- Propose -> sandbox -> test -> benchmark -> verify -> compare with parent -> retain/reject -> explicit promotion.
- Rank by information gain per CPU/GPU-minute, reproducibility, generality, external validation and human review burden.
- Never expand filesystem, network, credential, process, repository or deployment authority as a side effect of model improvement.
- Rollback, lineage and failure fingerprints are mandatory.
- Distinguish hypothesis, literature, numerical, experimental, interval-certified, formally verified, independent review and provenance.

## Current verified implementation baseline

Repository: `Mannyspiro/expert-robot`
Working branch: `feat/merlin-real-world-equation-atlas-v01-20261104`

Already present in the current branch:
- C++ research runtime, bounded agent swarm, model-server adapters, cognition/interoception, research engine, imagination, skill store and proof-search components.
- Equation atlas and simulation engines.
- CAD/engineering IR, coordinate frames, physical connectivity mapping, electrical/thermal/manufacturing screening, evidence receipts and SVG/logical wiring exports.
- Image/video prompt compiler and local ComfyUI API adapter.
- CI workflow on Avrea runner.
- Formal Lean wire qualification theorem module and proof audit from the prior checkpoint.

Prior Foundation v0.2 archive intake report: 13 project groups, 1,452 artifacts, 16/16 tests; not all subsystems are runtime-integrated. Five archive bulk-intake, project registry, universal artifact model and knowledge graph remain explicit integration work.

## Implemented in this increment

- `python/merlin/research_council.py`: typed council roles, evidence classes, pluggable physics environment declarations, serial agent adapter contract, deterministic session receipt and virtual chip resource budget.
- `config/merlin/platform_manifest.json`: canonical platform layer inventory and promotion invariants.
- CI tests for council contract and environment validation.

These are orchestration contracts, not a claim that actual LLMs, neural-chip physics or every physical environment are already running.

## Ranked build sequence

### P0 — make the foundation canonical
1. Intake all five archives; preserve originals and hash every member.
2. Implement project registry, universal artifact schema, blob store and knowledge graph.
3. Create deterministic project/module/claim/proof/source index and one generated context bundle.
4. Map existing C++/Python/Lean capabilities into the registry; mark maturity truthfully.

### P1 — connect existing research engines
5. Connect Hermes routing and council roles to actual pinned model adapters.
6. Connect CACE claims, experiment graphs, Lean jobs and verification receipts.
7. Connect MCFC worker leases and capacity; preserve exactly one proof-sensitive CACE job at a time.
8. Build Avrea cache manifests and reproducible restore/save steps.

### P2 — simulation and engineering
9. Add physics plugin API with units, assumptions, solver metadata, boundary conditions and evidence ceilings.
10. Build multi-environment model composition and cross-model consistency tests.
11. Complete native KiCad and FreeCAD adapters, ERC/DRC, round-trip identity, geometric constraints and CAD render pipeline.
12. Add transient thermal, electromagnetic and mechanical solvers only with benchmark and experimental correlation.

### P3 — voice-first web
13. Build persistent session API, streaming speech input/output, interruption/cancel, transcript and artifact references.
14. Build council view with role status, sequential/parallel rounds, disagreement and evidence filters.
15. Add project browser, graph explorer, notebook, simulation controls, CAD/media preview, proof ledger and run replay.
16. Provide local model mode and explicit remote-provider configuration; no credentials in project files.

### P4 — RSI and release
17. Add research-idea enumeration and candidate scoring.
18. Run held-out evaluation and ablation before accepting strategy changes.
19. Produce Avrea cache release manifest with source SHA, dependency lock, model revisions, toolchain, tests, artifacts and checksums.
20. Package and deploy only after exact-head verification and explicit promotion.

## Web app acceptance criteria

- Voice can start, interrupt, resume and stop a session.
- Every spoken answer is linked to a session and sources/artifacts.
- Council agents show distinct mandates and model identities.
- User can inspect each contribution and the skeptic's objections.
- Council can return unresolved/disputed state.
- Long jobs are cancellable and resumable.
- Artifacts and sessions persist across reloads.
- No hidden automatic deployment, repository push or capability promotion.
- AI off mode remains functional for non-AI deterministic workflows.

## Release and qualification criteria

A release is not “complete” until:
- archive inventory reconciles with source manifests;
- all module contracts are schema-validated;
- tests pass on exact source head;
- Lean proofs build from clean pinned sources and axiom audit is recorded;
- numerical simulations have convergence/benchmark evidence and documented limitations;
- CAD/EDA exports pass native tool checks and netlist round-trip;
- evidence hashes and cache manifests reproduce;
- voice/web end-to-end tests pass;
- independent reviewer confirms no claim exceeds its evidence;
- rollback is tested.

## Non-goals / prohibited shortcuts
- No invented project inventory or fake integration status.
- No treating a simulated chip resource budget as a transistor-level model.
- No treating generated images/videos as authoritative CAD.
- No treating an LLM consensus as scientific proof.
- No automatic promotion from cache hits, benchmarks or hashes.
- No broad permission grants to research agents.
- No paid services or card trials as default dependencies.
