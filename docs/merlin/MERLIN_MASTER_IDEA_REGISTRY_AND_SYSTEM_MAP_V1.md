# Merlin Master Idea Registry and System Map v1

**Purpose:** durable index of Merlin ideas, research programs, subsystems, interfaces, existing pull requests, and production gaps.  
**Snapshot date:** 2026-11-05  
**Repository:** `Mannyspiro/expert-robot`  
**Status:** portfolio map and implementation contract; not a claim that every listed subsystem is deployed.

## 0. Registry rule: no idea lost, no proposal mistaken for a product

Every material Merlin idea must have:
1. a stable idea ID;
2. a short statement of the problem and intended outcome;
3. an owning subsystem and accountable agent/human role;
4. links to prerequisites, consumers and related ideas;
5. a GitHub issue or PR (a PR when it includes an artifact or implementation; an issue when work is not yet ready to implement);
6. an explicit lifecycle state: captured, specified, implemented, CI-tested, independently verified, deployed, measured;
7. evidence references tied to exact commit, workflow run, artifact digest and tool version where applicable.

A conversation summary, design document, green CI run, artifact hash, Lean proof, experiment, deployment and scientific conclusion are different evidence types. Never conflate them. A PR is a traceable change proposal, not proof that a feature is production-ready. Keep draft PRs open until their exact dependencies, tests, review and operational acceptance criteria are satisfied.

This registry is a recoverable snapshot of Merlin-related project context surfaced in conversations and the connected repository. It is not a guarantee that every historical chat or every external repository has been exhaustively searched. New discoveries must be appended with source references rather than silently assumed.

## 1. The unifying idea

**Merlin is a research-and-engineering operating system that turns questions into reproducible, bounded work and turns results into inspectable evidence.**

It should be able to:
- understand a question and its context;
- represent it in multiple disciplinary, mathematical, linguistic and cultural frames;
- find and criticize sources;
- construct hypotheses and competing explanations;
- design calculations, proofs, experiments, simulations and engineering tasks;
- compile precise prompts for the right agent or subsystem;
- execute work under resource, network, tool and authority constraints;
- collect exact outputs, tests, logs, provenance and failures;
- have CACE independently check artifacts and formal evidence;
- preserve all versions and lineage;
- teach the knowledge through adaptive curriculum and Merlin Learning;
- improve its methods only through measurable, independently qualified changes.

Core invariant: **capability grows; authority never expands automatically.**

## 2. How the parts interrelate

### End-to-end research lifecycle

1. **Intake and framing:** user question, project, constraints, expected output and intended use.
2. **Lens selection:** discipline, mathematical representation, cultural/historical setting, epistemic method and risk class.
3. **Knowledge acquisition:** public scholarly sources, datasets, primary materials, media and local project artifacts; provenance and licensing recorded.
4. **Knowledge graph:** claims, definitions, hypotheses, evidence, methods, people, institutions, concepts, equations, artifacts and dependencies.
5. **Plan synthesis:** research curriculum and domain specialists decompose the problem into bounded tasks and acceptance criteria.
6. **Prompt compilation:** deterministic PromptTask/PromptCompiler bind context, input references, source repository/commit, outputs, limits and tool allowlist.
7. **Dispatch:** Hermes/outbox routes to the selected worker; MCFC/lease policy reserves bounded resources; Avrea executes suitable compute jobs.
8. **Result return:** PromptResult binds task, worker, prompt/task hashes, outputs, tests, evidence and limitations; acknowledgements are lease-checked and idempotent.
9. **Independent checks:** CACE re-hashes artifacts and checks receipts; Lean checks formal propositions and axiom dependencies; domain validators assess units, dimensions, statistics, CAD, SPICE, etc.
10. **Assessment:** an independent assessor distinguishes correctness, reproducibility, evidence quality, external validity and unresolved uncertainty.
11. **Persistence:** immutable artifact versions, append-only history, source/commit links, recovery points and evidence ledger.
12. **Presentation and teaching:** read-only HUD/research dashboard and Merlin Learning expose progress, provenance, explanations, lessons and review schedules.
13. **Iteration:** benchmark outcomes, compute cost, error rates and user/faculty feedback inform proposed improvements; approval and qualification gates remain explicit.

### Dependency map

```text
User / Institution / Research Question
                 |
       Intake + Project Registry
                 |
     Lens & Representation Selection
       /          |           \
  Domain      Logic/Math    History/Culture
  Curricula   / XMG / Lean   / Language
       \          |           /
        Knowledge + Hypothesis Graph
                    |
         Hermes Research Coordinator
                    |
        Deterministic Prompt Compiler
                    |
         Event Outbox / Leases / MCFC
                    |
       Expert Robot / Specialist Agents
                    |
              Avrea Execution
                    |
       PromptResult / Evidence Envelope
                    |
       CACE + Lean + Domain Validators
                    |
      Independent Assessment / Review
                    |
       Immutable Registry + Evidence Log
                    |
      HUD / Dashboard / Merlin Learning
                    |
       Evaluation -> Qualified Iteration
```

The diagram is conceptual: each connection must be verified against live code and an actual round-trip test before being called operational.

## 3. Logic as lenses of culture — a core Merlin research program

Treat logic as both:
- a formal study of valid inference under explicit rules; and
- a family of historically situated practices for organizing knowledge, disagreement, explanation, proof, classification and decision.

Do not claim that a culture has one uniform logic or that formal validity is merely relative. Separate formal semantics from the cultural, historical and institutional contexts in which people choose questions, categories, premises, evidence and standards of explanation.

### Five complementary lenses

1. **Formal lens:** syntax, semantics, inference rules, axioms, models, proof systems, consistency, completeness, decidability and expressive power.
2. **Historical lens:** what problems were being solved, which texts/tools/institutions existed, who transmitted or contested ideas, and how notations and methods changed.
3. **Cultural-linguistic lens:** how language, translation, metaphor, classification, ontology and rhetorical conventions shape what is made salient or expressible.
4. **Epistemic lens:** what counts as evidence, testimony, observation, demonstration, proof, authority, consensus, counterexample or practical success in a given inquiry.
5. **Applied lens:** how inference is used in mathematics, science, law, medicine, engineering, education, policy, art and everyday reasoning.

### Comparative research method

For each historical or living tradition:
- use primary sources where accessible and reliable specialist scholarship;
- identify dates, place, language, schools, translators and transmission routes;
- distinguish original sources from modern reconstructions;
- describe the actual problem and reasoning practices before assigning modern labels;
- compare formal structures only when a defensible mapping is available;
- preserve untranslatable terms and disagreement;
- avoid treating traditions as homogeneous or timeless;
- invite specialist review for culturally specific interpretations.

Potential comparative subjects include Greek traditions of syllogistic and demonstrative reasoning; Indian Nyaya and Buddhist pramana traditions; Chinese Mohist and classical argumentation traditions; Islamic kalam and philosophical logic; medieval scholastic methods; African philosophical reasoning traditions; Indigenous knowledge practices and their own standards of evidence; and modern symbolic, mathematical and computational logics. These are research areas, not interchangeable or exhaustive cultural categories.

### Formal logic families to model

Classical, intuitionistic, constructive/type-theoretic, modal, temporal, epistemic, deontic, probabilistic, fuzzy, paraconsistent, relevance, linear, higher-order and categorical approaches. Each module must state its syntax, semantics, proof/inference rules, assumptions and intended use. Do not collapse them into one universal score.

### Productive questions

- What can one formalism express that another cannot?
- Which assumptions make an inference valid?
- What is lost when a concept is translated into another notation or language?
- How do institutions and material tools shape accepted evidence?
- Which disagreements are factual, semantic, methodological, axiomatic or value-based?
- Can the same problem be represented in several frames and compared by invariant structure?
- What happens when a classical inference system is used on inconsistent, incomplete, temporal or uncertain information?

Outputs: annotated source atlas, comparative concept graph, logic-system specifications, translation/crosswalk records, worked examples, formal models, teaching modules and reviewable research papers.

## 4. Mathematics, Xenomaths and Math Kung Fu

This is a major discovery and teaching laboratory, not merely a set of calculators.

### Core components
- **Equation Atlas:** sourced equations with definitions, units, assumptions, domain, provenance, symbolic checks, dimensional checks, numerical experiments and status.
- **Xenomaths / ideonomy:** structured enumeration of mathematical ideas, operators, objects, relations, invariants, dimensions, bases, coordinate systems and possible compositions. Novelty is a hypothesis until independently checked.
- **Glyph Foundry / XMG:** grammar, parser, normalizer, rewrite rules, confluence/termination checks, typed glyphs, multi-frame representations and simulation/rendering contracts.
- **Coordinate Registry:** named spaces and frames, basis definitions, units, transforms, metrics, orientations, dimensions and explicit conversion rules.
- **Invariant Engine:** identify quantities preserved under allowed transformations and distinguish true invariants from coordinate artifacts.
- **Algebra and symbolic engine:** typed operations, simplification rules, domain restrictions, exact arithmetic and numerical cross-checks.
- **Lean bridge:** formalize candidate theorems with explicit assumptions, pinned dependencies, proof builds and axiom audits.
- **Math Kung Fu:** first-principles/history-led lessons, visual discovery, short explanations, exercises, quizzes, recall and spaced review.

### Current known research strands
- Xenomaths and ideonomy enumeration.
- Glyph systems, XMG grammars and multi-frame objects.
- N-ality and group/representation-theoretic questions.
- Time crystals and time-dependent symmetry.
- Equation atlas and source crosswalks.
- Coordinate systems, bases, dimensions and transformation/invariant research.
- Olympiad-style reasoning and first-principles mathematical education.
- THTG/UFT/QFT residuals: action/source equations, Page-curve behavior, 5D coupling dimensions and curvature-invariant basis, beta functions/fixed points, conditional Lean theorems and axiom audits.

### Evidence discipline
Every mathematical entry begins as a conjecture or candidate until checked. Record exact definitions, assumptions, source lineage, symbolic result, dimensions/units, numerical method, tolerances, code revision, test output and independent replication. A Lean theorem proves only its formal statement from its stated assumptions and axioms; it does not prove the physical assumptions are true.

## 5. Physics, quantum and UFT/QFT research

Research pipeline:
- literature and source acquisition;
- precise statement of the proposed theory and its relationship to established frameworks;
- definitions, action, fields, symmetries, boundary conditions and assumptions;
- dimensional and symmetry checks;
- analytic derivations and limiting cases;
- symbolic and numerical computation;
- lattice/Monte Carlo/FRG or other suitable methods;
- public quantum-computer/API experiments only where the task fits hardware limits and provider terms;
- uncertainty, benchmark comparison and independent replication;
- conditional Lean formalization for mathematical claims.

Known tasks to preserve: THTG source/action equations; Page-curve finite maximum and continuity issue; 5D coupling dimensions and curvature-invariant basis; beta functions and fixed point; conditional theorem assumptions and axiom audit; numerical FRG confirmation; lattice Page curve; Standard Model-shifted fixed point coordinates; cosmological MCMC; public IBM Quantum and other public quantum systems feasibility. These are separate research questions and must not be promoted as established findings.

## 6. Science, history, philosophy and cross-domain research

The universal research curriculum spans:
- mathematics and formal sciences;
- physics and astronomy;
- chemistry and materials;
- biology and life sciences;
- medicine and health;
- earth, environment and planetary sciences;
- computer science and AI;
- engineering and applied technology;
- social and behavioral sciences;
- humanities, languages and history;
- economics, business and organizations;
- design, arts and creative research;
- interdisciplinary and emerging fields.

The science/history/philosophy atlas connects ideas to their historical setting, competing schools, methods, institutions, instruments, sources and modern revisions. It must distinguish historical interpretation from scientific validation.

Research themes mentioned in prior planning include brain-gut/vagus research, comparative medical traditions, biological and biochemical models, physics/biology simulations, complex systems and interdisciplinary hypothesis generation. Medical or safety-sensitive research requires appropriate expertise, ethics and validation; educational simulations are not clinical evidence.

## 7. Engineering, CAD, MCFC and physical systems

### Engineering pipeline
- typed Engineering IR for parts, pins, nets, geometry, units and stable instance IDs;
- coordinate frames and transformations;
- FreeCAD import/export and CAD kernel integration;
- mechanical assemblies, mates/joints, degrees of freedom and kinematics;
- geometry, collision, clearance and tolerance checks;
- electrical connectivity and netlist generation;
- KiCad schematic/PCB integration;
- ngspice reproducible simulation with pinned models and exact netlists;
- manufacturing outputs and human-reviewed release manifests.

### MCFC
MCFC is the resource/lease and execution coordination layer: provider discovery, capability qualification, leases, budgets, concurrency, quotas, job lifecycle, artifact retention and telemetry. It must distinguish a configured provider from an available provider and a qualified provider.

### Current limits to preserve
- Engineering IR checks are not fabrication sign-off.
- AABB overlap is conservative, not an exact solid collision result.
- Supplied pin coordinates are not verified datasheet facts.
- A netlist does not create physical wiring routes.
- ngspice output is only as reliable as the model, netlist and assumptions.

## 8. Agents, coding teacher and universal research school

Hermes is the chief coordinator/teacher, not an unbounded autonomous authority.

Specialist roles:
- coder-teacher: repository literacy, architecture, code generation, debugging, tests, CI, APIs, security boundaries, formal methods and deployment;
- domain researcher;
- experiment designer/operator;
- formal verifier;
- evidence auditor;
- engineering/CAD agent;
- science writer;
- history-of-ideas teacher;
- media curator;
- independent assessor.

Training records are versioned and evidence-based. A teaching agent cannot self-certify its own competency. Independent/expert qualification requires independent replication and external review references. Agent prompts must use explicit outputs, acceptance criteria, tool allowlists, source refs and resource limits.

## 9. Merlin Learning university LMS

Merlin Learning is a product layer on the same knowledge graph and agent infrastructure:
- adaptive course/objective graphs;
- personalized lessons and explanation modes;
- retrieval practice and spaced repetition;
- interleaving, worked examples, elaboration and transfer tasks;
- historical problem reconstruction and intellectual biographies;
- globally sourced, licensed media and primary sources;
- faculty authoring and approval;
- student and cohort analytics;
- LTI/QTI/Caliper/CASE/Edu-API interoperability;
- privacy, accessibility and institutional governance;
- measured educational outcomes, especially delayed retention and transfer.

The LMS consumes verified curriculum and research content; it does not turn unverified hypotheses into teaching facts. Content records must distinguish established knowledge, contested interpretation, open question and generated material.

## 10. Runtime, integrations and infrastructure

Known integration tracks:
- GitHub repositories and PR-based delivery;
- Avrea as the preferred available CI/compute runner when configured and within quota;
- OCI runner and object storage for durable execution/evidence where configured;
- Base44 for UI/app workflows and integrations where appropriate;
- Vercel for app/deployment paths where appropriate;
- UiPath Community Edition as an optional desktop automation bridge;
- local and remote inference, llama.cpp, Hermes Agent, NousCoder/Qwen role qualification;
- Kokoro local TTS and voice interfaces;
- FreeCAD, OpenSCAD, KiCad and ngspice;
- Lean 4/mathlib;
- public scholarly metadata/search APIs and public quantum compute APIs where permitted.

Do not assume credentials, service connectivity, remaining quotas, runner availability, successful deployment or provider qualification. Inspect before use. User preference has been to prioritize no-cost/free tiers, use Avrea where possible, and avoid unnecessary paid services. Never place secrets or model weights in Git.

## 11. Evidence, CI, security and production invariants

- Every attempted PR should produce complete logs and machine-readable results, including failed attempts.
- Bind evidence to exact repo, PR, head SHA, merge SHA where applicable, run ID/attempt, runner identity, tool versions and artifact digests.
- Keep failed and skipped jobs visible; skipped inference is not a pass.
- CACE artifact integrity is not mathematical proof or scientific truth.
- A SHA-256 digest proves byte identity, not signer identity. Production receipts need cryptographic signatures with pinned/revocable keys and explicit trust policy.
- Lean proof qualification must pin Lean/mathlib and audit axioms/dependencies.
- No automatic merge, deploy, destructive repair, provider promotion or authority expansion.
- Immutable artifact versions, append-only lineage, compare-and-swap updates and non-destructive recovery.
- No untrusted source text becomes agent instructions.
- Secrets stay in secret stores; credentials and private prompts are not logged.
- Human approval is required for consequential changes and release.

## 12. Repository PR index captured in this snapshot

The following PRs were found in the connected `Mannyspiro/expert-robot` repository search on 2026-11-05. They are references, not an assertion that every one is merged, complete or production-ready. Check each PR's current state and exact-head CI before depending on it.

| PR | Subject | Main relationship |
|---|---|---|
| #66 | Hermes coding and local Kokoro voice | Agents, local inference, voice and API foundations |
| #67 | Network streaming, Hermes and engineering IR | Model gateway, streaming and engineering |
| #68 | Runtime capability and qualification contracts | Capability states and qualification evidence |
| #69 | MCFC virtual fabric and CAD contracts | Resource leases and engineering |
| #70 | Research graph, hypothesis engine, CAD/electrical foundation | Knowledge graph and research-to-engineering |
| #71 | THTG theorem qualification on Avrea | Physics/math formal research evidence |
| #72 | Equation Atlas and XMG simulation engine | Xenomaths, glyphs, symbolic and simulation |
| #73 | Integration and operations handoff | Repository and provider integration map |
| #74 | UiPath Community Edition MVP | Desktop automation |
| #75 | Lean proof optimization atlas and tactic profiles | Formal verification |
| #76 | Canonical registry, provenance and research integrations | Knowledge and artifact source of truth |
| #77 | Canonical research, HUD and engineering adapters | Observability and integration |
| #78 | Hermes claim routing and Avrea quick reference | Agent routing and runner operation |
| #79 | Runner and CACE bridge documentation | Agent execution and evidence |
| #80 | Science, mathematics, history and philosophy atlas | Cross-domain knowledge and history |
| #81 | Preservation, recovery and non-destructive repair architecture | Data integrity and recovery |
| #82 | Immutable artifact versions, recovery and Hermes orchestration | Durable artifacts and repair lifecycle |
| #83 | Deterministic engineered prompt contracts | Task compilation |
| #84 | Prompt-bound worker results and leased acknowledgements | Result return and lifecycle |
| #85 | Source-commit binding and CACE verification bridge | Provenance and independent artifact checking |
| #86 | Complete CI test logs and evidence for every PR | PR evidence capture |
| #87 | Universal research curriculum and coder-teacher | Research training and Hermes education |
| #88 | Merlin Learning university LMS blueprint | Commercial adaptive learning product |

Important known status details at snapshot:
- PR #87 head `35f4bdfa8f039af899c51b15485621df066c886d`, CI run #2536 / ID `42117238909`: completed success. The curriculum suite reported 8 passed; the job also ran the wider build and guardrail suite.
- PR #88 head `1647d07ef46711385cd27a0cc6eb1fc3a1bb713d`, CI run #2537 / ID `42118324371`: completed success. The `build-and-smoke` job and all listed steps completed successfully, including prompt tests, curriculum tests, C++ tests, Merlin research/API, glyph Foundry, equation-atlas, engineering IR/CAD/coordinate-frame, CACE bridge and independent smoke tests. The separate NousCoder inference job was skipped; no inference qualification is claimed.
- PRs #87 and #88 are open draft PRs at the time of this snapshot. A successful CI run does not merge them or prove deployment.

## 13. Missing or under-specified work to turn into focused PRs

These are explicit follow-up PR candidates. Keep each independently reviewable and link it back to this registry.

### P0 — operational closure
1. **PR candidate: live Hermes consumer and end-to-end round trip.** Connect prompt outbox to a running Hermes consumer; dispatch to a bounded worker; return authenticated PromptResult; acknowledge lease; run CACE against exact artifact; show one reproducible end-to-end test and logs.
2. **PR candidate: signed CACE receipt profile.** Ed25519 or another approved signature scheme, key ID, trust roots, revocation, signer/verifier identity, source commit, artifact digest/path/kind/schema, producer/verifier tool versions and policy digest. Verify signature independently.
3. **PR candidate: Avrea/OCI evidence archive.** Durable retention beyond ephemeral CI artifact window; verify retrieval by digest; record quotas and job lifecycle.
4. **PR candidate: canonical registry query API and dashboard.** Read-only project/artifact/task/proof/CI queries from canonical data, not a second store.
5. **PR candidate: actual PR evidence enforcement.** Verify default-branch CI policy captures complete logs and result manifest for every PR, including cancelled/failed attempts; preserve long-term artifacts.

### P1 — mathematical and logic research
6. **PR candidate: Logic-as-Cultural-Lenses research atlas.** Source-grounded comparative history, formal logic profiles, translation/crosswalk records, explicit cultural-methodological caveats and teaching units.
7. **PR candidate: Xenomaths typed ideonomy and coordinate registry.** Formal schemas for objects, operations, spaces, bases, dimensions, transforms and invariants; enumeration is reproducible and novelty claims remain unverified until checked.
8. **PR candidate: XMG executable grammar and multi-frame object engine.** Parser, normalizer, rewrite semantics, confluence/termination qualification, frame conversion, visualization and simulation.
9. **PR candidate: Equation Atlas 081–100 and evidence receipts.** Extend entries with source crosswalk, assumptions, units, symbolic/dimensional/numerical checks, Lean status and Avrea receipts.
10. **PR candidate: n-ality and time-crystal research programs.** Define precise problems, literature maps, candidate conjectures, computational tests, and formal claims separately.
11. **PR candidate: THTG/UFT residual execution.** Complete source/action equations, Page-curve analysis, 5D dimensions/invariants, beta functions/fixed points, numerical/lattice checks and conditional Lean proofs.
12. **PR candidate: public quantum-compute adapter.** Provider-neutral API adapter, quota-aware job planner, circuit/result provenance, classical baselines, provider terms and reproducible benchmark; no claim of quantum advantage without evidence.

### P2 — engineering and scientific labs
13. **PR candidate: FreeCAD-to-Engineering-IR pipeline.** Import, typed conversion, unit/coordinate preservation, round-trip fixtures and geometry checks.
14. **PR candidate: electrical design pipeline.** KiCad adapter, connector/pin libraries with source provenance, netlist, wire/harness representation and reproducible ngspice.
15. **PR candidate: MCFC live scheduler.** Provider discovery, leases, quotas, job state, recovery and Avrea adapter with real runner evidence.
16. **PR candidate: cross-domain reproducible experiment runner.** Dataset manifests, environment locks, seeded execution, metrics, uncertainty, replication and CACE artifact checks.
17. **PR candidate: science/history/philosophy source atlas.** Primary-source and scholarship distinction, chronology, contributors, institutions, contested interpretations and curriculum export.

### P3 — learning and product
18. **PR candidate: Merlin Learning MVP runtime.** Single-course objective graph, learner state, retrieval practice, adaptive spaced review, transparent recommendations and student interface.
19. **PR candidate: instructor course studio.** Faculty authoring/review, rubrics, source citations, misconception analytics and course export.
20. **PR candidate: history/media provenance pipeline.** Rights/licensing, attribution, language, captions, cultural context, source confidence and faculty approval.
21. **PR candidate: LMS interoperability.** LTI 1.3, QTI, Caliper, CASE, SSO and institution test harness.
22. **PR candidate: learning efficacy pilot.** Pre-specified measures for delayed retention, transfer, workload, completion, accessibility and equity; engagement alone is insufficient.

## 14. Production acceptance gates

A feature can be called production-ready only when applicable gates pass:
- code exists on a reviewable branch and has an owner;
- schema and API contracts are versioned;
- tests cover success, failure, retries, stale leases, malformed evidence and boundary conditions;
- exact-head CI logs and machine-readable results are retained;
- Avrea or the intended runtime executes the real workload;
- CACE independently checks the returned artifact/evidence where applicable;
- security/privacy/authority constraints are tested;
- operational monitoring, failure recovery and retention are specified;
- independent review and user acceptance are recorded;
- deployment is verified against the exact commit and health checks.

A skipped test, missing log, unavailable provider, simulation, mock adapter or unexecuted workflow must be explicitly reported as such.

## 15. How Merlin should use Merlin to build Merlin

- Hermes reads this registry and selects the highest-value unblocked task.
- Coder-Teacher turns it into a versioned lesson and implementation plan.
- PromptCompiler creates a hash-bound task with exact source refs and acceptance criteria.
- Expert Robot performs a bounded patch in an isolated branch.
- Avrea runs tests/builds and retains logs/results.
- CACE checks artifact bytes and signed evidence; Lean handles formal claims.
- Independent assessor reviews the change and its claims.
- The registry is updated with PR, commit, run, artifacts, test results, limitations and next dependencies.
- Human approval controls merge, deploy, destructive repair and any authority-sensitive action.

This loop is the first self-improvement target: Merlin must become reliable at building, testing, explaining and preserving its own changes before it attempts more ambitious autonomous research.

## 16. Change control for this registry

When adding a new idea:
- search existing PRs/issues/docs first to avoid duplicate work;
- preserve the original wording and context in a source note;
- create a focused PR for a concrete artifact or implementation;
- update this index with the PR and dependency links;
- never rewrite a historical status without preserving the prior evidence;
- maintain a separate list of unknowns and unresolved contradictions;
- keep this document a map, not a substitute for detailed subsystem specifications.


## 2A. Existing mathematical idea infrastructure discovered during repository audit

The repository already contains a more detailed mathematical idea system. This registry must extend and link to it, not duplicate or replace it:

- `docs/research/MERLIN_MATHEMATICAL_IDEA_LEDGER_V0.1.md`: representation-first mathematics, multiple coordinate frames, complex/geometric algebras, eigenstructure, spacetime/time crystals, Xenomaths/glyph-native formalism, ideonomy, fractals/lacunarity, collective mathematics, CAD/MCFC bridges, XMG rewrite/confluence proof obligations, transition graphs, holonomy distinctions, archived-claim audit, and a four-representation rotation example.
- `docs/research/MERLIN_MATHEMATICAL_IDEA_INTAKE.md`: stable IDs, typed relations, provenance, status discipline and non-authority intake rules.
- `docs/research/merlin-mathematical-idea-catalog.v1.json`: structured idea catalog with controlled status and relation vocabularies.
- `scripts/merlin_math_idea_validate.py` and `tests/test_merlin_math_idea_validate.py`: standard-library catalog validation and tests.
- `merlin/representation_graph.py` and its tests: exact rational frame transformations, path composition, cycles, similarity invariants and eigenvector coordinate transport.
- `MERLIN_ARCHIVED_MATH_CLAIM_AUDIT_V0.1.md`: corrections to earlier speculative blow-up, Parrondo and PGA/CGA/QGA claims.
- Prior PR #2: [Build hybrid verified math research engine from refactored-fishstick](https://github.com/Mannyspiro/expert-robot/pull/2).
- PR #72: [Equation Atlas 001–080 and XMG Simulation Engine](https://github.com/Mannyspiro/expert-robot/pull/72).
- PR #75: [Lean proof optimization atlas and tactic profiles](https://github.com/Mannyspiro/expert-robot/pull/75).

**Important audit note:** the current CI workflow has `paths-ignore` entries for the mathematical ledger, intake, JSON catalog, validator and its test. Therefore changes limited to those files may not trigger the standard PR workflow. This must be reviewed and corrected so mathematical idea changes receive automated validation and retained test logs. The current registry PR includes the math program as a cross-linked inventory; it does not claim that the catalog is fully exhaustive or that every idea is formally established.

The existing catalog's statuses are scoped to individual claims. Keep that rule. The ledger already correctly distinguishes coordinate transition consistency from geometric holonomy and records that the finite XMG rewrite explorer does not prove global confluence.
