# Merlin Unified Engineering Plan

**Revision:** 2026-11-15  
**Status:** living plan; implementation is incremental and evidence-gated  
**Primary implementation base:** `Mannyspiro/expert-robot`  
**Related verification repository:** `morganaspim/Cace-app`

## 1. Product definition

Merlin is an evidence-driven research and engineering operating system. It accepts a question, goal, artifact, voice instruction, or observed failure; turns it into a traceable plan; explores possible explanations and designs; constructs candidate artifacts; tests them with the appropriate tools; subjects claims and results to independent skeptical review; and records the exact provenance and verification state.

The first useful production slice is:

`question / goal -> Hermes decomposition -> engineering plan -> Ideonomy enumeration -> bounded execution (MCFC) -> independent review (Logos) -> domain verification (CACE / tools) -> canonical registry + knowledge graph -> Merlin synthesis and next plan revision`

The MVP must work end-to-end before Merlin is used to improve itself. Self-improvement is a later, sandboxed workflow, never an authority shortcut.

## 2. Non-negotiable system invariants

1. **Capability may grow; authority does not silently expand.** Candidate code, agents, models, skills, and tools receive only explicit, bounded permissions.
2. **Proposal is not evidence.** Model output, Ideonomy scores, a rendered image, a successful preview, a numerical experiment, or a compilation alone cannot be promoted into a verified claim.
3. **Independent review.** The proposer cannot be the sole reviewer or verifier of its own result.
4. **Exact provenance.** Every trust-bearing result binds source repository and immutable commit, exact artifact digest, tool and version, configuration, inputs, outputs, and verifier receipt.
5. **Fail closed.** Missing verifier transport, ambiguous authority, malformed provenance, expired leases, or unavailable required tools result in an explicit blocked/unverified state.
6. **No automatic promotion.** Verified candidates remain candidates until the applicable human/policy approval gate authorizes promotion.
7. **Local-first privacy.** Automatic model routing is local-only. Cloud execution requires explicit selection/confirmation; no silent fallback.
8. **Resource discipline.** Run static checks and small deterministic tests before expensive builds. Reuse warm caches, avoid duplicate runs, and record resource consumption.
9. **One canonical implementation.** Extend the existing Expert Robot/CACE architecture; do not create parallel registries, duplicate orchestration engines, or competing sources of truth.
10. **Visible state is real state.** HUD activity and progress must be backed by durable jobs, events, artifacts, and measurements—not invented activity or private chain-of-thought renderings.

## 3. Agent and subsystem responsibilities

### Merlin — product-level synthesis and research interface
- Maintains the project map, goals, engineering plan, dependencies, decisions, and current verified state.
- Integrates research, math, code, science, engineering, media, and user-facing explanations.
- Produces concise conclusions with uncertainty and provenance.
- Presents the interactive research canvas, persistent chat, voice controls, and agent council.

### Ideonomy — enumerative discovery and alien-lacuna search
- Enumerates candidate hypotheses, structures, analogies, mechanisms, designs, and unexplored combinations.
- Searches both known combinations and underexplored/alien-lacuna regions; records what was enumerated, excluded, and not yet explored.
- Uses quality-diversity niches so one high-scoring family does not erase distinct representations.
- Scores novelty, coherence, explanatory reach, feasibility, falsifiability, expected information gain, cost, and evidence.
- Preserves raw proposals and scoring provenance. Scores prioritize experiments; they never certify truth.
- Converts promising candidates into explicit claims with assumptions, predicted observations, possible falsifiers, and proposed tests.

### Hermes — teacher-coder, decomposition, and orchestration
- Teaches concepts and explains the reasoning path at the requested level; can act as tutor, pair programmer, and implementation worker.
- Translates goals into typed tasks, acceptance criteria, dependency graphs, budgets, and tool requirements.
- Writes code, tests, documentation, adapters, and candidate artifacts in isolated workspaces.
- Uses durable jobs, idempotency keys, leases, heartbeats, outbox acknowledgements, retries, cancellation, and result collection.
- Reports what it built, what ran, what failed, and what remains unverified.
- May propose plans and code; may not self-certify, approve its own promotion, or bypass Logos/CACE.

### Logos — skeptical scientist and cross-domain challenge function
- Reviews all important Merlin claims and deliverables, not only formal mathematics.
- Challenges assumptions, checks units and dimensional consistency, hunts counterexamples, checks alternative explanations, and asks what observation would falsify a claim.
- Separates established facts, supported inferences, hypotheses, speculation, and unknowns.
- Audits whether the evidence actually supports the conclusion and whether the experiment could distinguish competing explanations.
- Produces structured review findings and required follow-up tests. Logos is not the final authority for machine-checkable artifacts; CACE and domain tools provide independent verification.

### CACE — independent artifact and proof verification
- Verifies exact artifact bytes and provenance independently of the proposing agent.
- For Lean: pinned toolchain and Mathlib, compilation, theorem metadata, proof-hole checks, kernel axiom audit, exact-head qualification, and signed/attested receipt as required.
- For code: reproducible test/build evidence and artifact digest.
- For CAD/electrical/simulation: exact source files, tool versions, solver settings, validation reports, and independent checks.
- Does not accept self-reported SHA strings or local test doubles as independent CACE receipts.
- No transport or credentials means `unavailable/unqualified`, not a simulated success.

### MCFC — bounded compute fabric
- Schedules workers and tool modules against explicit CPU, RAM, GPU/VRAM, time, storage, and concurrency budgets.
- Issues execution leases; enforces deadlines, cancellation, quotas, and isolation.
- Records telemetry and immutable execution receipts.
- Selects the cheapest adequate tier; expensive qualification runs only after cheaper gates pass.

### Avrea / OCI / local workers
- Avrea is treated as unavailable until 2026-12-01.
- OCI is the current remote execution path when available and within resource limits.
- Local and free/low-cost preflight paths are preferred for static checks and focused tests.
- Never revive the retired Cloudflare runtime as a dependency.

### Forge — internal virtual Git and controlled change management
- Provides commits, branches, diffs, three-way merge/conflict handling, review, rollback, and event history.
- Supports isolated headless CI and artifact/evidence receipts.
- GitHub may be used as a read-only source adapter or external mirror; ordinary GitHub PR workflow is not the primary user experience.
- Merge and deployment are explicit policy-gated operations.

## 4. The problem-translation loop

Every difficult or stalled task must trigger a structured reframing pass before spending another large compute budget:

1. State the original problem and acceptance criteria precisely.
2. List assumptions, constraints, invariants, units, boundary conditions, and unknowns.
3. Generate alternative representations: algebraic, geometric, topological, graph, combinatorial, probabilistic, physical, computational, optimization, or constructive.
4. For each translation, state the mapping in both directions and identify what must be preserved.
5. Prove equivalence where possible; otherwise label it as an approximation, relaxation, analogy, or heuristic and quantify its limitations.
6. Build the smallest toy model or counterexample that can discriminate between representations.
7. Ask Ideonomy to enumerate routes and Logos to challenge them.
8. Select the next route by expected verified information gain per unit cost.
9. Record why the route was selected and what result would cause a switch.

A representation change must not silently change the problem.

## 5. Living engineering-plan protocol

The plan is a versioned artifact in the canonical registry and Forge. Every task contains:
- stable task ID and parent goal;
- requirement/decision references;
- current state: proposed, ready, running, blocked, failed, verified, accepted, or deferred;
- owner/agent and bounded capabilities;
- prerequisites and affected artifacts;
- acceptance tests and independent verifier;
- resource estimate and hard budget;
- exact source/input revisions;
- result, evidence receipt, and failure classification;
- next action and reason for priority.

Plan updates are triggered by new requirements, failed tests, counterexamples, changed dependencies, resource constraints, or verified discoveries. The plan records both the previous and new decision with a reason; it does not rewrite history.

Ranking rule: prioritize dependency-unblocking work, then trust-boundary correctness, then the smallest vertical slice that creates measurable end-to-end value, then breadth. Avoid parallel implementations and speculative infrastructure that does not unblock the slice.

## 6. Canonical data and evidence model

Use one registry and universal artifact model for:
- projects, goals, requirements, tasks, decisions, hypotheses, claims, assumptions;
- equations, Lean declarations, source files, code, datasets, experiments, counterexamples;
- CAD parts, sketches, assemblies, drawings, wiring diagrams, netlists, simulations;
- images, video, audio, models, reports, and UI visualizations;
- executions, tool versions, logs, approvals, reviews, and verification receipts.

Every artifact has an immutable content digest, media/type schema, provenance, relationships, lifecycle state, and evidence links. The knowledge graph stores typed edges such as `DERIVED_FROM`, `TESTS`, `SUPPORTS`, `CONTRADICTS`, `USES`, `IMPLEMENTS`, `CONNECTED_TO`, and `VERIFIED_BY`. The event outbox is durable and replayable. Read APIs expose project/artifact/graph state without granting write authority.

## 7. CAD, drafting, wiring, and simulation

Image generation is useful for concept exploration, reference sheets, textures, layouts, and visual alternatives. A generated image is not a native CAD model, dimensioned drawing, electrical schematic, netlist, or verified design.

Provide a hand-drafting-style workspace where a user or agent can:
- draw points, lines, arcs, splines, profiles, symbols, and wires;
- apply dimensions, geometric constraints, tolerances, and coordinate frames;
- place and connect components with named pins/ports;
- create parametric 2D sketches and 3D parts/assemblies;
- generate orthographic drawings, sections, exploded views, bills of materials, and wiring schedules;
- translate schematics into netlists and validate connectivity;
- run geometry, clearance, thermal, electrical, manufacturability, and simulation checks;
- export native editable source artifacts and neutral exchange formats.

Use FreeCAD/OpenCASCADE for parametric mechanical CAD, KiCad for electrical schematics/PCB, ngspice for circuit simulation, and OpenModelica where multi-domain physical modeling is appropriate. Preserve the editable native source and exact toolchain alongside every rendered preview.

## 8. Research, mathematics, and scientific domains

- Mathematics: Ideonomy discovery -> explicit conjecture/assumptions -> counterexample search/numerical exploration -> Lean formalization -> CACE verification.
- Physics/engineering: dimensional analysis -> model derivation -> parameter provenance -> numerical solver -> sensitivity/uncertainty analysis -> independent review.
- Biochemistry/evolution: literature-grounded claims, sequence/structure evidence, reproducible pipelines, uncertainty, and domain-specific validation.
- RSI/self-improvement: candidate changes isolated; benchmarked against parent; tested, reviewed, and retained/rejected by policy. Capability improvement never implies authority expansion.
- Titan remains a separate research track for key-space/security and post-quantum/hybrid cryptography. Do not mix Titan's authority or experimental invention graph into ordinary Merlin claims.

## 9. Visual, voice, and interaction system

- Persistent chat at the bottom; a central adaptive research/engineering canvas; a compact Jarvis/Watson-inspired HUD that does not obscure the work.
- A 3D neural constellation can zoom, rotate, and focus on agents, jobs, hypotheses, artifacts, dependencies, and evidence. Its animation must be driven by real event and telemetry data.
- The council can include Architect, Compression Scientist, Performance Engineer, Skeptical Scientist, Evolutionary Researcher, and domain specialists. Personalities may be lively and verbose, but their roles and evidence standards remain explicit.
- Voice is opt-in and controllable, with editable transcription, cancellation/error handling, and no automatic submission without the user's chosen interaction.
- Lightweight TTS is preferred where it meets quality requirements; local-first privacy remains the default.
- Images/video are first-class artifact types and may be generated through pluggable workflows such as ComfyUI, with provenance and licensing metadata.

## 10. Open-source components to evaluate and reuse

Prefer adapters and existing projects over rewriting mature tools. Candidate components (license and maintenance status must be rechecked before adoption):

| Capability | Candidate | Intended reuse |
|---|---|---|
| Formal proof | Lean 4 + mathlib4 | theorem definitions, proof checking, math library |
| Mechanical CAD | FreeCAD + OpenCASCADE | parametric sketches, parts, assemblies, drawings |
| Electrical CAD | KiCad | schematic capture, PCB, netlist interchange |
| Circuit simulation | ngspice | SPICE-compatible circuit execution |
| Multi-domain simulation | OpenModelica | physical systems and co-simulation |
| Lightweight parametric drafting | SolveSpace | constraint-based 2D/3D sketching and parts |
| Image/video generation workflows | ComfyUI | node-based local generation and API integration |
| 3D scene and visualization | Blender | rendering, animation, scene authoring |
| Interactive node canvas | React Flow / xyflow | research graph, workflow and wiring UI |
| 3D web visualization | Three.js | neural constellation and interactive geometry |
| Graph analysis | NetworkX | research graph algorithms and prototypes |
| Model gateway | LiteLLM | optional provider adapter behind local-first policy |
| Agent workflow patterns | LangGraph | reference patterns only; do not duplicate Hermes without a measured reason |

No dependency is adopted solely because it is popular. Evaluate license compatibility, security, maintenance, API stability, resource footprint, offline operation, and whether it preserves native editable artifacts.

## 11. Ranked implementation sequence

### P0 — Restore a trustworthy, current source of truth
- Keep PR #143 and related work explicitly draft/unmerged until exact-head gates pass.
- Reconcile Expert Robot, CACE, and prior Merlin artifacts into one inventory: implemented, partial, prototype, planned, retired.
- Preserve Titan separation, local-first privacy, no automatic promotion, and no Cloudflare dependency.
- Fix the currently failing RP² Lean linearity/composition proof and record the new failure class F-035 in CACE's ledger.

### P1 — Complete one vertical slice
- User question -> Hermes task graph and acceptance criteria.
- Ideonomy enumerates and ranks a bounded candidate set.
- Hermes executes one selected task under MCFC lease and budget.
- Logos reviews the claim and evidence.
- CACE or the relevant domain verifier checks the exact artifact.
- Registry, knowledge graph, and event outbox persist the result.
- Merlin explains the result and revises the engineering plan.

### P2 — Make the plan and memory durable
- Canonical project registry, universal artifact schema, typed provenance, replayable outbox.
- Knowledge graph and hypothesis/claim ledger.
- Versioned engineering plan with dependency and decision history.
- Search/retrieval over prior chats, repositories, files, research, and evidence, with source and confidence labels.

### P3 — Complete scientific and engineering workspaces
- Lean/numerical/counterexample adapters with real CACE transport.
- FreeCAD import and editable modeling/assembly adapter.
- KiCad schematic/netlist adapter and ngspice simulation receipts.
- Engineering IR, coordinate transforms, unit checking, safety and manufacturability gates.
- ComfyUI image/video workflows and Blender/Three.js visualization.

### P4 — Production orchestration and Forge
- Hermes durable job lifecycle, outbox acknowledgements, retries, cancellation, and result collection.
- MCFC leases, scheduler, resource telemetry, concurrency and budgets.
- Internal Forge with virtual PRs, isolated CI, evidence-backed merge and rollback.

### P5 — Unified Merlin experience and measured RSI
- HUD, canvas, voice, council, and live job/evidence visualization.
- Benchmark-driven model/skill routing and compression.
- Sandboxed self-improvement evaluated against a frozen parent baseline.

## 12. Current checkpoint and next action

- Current CACE exact-pin RP² preflight run: [43741255348](https://github.com/morganaspim/Cace-app/actions/runs/43741255348), exact head `88da2a15a9ed22b23c988354658a328a759a1b70`.
- It passed the preceding canaries and requested module checks, but the RP² standalone target failed in the two `Fintype` scalar-sum rewrites and the linear-map composition extensionality proof. Root compilation was skipped. It explicitly reported `qualification=false`.
- The evidence bundle is retained at [artifact 14172905900](https://github.com/morganaspim/Cace-app/actions/runs/43741255348/artifacts/14172905900).
- The new failure classification is recorded on isolated branch `merlin/record-rp2-linearity-failure-035` in the CACE repository. It is not merged and does not claim a repair.
- Avrea remains unavailable until 2026-12-01; use OCI only when available and justified by preflight. Avoid duplicate or broad runner dispatches.

**Immediate next action:** repair and compile the three local Lean proof seams with focused tests, then rerun the quarantined standalone target once. Only after it passes should the next promotion stage be considered. In parallel, inventory existing Expert Robot modules and reuse them to implement the P1 vertical slice; do not rebuild its existing imagination, skeptic, cognition, or recursive-lemma machinery.
