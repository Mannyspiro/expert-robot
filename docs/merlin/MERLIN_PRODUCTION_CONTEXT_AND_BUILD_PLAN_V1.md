# Merlin Production Context and Build Plan v1

**Purpose:** consolidate the relevant Merlin and Merlin Learning decisions from prior prompt/response work into one implementation contract. This is a planning and traceability artifact; it does not certify unfinished components as production-ready.

## 1. Product boundary

Merlin is the shared research, engineering, orchestration and knowledge platform. Merlin Learning is a first-party learning product built on the same registry, evidence, agent, model and execution services. Do not create a second independent AI stack for the LMS.

The current phone, headphone, smart-TV and general IoT ideas remain backlog concepts. They are not part of the present production critical path.

## 2. Canonical platform

The target platform is organized around durable, versioned services:

1. **Canonical project and artifact registry** — stable project IDs, universal artifact records, content digests, immutable versions, provenance and read-only inventory APIs.
2. **Knowledge graph** — typed entities and relationships for projects, research questions, hypotheses, papers, equations, claims, proofs, datasets, experiments, engineering assemblies, lessons and competencies.
3. **Event outbox** — durable task/event publication, idempotency, leases, heartbeats, acknowledgements, retries and dead-letter handling.
4. **Capability registry** — only configured, unavailable or unqualified; declarations alone never prove a capability works.
5. **Artifact/evidence service** — source repository and verified commit, exact artifact digest, toolchain/configuration, execution logs, provenance and independent verification receipt.
6. **Identity and policy service** — authenticated users and service identities, scoped permissions, explicit approvals, audit trails, tenant boundaries and revocation.
7. **Observability** — request/job IDs, structured logs, metrics, traces, resource use, failure reasons and reproducible run manifests.

The capability and graph HTTP contracts now have a tested first implementation in PR #109. The course and LMS platform foundation is in PR #108. Both remain draft and unmerged.

## 3. Agent and execution organization

- **Merlin Core:** user-facing reasoning, research canvas, persistent project context and prompt engineering.
- **Hermes:** planner, task decomposer, curriculum coordinator and event/outbox dispatcher. It produces typed task contracts rather than arbitrary shell commands.
- **MCFC:** virtual compute fabric; resource budgets, scheduling, execution leases, worker telemetry and module dependencies.
- **Avrea:** preferred reproducible execution runner when available. Its build cache is not a database, inference service or durable runtime.
- **OCI:** alternate execution provider to qualify from the morgana cace repository; do not mark it configured until an actual run and receipt prove it.
- **CACE:** independent verifier for exact submitted artifacts, formal proofs, test results and execution evidence. A local test double is never represented as real CACE verification.
- **Council:** specialist perspectives with explicit roles, evidence packets, disagreement and uncertainty. Simulated personas are not independent external experts.
- **Coder-Teacher:** maintains code, tests, agent tooling and training curriculum; it cannot approve its own high-impact changes.
- **Independent Assessor:** separated from the agent that generated or taught the work.

The intended execution cycle is: intent → typed prompt/task contract → preview and policy check → explicit approval when required → outbox publication → leased worker → reproducible artifact/logs → result acknowledgement → CACE verification → registry/graph update.

## 4. Research and invention portfolio

### 4.1 Established and reproducible mathematics

Build the equation atlas and Math Kung Fu as a research-to-learning pipeline:
- canonical equation entries with source citations, symbols, dimensions, assumptions and applicability boundaries;
- symbolic and dimensional checks;
- numerical experiments with pinned solver, parameters, seed, precision and environment;
- counterexample searches over declared domains;
- Lean formalization only when assumptions and theorem statements are precise;
- regression tests and independent CACE receipts;
- lesson objects generated from verified examples, not from unsupported claims.

Core mathematical tool families include linear algebra, optimization, Fourier methods, probability/statistics, graph theory, state-space/Kalman methods, differential equations, conservation laws, numerical analysis and formal methods.

### 4.2 Experimental mathematics

XMG multi-frame representations, Xenomaths, glyph operators, n-ality structures, time-crystal ideas and related novel mathematical systems remain experimental research tracks. Store their definitions, coordinate conventions, transformation rules, invariants, examples, conjectures and falsifiers as versioned research artifacts. Do not silently promote a notation, analogy, simulation or numerical pattern into an established theorem.

### 4.3 Physics and quantum research

Provide research adapters for public quantum-computing systems and APIs, including provider discovery, authentication, job submission, queue/status retrieval, result provenance, cost/resource budgets and simulator-versus-hardware labeling. Potential research areas include quantum information, QFT and the user's UQFT/QFTOE questions. A simulator result, provider demo or hardware job is evidence of that run only; it is not by itself a physical theory validation.

### 4.4 Scientific breadth

Use the universal research curriculum as the competence framework across mathematics, physics, chemistry/materials, biology, medicine/health, Earth/environment, computer science/AI, engineering, social/behavioral sciences, humanities/history, economics/business, arts/design and interdisciplinary research. The current curriculum baseline records 13 domain families, 221 subdomains and 18 reusable competencies. Keep the taxonomy many-to-many rather than forcing fields into isolated silos.

## 5. Engineering and virtual laboratory

- Import actual FreeCAD documents and assemblies; do not stop at a generic geometry sketch.
- Convert source models into a typed engineering IR with units, constraints, parts, joints, materials and provenance.
- Generate and validate wiring diagrams/netlists with explicit component and pin relationships.
- Run real ngspice through a pinned adapter; capture version, netlist digest, parameters, solver settings, logs, outputs and resource use.
- Add thermal, electrical, mechanical, manufacturing and safety checks with traceable requirements and qualified human review where appropriate.
- Keep simulation evidence distinct from physical test evidence.
- Represent CAD assemblies, wiring and simulation dependencies in the knowledge graph.

## 6. Multimedia and prompt engineering

Merlin should compile user intent into engineered prompts for text, research, image, video, CAD and simulation subsystems. Prompt contracts should carry objective, audience, format, references, constraints, exclusions, continuity/state, success criteria and required evidence. Store prompt version, model/provider version, input references, generated artifact digest and reviewer state. Preserve video direction continuity across shots and frames; label generated media and never present it as historical primary evidence.

## 7. Titan — isolated cryptographic research track

Titan remains separate from the experimental invention graph and ordinary user-facing research context. Its workstream includes pinned post-quantum cryptography providers, upstream provenance, reproducible installation, official FIPS 203/204/205 test vectors, Lean models for transcript binding/key separation/hybrid composition/downgrade invariants, and CACE verification of the actual Avrea/OCI evidence bundle. A cryptographic receipt must bind signer identity, source commit, exact artifact digest, toolchain and verification result.

## 8. Merlin Learning

Merlin Learning is the university/adaptive LMS product, not merely a tutoring prompt.

### Learner experience
- Versioned course → module → objective → concept/skill → prerequisite graph.
- Low-stakes diagnostics; student-selected goals, pace and study schedule.
- Retrieval practice, spaced review, interleaving, elaboration, worked-example fading, multimodal explanations, self-explanation and transfer tasks.
- Transparent objective-level mastery and uncertainty; no opaque single learner score.
- Explainable recommendations with student override and inspect/export controls.
- Historical and intellectual pathways using primary sources, competing explanations, social context and global contributions.
- Licensed/open media with creator, source, license, language, region, date and accessibility metadata.
- AI-generated teaching content is labeled and reviewed; it is not represented as a primary source.

### Faculty and institution experience
- Course authoring/import, objective mapping, resource curation, assessment/rubric authoring and approval workflows.
- Faculty review of generated materials and source citations.
- Cohort-level misconception and progress summaries with privacy-preserving thresholds.
- Institution roles, SSO, audit, retention/deletion/export, data residency options and integration controls.
- Design for LTI 1.3/LTI Advantage, QTI, Caliper Analytics, CASE, Edu-API, documented REST/webhooks and CSV interchange.
- Target WCAG 2.2 AA.
- FERPA and applicable privacy obligations require qualified legal/security review before institutional deployment.
- Do not sell student data or use identifiable student records to train general models.
- Do not optimize for compulsive engagement, punitive streaks or time-on-platform. Evaluate delayed retention, transfer, mastery, workload, accessibility, course completion and faculty time.

### Teaching agents
Hermes Learning Coordinator, Subject Teacher, Learning Scientist, History-of-Ideas Teacher, Media Curator, Assessment Designer, Feedback Coach, Accessibility/Linguistic Reviewer, Faculty Copilot and Independent Assessor have bounded roles. Teaching agents cannot self-certify mastery or silently change grading/course policy.

## 9. Learning from interaction and controlled self-improvement

Merlin should improve from observed use and research outcomes, but data use is governed:
- default to operational metadata and explicit categorical feedback, not indiscriminate raw conversation retention;
- separate user memory, product telemetry, training data and research evidence;
- require consent and clear purpose before retaining user content for learning;
- aggregate only after minimum-sample thresholds; redact secrets and sensitive data;
- turn observations into versioned improvement hypotheses, not automatic production changes;
- evaluate on held-out tasks and paired comparisons;
- require independent review, policy checks, explicit approval for high-impact changes, rollback and CACE evidence;
- keep negative results and failed runs in the ledger;
- capability may grow, but authority does not expand automatically.

## 10. Virtual Git and CI

The preferred product workflow is Merlin's internal/headless Git-like system: SQLite-backed commits, branches, virtual PRs, event history, 3-way merges, conflicts, rebase, rollback and isolated CI workspaces. GitHub remains an upstream/read-only provenance adapter where useful, not the main user workflow.

Every attempted PR/job must preserve exact commit identity, command, environment, tool versions, timestamps, exit code, stdout/stderr, test summaries and artifact digests. Failed, cancelled, queued and unstarted jobs must be reported distinctly. A missing log is a blocker, not a pass.

## 11. Runtime and deployment facts to preserve

- The current Merlin MVP HTTP server binds to 127.0.0.1; it is not a production network service.
- Never expose it directly on 0.0.0.0 without authenticated HTTPS gateway, tenant-aware authorization, rate limits and operational hardening.
- Provider status is separate from provider health and held-out qualification.
- Avrea reported no credits available for a recent PR job; hosted GitHub Actions was used for the learning evidence workflows. OCI remains to be qualified with a real job.
- Do not equate build cache, model cache, inference workers, execution workers and durable storage.
- No current deployment, SSO, institutional pilot, CACE production transport or verified Avrea/OCI runtime is implied by these source changes.

## 12. Ranked production sequence

1. **Security and identity foundation:** verified OIDC/SSO, service identities, tenant-scoped authorization, secret management, HTTPS gateway, rate limiting, CSRF/origin policy, backup/restore and data lifecycle.
2. **Canonical registry and graph:** unify projects, artifacts, claims, equations, lessons, competencies and provenance; verify upstream commit identity and content digest; connect graph validation to the persisted graph.
3. **Reliable event execution:** Hermes outbox/ack lifecycle, idempotency, leases, heartbeats, cancellation, retries, resource limits and dead letters.
4. **Execution-provider qualification:** real Avrea and OCI jobs with reproducible workspaces, pinned dependencies, resource receipts and retained logs.
5. **Independent CACE evidence:** authenticated transport and signer identity; exact artifact/commit/tool binding; fail closed if CACE is not reachable or configured.
6. **Merlin Core research loop:** engineered prompts, council, evidence-aware search, hypothesis ledger, equation atlas, Lean/numerical/counterexample runners and reproducible research artifacts.
7. **Engineering/virtual lab:** FreeCAD importer, engineering IR, wiring/netlist generation, real ngspice, CAD and simulation evidence.
8. **Merlin Learning product:** real identity/tenant integration, learner and faculty interfaces, objective graph, assessment workflows, accessible content studio, privacy/export/delete, interoperability and a faculty-led pilot.
9. **Provider/media expansion:** qualified model routing, voice, image/video, public quantum provider adapters and specialist tools.
10. **Governed self-improvement:** measured interaction-to-hypothesis pipeline, held-out evaluation, independent review, staged rollout and rollback.
11. **Operational launch:** deployment automation, monitoring, incident response, service-level objectives, restore drills, accessibility review, institutional/legal review and production acceptance.

A phase is complete only when its acceptance evidence exists in the canonical registry and can be independently reproduced. Draft PRs, architecture documents and green unit tests are useful progress, but none alone means production readiness.
