# Merlin Master Context and Cross-Chat Handoff

**Snapshot date:** 2026-11-16  
**Repository:** `Mannyspiro/expert-robot`  
**Purpose:** Consolidate the available prior-chat context, project decisions, research ambitions, architecture, verification rules, current work, and next steps into a durable source-controlled reference for Merlin.

> This is a context and planning artifact, not a claim that every described capability is implemented. Every capability is labelled as implemented/source-authored, partially implemented, planned, or unverified where the available record permits. Earlier assistant-generated handoff material and reported test results are identified as historical claims, not silently upgraded into current evidence.

## 1. Executive purpose

Merlin is intended to become a persistent, agentic, multimodal research and engineering environment: a system that can discover questions, gather and normalize evidence, enumerate candidate ideas, plan investigations, run bounded experiments, construct mathematical and engineering artifacts, challenge its own conclusions, and preserve reproducible evidence.

The near-term objective is a useful, reliable MVP. The longer-term objective is for Merlin to help improve and extend Merlin itself through controlled, measurable, independently reviewed changes. The user wants working production infrastructure rather than disconnected demos, repeated architecture proposals, or workflows that depend on the user performing routine manual operations.

The system must support inductive discovery and deductive verification together:
- Induction: observe, ingest, compare, enumerate, hypothesize, discover patterns, propose models.
- Deduction: state assumptions, derive consequences, prove lemmas, run formal and numerical checks, search for counterexamples, and independently verify artifacts.
- Scientific skepticism: challenge assumptions, inspect source quality, identify uncertainty and bias, distinguish evidence from interpretation, and record what would falsify a claim.

The governing invariant is:

**Capability may grow; authority does not automatically expand.**

No model, agent, generated artifact, or successful benchmark may silently acquire additional filesystem, network, credential, process, repository, signing, deployment, or production authority.

## 2. Product experience and long-term vision

### 2.1 Main interface

The desired Merlin interface is a persistent research workspace, not a conventional chat window with unrelated tools:
- Chat and persistent voice interaction anchored at the bottom.
- A restrained Jarvis/Watson-inspired HUD with clear status, resource, job, evidence, and approval state.
- A central adaptive research canvas that shows active questions, branches, evidence, equations, artifacts, and experiments.
- A 3D neural/knowledge constellation that can zoom, rotate, focus, and reveal relationships.
- Visible research branching and evidence flow.
- Agent entities (Hermes, Logos, CACE, MCFC, Avrea and specialist agents) with explicit assignment, state, progress, and handoff.
- Equations and mathematical objects represented geometrically, with coordinate transforms and linked visualizations.
- CAD assemblies, wiring diagrams, simulation artifacts, and their dependencies represented in the same provenance-aware workspace.
- Visualizations should represent actual recorded computations or explicitly labelled simulations, not fictional depictions of hidden model cognition.

Long-term media ambitions include image/video generation, CAD drafting, engineering diagrams, and multimodal research artifacts. Media outputs must be treated as versioned artifacts with source, tool, configuration, and validation provenance.

### 2.2 User interaction principles

- Continue autonomously where repository, connector, or runtime access permits.
- Do not ask the user to perform routine manual workflows unless a real authorization, secret, physical resource, or external account action makes it unavoidable.
- Give ranked, concrete next steps and execute the highest-value safe step.
- Reframe or translate a blocked problem into a tractable representation.
- Use Ideonomy to enumerate alternatives rather than prematurely selecting one.
- Keep the user informed about what was changed and what was actually verified.
- Do not waste paid compute or trigger speculative CI runs.
- Do not merge, deploy, sign, mutate production secrets, change trust roots, or promote capabilities without explicit authorization and all relevant gates.
- Preserve originals and append lineage; packaging and transformation must not delete source artifacts.

## 3. Agent roles and separation of authority

| Agent/system | Intended responsibility | Must not be treated as |
|---|---|---|
| **Hermes** | Decompose research and engineering tasks; plan and dispatch stages; teach/codify workflows; manage stage lifecycle, retries, task identity and durable checkpoints. | Independent truth verifier or authority escalator. |
| **Logos** | Skeptical scientist/reviewer; inspect evidence, challenge assumptions, identify fallacies/bias, generate counter-hypotheses and falsifiability questions. | CACE, proof checker, truth oracle, or promotion authority. |
| **CACE** | Independent verification and evidence receipts bound to exact artifacts, source commits, tools and results. | A local test double, self-reported hash, or unconfigured endpoint. |
| **MCFC** | Virtual compute fabric: worker scheduling, resource budgets, leases, isolation, telemetry, execution limits and module coordination. | A metadata-only estimate or unrestricted executor. |
| **Avrea** | Preferred remote runner/compute integration when available, subject to budget, capability qualification and approval. | Assumed available when the service is unavailable. |
| **Specialist agents** | Domain-specific research, coding, math, CAD, biology, chemistry, literature and other bounded tasks. | Unreviewed privileged agents. |

Agent personas may be lively, verbose, and distinct in internal discussion, but outputs must retain typed roles, source references, and explicit uncertainty. A council of voices is useful for idea generation and critique, not a substitute for evidence.

## 4. Canonical architecture

The target architecture should converge on one canonical implementation rather than parallel, conflicting registries, graphs, execution engines, or evidence systems.

### 4.1 Core services

1. **Canonical project and artifact registry**
   - Stable project identity and repository binding.
   - Universal artifact model and versioned ArtifactRefs.
   - Immutable content digests and explicit lineage.
   - Read-only project/artifact query APIs before introducing mutation paths.
   - Canonical registry contract and policy hashes.

2. **Knowledge graph**
   - Projects, source artifacts, extracted representations, claims, hypotheses, equations, experiments, proofs, models, skills, agents, and derived artifacts.
   - Typed relationships and provenance.
   - Graph validation endpoint (planned/previously requested: `/api/graphs/validate`).
   - Graph edges must reference resolvable artifacts and preserve lineage.

3. **Evidence/provenance bridge**
   - Typed CACE receipts.
   - Exact source repository and commit, ArtifactRef, artifact digest, tool and tool version, configuration, execution result, and independent verifier receipt.
   - No promotion from a hash alone.

4. **Event journal and outbox**
   - Append-only lifecycle events.
   - Idempotent dispatch and acknowledgements.
   - Durable task state, checkpoints, replay and reconciliation.
   - Explicit handling of ambiguous, malformed, rejected and non-eligible claims.

5. **Hermes orchestration**
   - Typed stage contracts, task IDs, idempotency keys, deadlines, cancellation and bounded retries.
   - Stage outputs are canonical artifacts, not ephemeral text alone.
   - Every stage records inputs, outputs, tools, config, resource use and failure state.

6. **MCFC worker fabric**
   - Worker leases, scheduling, resource budgets, concurrency controls, heartbeats, process supervision, telemetry and result collection.
   - Actual OS/container enforcement for memory, CPU, time, filesystem, network and secrets.
   - Process-tree termination and cleanup.
   - A budget field in a task payload is not enforcement.

7. **Capability registry**
   - Capability states: `configured`, `unavailable`, `unqualified` (plus any explicitly approved qualified state only after evidence).
   - Fail closed when dependencies or transports are missing.
   - Capability discovery endpoint (previously requested: `/api/capabilities`).
   - Capability policy hash and registry contract hash.
   - No automatic authority expansion.

8. **Async interaction gateway**
   - Streaming chunks and timing, cancellation, deadlines, concurrency limits and provider routing.
   - Provider qualification receipts bound to model/revision, held-out task results, privacy review and measured performance.
   - Route by paired, held-out evaluations rather than unverified claims or model names.

9. **Unified HUD and Forge**
   - Jobs, agents, approvals, resources, evidence, failures, review queues, and project state.
   - Mobile-friendly Forge dashboard for the internal virtual repository/PR/CI lifecycle.

### 4.2 Artifact and provenance model

Every durable result should have:
- Stable ArtifactRef with project, logical path/version and digest.
- Artifact type/schema and canonical serialized payload.
- Source ArtifactRefs and locator-level bindings where applicable.
- Repository identity and exact commit SHA when code is involved.
- Tool/adapter identity, immutable version/revision and build digest.
- Configuration/prompt/template digests where generation is involved.
- Execution environment and resource metadata.
- Verification status and receipt references.
- Explicit epistemic status and authority boundary.

A content hash establishes identity/integrity only. It does not establish semantic correctness, source authenticity, proof validity, or independent verification.

### 4.3 Internal virtual GitHub

The intended primary workflow is an internal/headless Git-like system, not a conventional GitHub PR process:
- SQLite-backed commits, branches, virtual PRs, event history and artifact references.
- Three-way merge, conflict representation, rebase, rollback and audit history.
- Headless CI in isolated workspaces with resource limits, timeouts and logs.
- CACE commit/test/reviewer receipts.
- MCFC worker execution and scheduling.
- Controlled merge gates and explicit approval.
- External GitHub remains a useful read-only adapter and optional publication interface, not the core product lifecycle.

## 5. Research lifecycle and scientific method

Canonical research lifecycle:

`question → scope → sources → extraction → normalization → ideonomy → Hermes plan → experiments/proofs → Logos critique → CACE verification → registry/graph → synthesis/lesson`

Each stage must preserve:
- Research question and intended decision.
- Scope, exclusions and operational definitions.
- Source quality, provenance, publication/version and locator.
- Variables, units, assumptions and boundary conditions.
- Candidate hypotheses and alternatives.
- Method, controls, baselines and expected observations.
- Uncertainty, bias, confounders and limitations.
- Falsification/counterexample criteria.
- Reproducible experiment inputs and outputs.
- Independent verification status.

### 5.1 Source intake

Use publicly available resources only unless a separate explicit authorization changes that scope. Ingest public-domain books and open scientific/technical resources when licensing and source metadata permit. Preserve the original and record:
- Source URL/identifier, author, publisher/repository, publication date and version.
- License and usage restrictions.
- Acquisition time and content digest.
- Extraction tool/version and extraction confidence.
- Page, section, timestamp, code path or other exact locator.
- OCR/transcription uncertainty and document structure.

Mine YouTube transcripts as supplemental research sources when available, with channel, video, publication date, transcript provenance and timestamp locators. A transcript is not equivalent to a peer-reviewed paper or primary dataset.

Avoid uncontrolled storage growth: deduplicate by content digest, retain source identity, compress where appropriate, store derived representations separately, and use retention policies that never silently delete originals.

### 5.2 Evidence classification

Keep distinct:
- Direct source quotation.
- Paraphrase.
- Interpretation.
- Hypothesis.
- Numerical observation.
- Formal proof.
- Independent verification.
- Speculation or exploratory model.

A source citation proves where a statement came from, not that the statement is true. A model-generated explanation is not a source. An experiment supports only the tested conditions and assumptions.

### 5.3 Ideonomy

Ideonomy should enumerate candidate ideas, primitives, relationships, explanations, models, and experiment directions. Enumeration is not truth validation. Each candidate must bind to inspected source locators and preserve its generator provenance. Candidate IDs and candidate-set identities must be recomputable from canonical content and full provenance.

The system should track duplicate/near-duplicate ideas, contradiction, novelty, scope, source coverage, and unresolved dependencies. Candidate rankings should be evidence- and objective-dependent, not treated as universal merit.

## 6. Research domains and capability ambitions

Merlin should cover established disciplines, interdisciplinary work, and carefully labelled speculative exploration. The following is a research map, not a statement that engines for every domain already exist.

### 6.1 Mathematics and mathematical computing

- Algebra, linear algebra, abstract algebra, number theory, combinatorics, discrete mathematics.
- Analysis, real/complex analysis, calculus, functional analysis, differential equations, PDEs.
- Geometry: Euclidean, affine, projective, hyperbolic, spherical, symplectic and differential geometry.
- Topology, algebraic topology, homology, homotopy and category-theoretic correspondences.
- Probability, statistics, Bayesian inference, stochastic processes, information theory.
- Optimization, operations research, control theory, numerical analysis and scientific computing.
- Graph theory, networks, spectral methods, eigenmethods, tensors, matrices and least squares.
- Fourier analysis, sampling, signal processing, Shannon–Nyquist.
- Conservation laws, state-space models, Kalman filtering, dynamics and stability.
- Formal methods, type theory, theorem proving, proof search and proof engineering.
- Mathematical history, philosophy, pedagogy, problem-solving and Olympiad-level training.

Priority applied equation families previously identified:
- Heat, wave and Maxwell equations.
- Conservation laws and PDE systems.
- Reaction-diffusion and biological growth.
- Finite-element methods and structural/field simulation.
- Robotics, control and state estimation.
- Networks, graph models and spectral methods.
- Bayesian models, risk and statistical inference.
- Quantum-safe / post-quantum cryptographic mathematics as a research topic, subject to separate security-track boundaries.

For every equation/model, normalize symbols, units, assumptions, domains, boundary conditions, provenance, known validity, empirical tests and proof status. Compare models by accuracy, cost, complexity, uncertainty, constraints, evidence and verification.

### 6.2 Xenomathematics and XMG

User-defined exploratory direction:
- **Xenomathematics:** explore mathematical systems that do not assume human notation, glyphs, conventional axioms, or familiar representational habits. Consider alien mathematical cognition and notation as research hypotheses, not established facts.
- Explore operations as glyphs, geometric writing, composable operator collections, and alternative symbol systems.
- Investigate biological/embodied mathematical representations, non-carbon life and possible nonhuman forms of cognition as speculative interdisciplinary topics; clearly distinguish scientific evidence from conjecture.
- **XMG:** develop novel coordinate systems and multi-frame mathematical representations. Represent the same point/object across 2D, 3D, 4D, 5D and higher-dimensional systems; map transformations, equations, matrices, bases and invariants between frames.
- Explore multi-frame geometry, glyph algebra, operator composition, invariant discovery, dimensional comparison and geometric equation visualization.

Candidate mathematical systems and representations previously discussed include Cartesian, polar, cylindrical, spherical, projective and custom frames; real, complex, quaternion, octonion, Clifford, matrix and tensor systems; spacetime/Minkowski invariants; and category/type-theoretic correspondences.

Desired engines (planned): Ideonomy Engine, XMG Glyph Compiler, coordinate/algebra/geometry engines, invariant discovery, visualization and CAD bridge, CACE+Lean verification, evidence receipts and knowledge graph.

### 6.3 Physics and spacetime

- Classical mechanics, dynamics, fields, waves, electromagnetism and thermodynamics.
- Relativity, spacetime geometry, Minkowski invariants and coordinate transformations.
- Quantum theory and mathematical foundations, with explicit assumptions and limits.
- Continuum mechanics, fluids, materials and multiscale modelling.
- Dimensional analysis, conservation laws, PDEs and numerical simulation.
- Compare models and frames by invariants, predictive accuracy, assumptions, domain of validity and experimental evidence.

### 6.4 Chemistry, materials and biochemistry

- Physical, organic, inorganic and analytical chemistry.
- Molecular structure, reaction networks, kinetics, thermodynamics and transport.
- Materials science, metamaterials, microstructure and property prediction.
- Biochemistry, molecular evolution, protein structure and molecular interactions.
- DNA transcription and other molecular mechanisms.
- AlphaFold/Evoformer-related structural representations and Ramachandran geometry scoring as a specific existing research-skill concept.
- Reaction-diffusion, biological growth and coupled physical/chemical systems.

All predictions must distinguish empirical datasets, model predictions, simulation assumptions and biological interpretation. Do not infer clinical validity from a structural or computational score.

### 6.5 Biology, evolution and life sciences

- Evolutionary biology, genetics, molecular biology, cell biology and systems biology.
- Ecology, developmental biology, biological growth and morphogenesis.
- Protein structure/function, transcription and biochemical pathways.
- Non-carbon life and nonhuman consciousness as explicitly speculative, evidence-seeking research questions.
- Mathematical models of living systems, information processing and adaptation.

### 6.6 Engineering and physical design

- Mechanical, electrical, electronic, software, systems and controls engineering.
- CAD assemblies and geometry; FreeCAD integration and importers.
- Engineering intermediate representation (IR) linking geometry, parts, constraints, materials, tolerances and manufacturing.
- Wiring diagrams, netlists, PCB relationships and component metadata.
- Electrical safety, thermal analysis, manufacturability and design-rule verification.
- ngspice adapter with exact tool version, input deck, output digest, solver configuration, resource and runtime receipts.
- FEM, structural, thermal, fluid and multiphysics simulation.
- Robotics, sensing, control and embedded systems.

CAD import is not equivalent to engineering validation. A rendered assembly is not a manufacturable or safe design. Each check must identify its assumptions, standard/rule source, applicable revision and exact artifact.

### 6.7 Computer science, AI and software systems

- Programming languages, compilers, type systems, algorithms and data structures.
- Distributed systems, databases, event sourcing, queues, concurrency and reliability.
- AI/ML, model evaluation, inference, multimodal generation, agents and tool use.
- Information retrieval, literature synthesis, embeddings and knowledge graphs.
- Formal verification, security engineering, privacy, sandboxing and supply-chain provenance.
- Reproducible builds, benchmark design, regression and mutation testing.
- Adaptive learning systems and code education.

AI model selection should use exact revisions, measured held-out evaluations, privacy review, cost/latency/resource budgets and failure analysis.

### 6.8 Economics, finance, statistics and risk

Potentially relevant applied research domain:
- Optimization, econometrics, time series, Bayesian inference, forecasting and uncertainty.
- Financial/statistical risk, public-finance datasets and economic models.
- Compare assumptions, incentives, data quality, uncertainty, causal claims and out-of-sample performance.
- Treat forecasts as uncertain model outputs, not facts; record data vintages and reproducibility.
- Keep this research domain separate from election/voting-system infrastructure and from the Titan security track unless a separately scoped project is authorized.

### 6.9 Scientific literature and research synthesis

- Cross-paper synthesis and literature invariant discovery.
- Compare definitions, datasets, methods, assumptions, sample populations, units, uncertainty and contradictions.
- Maintain citation and quotation locators down to page/section/table/figure or transcript timestamp.
- Track replication status and evidence strength.
- Existing skill concept: arXiv literature invariant synthesizer.

## 7. Learning and teaching system

Merlin should support three connected but distinct learning paths:
1. **Mathematician:** concepts, definitions, proof, mathematical history, conjecture and research.
2. **Mathematics programmer:** implement mathematical ideas, numerical algorithms, symbolic systems, testing and visualization.
3. **Computational hacker/problem solver:** CS50-inspired computational thinking, decomposition, debugging, experimentation and building.

The system should:
- Adapt progression to demonstrated skill, learner history, interests and errors.
- Teach induction and deduction as complementary habits.
- Use historical mathematicians and the development of ideas as context.
- Use video/YouTube lessons as interest-driven supplements, not unquestioned authorities.
- Include Olympiad-style “Math Kung Fu” problem solving.
- Generate exercises only when grounded in a known learning objective and verified solution path.
- Track mastery evidence and uncertainty; avoid confusing answer recall with understanding.
- Use Hermes for decomposition and teaching/coding assistance, Logos for critique, and CACE/Lean for proof-backed answer validation when applicable.

## 8. Math Discovery Engine and formal verification

Target pipeline:
1. Ideonomy produces a source-bound candidate claim.
2. Validate scope, assumptions, definitions, falsifiability, source IDs and exact locators.
3. Hermes decomposes into proof, numerical, literature and counterexample tasks.
4. Lean formalization is generated without `sorry` or `admit` placeholders.
5. Compile with pinned Lean and mathlib toolchains.
6. Run numerical experiments with reproducible seeds, precision, solver/version, parameters, environment, runtime and output digest.
7. Run finite/bounded counterexample searches with domain, bounds, method, seed and termination status.
8. Logos challenges assumptions and interpretations.
9. CACE independently verifies exact artifact digests and receipts.
10. Registry and graph record the complete evidence chain.

Lean receipts must include status, stdout/stderr, toolchain, dependency lock and source digest. Numerical and counterexample results must include full execution metadata. A Python reference calculation is not a formal proof. A Lean source file is not a proof until it compiles under the pinned toolchain and its exact artifact is verified.

### 8.1 RP² formalization work

A dedicated project has sought a Lean formalization of the real projective plane chain complex:
- Six vertices, fifteen edges, ten facets.
- Boundary maps and proof that boundary composed with boundary is zero.
- Connectedness of the one-skeleton.
- Integral chain groups and boundary maps.
- Desired integral homology classifications: (H_0 \cong \mathbb{Z}), (H_1 \cong \mathbb{Z}/2), (H_2=0).

Current recorded state:
- PR #102 in `morganaspim/Cace-app`, head `c2af6c0f01babb3d89d4ef8972dd96535a71b422`.
- Lean file `formal/cace_formal/CACEFormal/RP2ChainComplex.lean`.
- Definitions and some chain-complex/connectivity results are present, but the integral classification is not established.
- No exact-head pinned Lean compile result is recorded.
- Independent Python reference calculations support the proposed homology, but do not prove the Lean theorem or the basis equivalences.
- Required next proof steps: H0 augmentation quotient; H2 injectivity via a nonzero determinant minor; H1 fundamental cycle basis and quotient presentation; determinant/minor witnesses; quotient (mathbb{Z}/2); exact pinned compile and independent CACE verification.

## 9. Media, CAD and multimodal toolchain

Historical source inventory:
- Blender 5.3.0 Linux x86-64 archive: SHA-256 `dacb8264197a3f7fda6001285a5a506fc97ee943881261c2c3bd63c882f22e05`; archive integrity and member-path checks were reported successful.
- ComfyUI source archive: SHA-256 `d04633f43a85041453f21c7970b4ec3881c3dd2acf4e78b535c7b44eeeeed62b`; 1,563 members, 116 JSON workflow blueprints, no model weights, no Git metadata/upstream source commit recorded.
- These archives were not evidence of installed or executed runtimes. No model weights were included. Neither runtime was reported as launched in the previous work.
- Blender archive is Linux x86-64; the previously identified OCI runner was ARM64 and cannot directly run that binary without a suitable compatibility/alternative build.
- Blender adapter requirements: absolute executable, `shell=False`, disable auto-execution, constrained low-resolution render, explicit allowlisted environment, workspace-contained paths, version probe, executable digest, bounded input/output/log streaming, timeout, process cleanup and external OS/container isolation.
- ComfyUI API research recorded endpoints for prompt submission, job status, cancellation and view retrieval. Loopback binding is not a sandbox; custom nodes and workflows need isolated execution with restricted filesystem/network and no secrets.
- PR #174 media adapters: exact-head CI run #43795822511 was reported successful for build-and-smoke, optional inference job skipped. This is repository CI evidence only, not runtime qualification. Source-review blockers include environment inheritance, unbounded reads, output/log caps after buffering, and lack of OS sandbox/process-tree cleanup.
- PR #173 creative toolchain inventory: exact-head CI run #43790408866 was reported passed. Inventory evidence only.

## 10. Runtime, infrastructure and resource constraints

- User expects Linux x86-64 as the standard target for local application/tooling unless a component has a separately qualified architecture build.
- A machine was previously reported as 8 vCPU and approximately 24.8 GB available cache/current available memory; this is a historical environment note, not a current live measurement.
- Avrea runner budget was reported as 3,000 minutes/month remaining; user explicitly said to assume Avrea unavailable until 2026-12-01 and preserve the budget until then.
- OCI runner previously identified as `cace-oci-a1`, Linux ARM64, labels `self-hosted,cace,oci,aarch64`, persistent Lean/mathlib caches, loopback MCP :8765, instance-principal least-privilege IAM. This is historical configuration and must be revalidated before use.
- An earlier unrestricted `ocarun` sudo pattern must not be reused.
- Cloudflare was later explicitly removed/disabled; do not plan new Cloudflare deployment work unless the user changes that decision.
- No paid compute. Avoid speculative or overlapping GitHub Actions runs. Before a manual run, identify exact acceptance target, exact head, owner-approved window, resource/cost impact and whether an equivalent run already exists.
- The user does not want routine manual steps. Do not ask them to create secrets with blank values or pretend an unconfigured secret/transport is available.

## 11. Security, governance and trust boundaries

- Least privilege, deny-by-default and explicit approvals.
- Capability growth must never imply authority growth.
- Isolate generated code, workflows, plugins, models and custom nodes.
- Enforce process, CPU, memory, wall-time, network, filesystem, credentials and concurrency limits outside the model.
- Secret material must never be exposed to untrusted agents or subprocesses.
- Use immutable provenance and append-only audit events.
- Idempotency and replay must be tested under failure and concurrency.
- A worker lease without process termination cannot guarantee exclusivity after lease expiry.
- Cancellation must terminate or safely isolate work; a callback check alone cannot interrupt a blocked subprocess/provider call.
- Provider provenance supplied by the runtime is a declaration unless authenticated by a trusted provider/adapter receipt.
- CACE transport must fail closed when not configured; do not use local test doubles as evidence of real CACE verification.
- No production signing, trust-root changes, secret mutation, deployment, merge or capability promotion without explicit authorization and relevant independent gates.
- Titan is a separate user security/encryption research track and must remain separate from the experimental invention graph.

## 12. Current source work and pull-request ledger (snapshot 2026-11-16)

The following statuses are from the prior-chat handoff and current work at the snapshot date. They must be rechecked against GitHub before relying on them.

### Current active work in `Mannyspiro/expert-robot`

- **PR #171 — Ideonomy enumeration**  
  URL: https://github.com/Mannyspiro/expert-robot/pull/171  
  Recorded head: `e95920f4f877df1cda0b71ca8c5b88a34043b9e5`.  
  Draft/open/unmerged in last recorded state. Earlier CI run failed two assertions; later fixes corrected source-node ID binding and tamper-fixture ordering, but no passing exact-head CI was recorded. Source binding does not establish semantic entailment or truth.

- **PR #172 — Hermes Ideonomy stage**  
  URL: https://github.com/Mannyspiro/expert-robot/pull/172  
  Recorded head: `b3d78ff8ada12947cb53dcdfd13b627e52aee343`.  
  Draft/open/unmerged. Runtime-owned generator provenance is validated before provider invocation; full provenance contributes to candidate and candidate-set identities; a SQLite stage journal binds idempotency keys to immutable request identity, checkpoints generated candidate sets and replays completed results. Exactly-once provider execution during an in-flight crash is not guaranteed. No exact-head tests/CI result recorded.

- **PR #175 — Immutable Ideonomy generator provenance**  
  URL: https://github.com/Mannyspiro/expert-robot/pull/175  
  Recorded head: `f9ae326fc1b0180da8fe7d6dce5b8cbc4aae6ae1`.  
  Draft/open/unmerged. Requires immutable provider revision and prompt/config/adapter digests; recomputes identities and rejects provenance tampering. Runtime declarations are not authenticated provider attestations. No exact-head CI recorded.

- **PR #176 — Logos source-bound review stage**  
  URL: https://github.com/Mannyspiro/expert-robot/pull/176  
  Created 2026-11-16 on branch `feat/merlin-logos-source-bound-review-20261116`, initially based on PR #172 head. Adds source-bound candidate validation, typed findings and dispositions, counter-hypotheses, falsifiability questions, reviewer provenance, canonical storage and graph linkage, and tests. Draft/open/unmerged in the last recorded state. Tests were authored but not executed. Opening the draft automatically queued workflows at head `895d8418aae8471c32fca81e09631139d1e31bbb`: unified-platform run `43876764161` queued and CI run `43876764230` pending; no pass recorded. Recheck current head/status before any decision.

- **PR #174 — Media adapters**  
  URL: https://github.com/Mannyspiro/expert-robot/pull/174  
  Recorded head `980300fafafbb58f52ab4ea31fb3f326d953fd91`. Draft/open/unmerged. Build-and-smoke CI reported success, optional inference skipped. Runtime qualification blocked by environment inheritance, unbounded buffering, missing external OS sandbox and process-tree enforcement.

- **PR #173 — Creative toolchain inventory**  
  URL: https://github.com/Mannyspiro/expert-robot/pull/173  
  Recorded head `10e52ea57d3542a1c303cf11e049a2cd8eb222b8`. Inventory-only; exact-head CI run reported passed. No runtime launch/qualification.

### Other projects

- **PR #102 — RP² Lean formalization** in `morganaspim/Cace-app`, head `c2af6c0f01babb3d89d4ef8972dd96535a71b422`. Partial chain-complex formalization; integral homology classifications and exact-head compile remain outstanding.
- Earlier Merlin architecture/bootstrap/continuity PRs and branches exist (including historical PR #138, #143, #144 and #102 in prior handoffs). Reconcile them with live repository state; do not infer their present status from this snapshot.
- Repository names previously referenced include `Mannyspiro/expert-robot`, `morganaspim/Cace-app`, `morganaspim/Cace-ksee-webapp`, and `morgana cace` OCI context. Validate exact repository identity and access before writing.

## 13. Historical handoff bundles and archive notes

A prior conversation reported creation of a 234 MB, 50-file master handoff ZIP with SHA-256 prefix/suffix `26ad826d...ad7c73e`, containing Sovereign OS/Hermes/CACE/MCFC archives, Research Gates, MVP/Forge versions, Virtual PR/MCFC prototypes, source trees, handoff, limitations, verification protocol, roadmap and manifest. It was reported as not an integrated working runtime and not freshly retested. It was split into independently extractable parts of approximately 133 MB and 99 MB, reportedly integrity-checked.

These are historical prior-assistant reports. This PR does not assert those files are currently attached, available, or revalidated. Do not infer download paths or claim a new backup. Do not delete or overwrite source files during future consolidation.

## 14. Explicitly unresolved blockers

1. End-to-end Hermes → Ideonomy → Logos integration tests with real canonical registry artifacts and graph persistence.
2. Authenticated independent CACE transport and exact-artifact receipts.
3. External MCFC supervisor with actual OS-enforced isolation, cancellation, timeouts, resource limits, process-tree cleanup and concurrency control.
4. Provider-authenticated provenance/attestation rather than runtime-declared revision alone.
5. Exact-head validation of PRs #171, #172, #175 and #176; do not trigger unnecessary CI.
6. RP² integral homology proofs and pinned Lean compile.
7. Canonical registry/graph/evidence contract reconciliation across repositories.
8. Production-grade virtual GitHub lifecycle and controlled merge gates.
9. Qualified FreeCAD importer, engineering IR, netlist, safety/thermal/manufacturing checks and ngspice execution receipts.
10. Real media runtime qualification with isolated Blender/ComfyUI workers and model provenance.
11. Provider routing based on held-out measured evaluations and privacy review.
12. Research atlas coverage expansion, including the previously scoped normalized entries 021–100, specialist sources, reproducible checks, Lean candidates, and interactive XMG views.

## 15. Ranked roadmap

### P0 — Trustworthy research MVP
- Canonical project/artifact registry and ArtifactRef contract.
- Source ingestion/extraction with locator-level provenance.
- Ideonomy candidate generation with immutable provenance and reproducible identities.
- Hermes stage orchestration, durable journal, idempotency and bounded retry.
- Logos source-bound skeptical review with no authority to promote.
- Exact CACE verification bridge and fail-closed behavior.
- MCFC external worker supervisor.
- Unified research status and evidence view.
- End-to-end tests and exact-head verification.

### P1 — Reproducible mathematical discovery
- Real-World Equation Atlas: normalized equations, units, assumptions, sources, experiments and proof status.
- Ideonomy-to-Lean pipeline, numerical experiment runner and counterexample search.
- RP² proof completion as a formalization milestone.
- XMG multi-frame coordinate and glyph-algebra prototypes with exact transform contracts.
- Math Kung Fu learning path and adaptive evidence-backed lessons.

### P2 — Engineering and virtual laboratory
- FreeCAD importer and engineering IR.
- Assembly/wiring/netlist representation.
- Safety, thermal and manufacturability checks.
- ngspice adapter and reproducible simulation receipts.
- Virtual lab job orchestration and resource budgets.
- CAD/math/simulation adapters connected to canonical artifacts and graph.

### P3 — Multimodal research
- Blender and ComfyUI isolated adapters.
- Model/workflow provenance and output validation.
- Image/video/CAD artifacts with lineage and evidence.
- Interactive XMG and research-canvas visualizations.
- Media capability remains unavailable/unqualified until runtime gates pass.

### P4 — Virtual GitHub / Merlin Forge
- SQLite commit/branch/virtual PR/event model.
- Three-way merge, conflicts, rebase and rollback.
- Isolated headless CI and CACE receipts.
- MCFC worker execution, approval and controlled merge.
- Mobile Forge dashboard.

### P5 — Adaptive self-improvement
- Held-out evaluations and paired model comparisons.
- Research-skill discovery and versioning.
- Candidate improvement sandbox → test → benchmark → verify → compare → retain/reject → explicit approval.
- Capability can improve without automatic authority expansion.

### P6 — Expanded science and learning
- Extend research atlas across disciplines and subfields.
- Public-domain/open-resource library with provenance and storage governance.
- Cross-disciplinary synthesis and contradiction discovery.
- Adaptive mathematician, math-programmer and computational-hacker curricula.
- Carefully labelled speculative xenomathematics and nonhuman cognition research.

## 16. Operational acceptance checklist

A production claim is accepted only when the evidence identifies:
- Exact repository, commit and artifact digest.
- Exact tool/runtime and version.
- Exact configuration and dependency lock.
- Reproducible inputs and output digests.
- Test/CI run ID and exact tested head, where applicable.
- Actual runtime and resource enforcement evidence.
- Independent CACE receipt for claims requiring independent verification.
- Explicit limitations and unresolved failure modes.

Never conflate:
- Source authored with test passed.
- Test passed with exact-head CI passed.
- CI passed with runtime qualified.
- Runtime completed with independent CACE verified.
- Hash integrity with semantic correctness.
- Candidate generation with discovery/validation.
- Logos critique with proof.
- Python reference calculations with Lean proof.
- Inventory with installed/executed toolchain.
- A queued workflow with a successful workflow.

## 17. Maintenance protocol

- Update this document when decisions, architecture, status or constraints change.
- Preserve superseded decisions with date and reason rather than silently rewriting history.
- Link every implementation PR, test result, artifact and receipt to exact commits.
- Add a short change log to the project status ledger.
- Distinguish user requirements from assistant proposals and unverified implementation claims.
- Reconcile this document with the canonical registry and current repositories periodically.
- Keep unrelated personal context out of the Merlin project record.
