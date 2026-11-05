# Merlin Unified Mathematical Research and HUD Engineering Plan v1.0

Status: requirements baseline and implementation sequence; not a claim of a completed product.
Scope: integrate mathematical research, formal verification, engineering/CAD, orchestration and a minimal full-screen HUD.

## 1. Engineering method: induction and deduction

Merlin shall maintain two linked reasoning tracks.

### Inductive track — observations to requirements
- Collect observations from source repositories, tests, benchmark receipts, proof receipts, runtime telemetry, engineering artifacts and operator feedback.
- Normalize each observation with source identity, timestamp, exact revision, content digest, evidence class and uncertainty.
- Group repeated observations into patterns; distinguish a single failure from a reproducible pattern.
- Derive candidate requirements only when supported by traceable observations.
- Record counter-observations and unresolved assumptions instead of silently averaging them away.

### Deductive track — requirements to executable specifications
- Express each accepted requirement as typed inputs, outputs, invariants, failure states and acceptance tests.
- Derive module contracts and dependency edges from those requirements.
- Generate tests and proof obligations from invariants where practical.
- Reject implementation claims that exceed the evidence available from their tests, proofs or measurements.
- Feed observed test and runtime outcomes back into the inductive track.

Each requirement has: requirement_id, observation_refs, rationale, priority, owner_module, acceptance_tests, proof_obligations, evidence_class, status and revision.

## 2. Evidence hierarchy and mathematical claim discipline

Use distinct labels; never collapse them into one green check:
- observed: recorded input or behavior with source provenance
- reproduced: same declared procedure and environment reproduce the result
- numerically_supported: a numerical experiment supports a model within declared tolerances
- formally_proved: the exact proposition is kernel-checked under recorded assumptions and axiom dependencies
- independently_reviewed: a separate verifier or qualified reviewer checked the result
- empirically_validated: comparison with suitable real-world data and a declared validation protocol
- engineering_qualified: all project-specific engineering checks and approvals are complete

A content hash proves byte identity, not truth. A simulation proves behavior of its encoded model, not that the model describes reality. A Lean theorem proves its proposition from its assumptions, not the truth of those assumptions.

## 3. Unified Merlin system architecture

Canonical flow:

Research question -> hypothesis ledger -> representation/model builder -> experiment planner -> bounded execution -> evidence receipts -> independent verifier -> knowledge graph -> engineering/CAD projections -> HUD and operator decision.

Core services:
1. Project and artifact registry: canonical IDs, immutable content-addressed artifacts, project membership and read-only query API.
2. Provenance service: authenticated repository/commit metadata, workflow identity, artifact digests and retrieval records.
3. Mathematical research engine: equation atlas, typed representation graph, symbolic/numeric experiment adapters, conjecture ledger and proof obligations.
4. Proof Observatory: append-only attempts, theorem DAG, tactic/benchmark receipts and exact Lean qualification references.
5. Knowledge Graph: typed claims, assumptions, evidence, counterexamples, relations and revision-bound engineering views.
6. Engineering IR: parts, assemblies, coordinate frames, transforms, component pins, electrical nets, geometry and simulation references.
7. MCFC: resource measurement, admission, leases, quotas, cancellation and execution accounting.
8. Event outbox and Hermes adapter: durable event delivery, idempotency, lease recovery, result acknowledgement and quarantine.
9. Avrea adapter: explicit approval, bounded MCFC grant, runner identity, execution record and collected artifacts. No dispatch when provider/runner identity is unavailable.
10. CACE verifier: independent artifact, source, theorem, assumption, axiom and engineering-revision qualification.
11. HUD/API shell: read-only projections by default, one bottom conversation surface, explicit operator approvals.

## 4. Mathematical research is also Merlin's optimization engine

Merlin should use mathematics to improve its own research scheduling and representations, while keeping verification policy fixed.

### 4.1 Research task objective

Represent each candidate task with:
- expected_information_gain
- expected_verified_progress
- novelty
- reproducibility
- uncertainty
- compute_cost
- wall_time
- dependency_unlock_value
- verification_cost
- resource_demand

Do not compress all trade-offs into a single opaque score. First enforce hard constraints: policy permission, resource lease, provenance availability, reproducible input, and required approval. Then rank admissible tasks using a transparent multi-objective policy.

Initial utility estimate:

U(task) = wI*information_gain + wV*verified_progress + wD*dependency_unlock_value + wR*reproducibility - wC*compute_cost - wT*wall_time - wU*uncertainty - wQ*verification_cost.

Weights are versioned policy parameters, not model-generated authority. Keep Pareto-nondominated candidates visible so a high-novelty, high-cost experiment is not hidden by a single weighted sum. Report score components and uncertainty, not just the rank.

### 4.2 Adaptive allocation

- Start with cheap analytical reductions, dimensional analysis, symmetry checks and toy models.
- Use numerical experiments to discriminate between competing hypotheses, not merely generate plots.
- Escalate to symbolic derivation and Lean formalization when the statement and assumptions are stable.
- Use counterexample search and adversarial parameter sweeps before expensive runs.
- Allocate repeated runs according to measured variance and decision sensitivity.
- Stop when marginal expected information gain is below a configurable threshold, the resource budget is exhausted, or the evidence is sufficient for the next decision.
- Keep a held-out benchmark set to detect overfitting of Merlin's own optimizer.

### 4.3 Mathematical representation graph

Every mathematical object should have a typed representation with explicit conversion maps and loss annotations. Initial domains:
- scalar, vector, matrix and tensor
- complex numbers and polar form
- trigonometric and exponential representations
- Euclidean, affine and projective geometry
- quaternions and geometric algebra
- coordinate frames and spacetime projections
- eigenvalues, eigenspaces, spectral decompositions and invariant subspaces
- graph, topology, combinatorics and information-theoretic representations
- differential equations, dynamical systems and stochastic processes
- XMG / xenomathematical operators as explicitly experimental typed operators

A conversion edge records domain, codomain, assumptions, inverse status, numerical conditioning, units, invariants preserved, error bound and proof/experiment receipt. No representation is declared equivalent merely because its visualization looks similar.

### 4.4 Research lifecycle

Question -> definitions -> assumptions -> competing hypotheses -> minimal model -> dimensional/symmetry checks -> experiment design -> counterexample search -> numerical/symbolic evidence -> Lean formalization -> independent review -> claim status update.

Every negative result is retained with exact inputs and reason. Failed attempts are useful evidence and should not be silently discarded.

## 5. HUD product requirement

Design target: a full-screen research workspace with almost no chrome. The upper HUD is a live, animated activity visualization above the adaptive research canvas; the conversation surface stays anchored to the bottom.

### 5.1 Screen composition

Upper HUD activity layer (above the canvas): project/workspace identity; current task and phase; run state; agent/tool activity; event timeline; measured resources; evidence/verification state; connection status. Show animated process geometry (nodes, paths, pulses, dependency links and progress traces) driven by actual normalized telemetry and outbox events. If only demo data is available, label it DEMO and never present it as live runtime activity. This layer visualizes observable work—task transitions, model calls, tool invocations, experiment starts/results, proof checks, verification receipts and artifact registration—not private chain-of-thought or fabricated internal thoughts.

Adaptive research canvas (below the HUD): one active work surface at a time. It must change with the active stage: hypothesis graph, representation/coordinate transform, numerical plot, counterexample search space, theorem/proof DAG, verification evidence, artifact lineage, CAD assembly or wiring topology. The view is selected by task context and may animate geometry, but its displayed values and labels must be tied to actual event data or explicitly marked illustrative. It can be switched without navigating away from the conversation.

Bottom chat: persistent text composer, push-to-talk/voice control, attachment/context affordance, stop/cancel, and agent activity indicator. Conversation remains the primary control plane. Voice and text use the same task ID, authorization checks and event stream.

Nothing should float over the central work area except deliberately invoked contextual controls. Avoid dashboards full of cards, decorative charts, or duplicate navigation.

### 5.2 HUD states

- idle: objective and last verified state
- planning: proposed plan and expected resource envelope
- awaiting_approval: exact action, inputs, permissions, cost/time limits and diff
- running: live progress, current agent, resource consumption and cancellation
- verifying: independent verifier and outstanding proof/evidence obligations
- completed: result, artifact links, receipts and remaining caveats
- blocked: precise missing prerequisite and safe next action
- failed: error class, reproducible trace and retry proposal

### 5.3 Agentic interaction

Agents may propose plans, read approved project data, create isolated candidate artifacts, run bounded tools and prepare changes. They may not silently merge, deploy, widen credentials, alter policy, or exceed resource grants. Any action with external side effects must show a preview and require the relevant approval.

Voice is an input/output adapter to the same conversation and task protocol, not a separate privileged agent. Voice transcripts and tool actions must be linked to the same event/provenance trail as typed chat.

## 6. API and event contracts

Every operation uses a typed envelope:

{schema_version, request_id, project_id, actor, intent, inputs, input_digests, requested_capabilities, resource_budget, approval_ref, idempotency_key, created_at}.

Every result uses:

{schema_version, request_id, status, outputs, output_digests, source_commit_receipt, execution_receipt, verifier_receipts, resource_actuals, warnings, created_at}.

Read-only registry queries must not mutate state. Mutations are separate commands with explicit authorization, preview, idempotency and audit receipt. Outbox delivery is at-least-once; consumers must be idempotent. Cross-database atomicity is not assumed.

## 7. Ranked implementation sequence

### P0 — consolidate and establish one truth
1. Reconcile PRs #75, #76 and #77 into one canonical integration branch after checking overlapping file changes and exact ancestry. Do not merge blindly.
2. Run focused tests locally or on an authorized runner; record exact commit and environment. Resolve import, schema and migration drift.
3. Make the registry the canonical source for project/artifact IDs; expose read-only project, artifact, claim and receipt queries.
4. Add immutable provenance checks to graph nodes and edges, and make registry relations reject conflicting rewrites.
5. Add the outbox consumer lifecycle and restart recovery; test duplicate delivery, lease expiry, stale acknowledgements, quarantine and crash recovery.

### P1 — mathematical research as a first-class system
6. Build a typed hypothesis/claim ledger linked to the mathematical idea catalog and equation atlas.
7. Build the representation graph and conversion contract; start with complex/polar/trigonometric, matrices/eigenstructure, coordinate transforms and ODE systems.
8. Build an experiment planner that selects the cheapest discriminating experiment, records seeds/tolerances/units, and emits content-addressed receipts.
9. Integrate Lean theorem candidates and axiom reports; preserve assumptions and exact toolchain/manifest identity.
10. Add optimizer evaluation with fixed holdout problems, ablation comparisons and Pareto reports. Do not let the optimizer rewrite qualification rules.

### P2 — execution and independent verification
11. Authenticate GitHub repository/commit metadata and separately bind workflow run, runner identity and artifact digests.
12. Connect Hermes to durable outbox events and result acknowledgements.
13. Connect Avrea only when a live runner is confirmed; require operator approval and an MCFC LeaseBook grant before dispatch.
14. Connect CACE to verify exact source/artifact/proof receipts independently; record assumptions, axioms and qualification drift.

### P3 — engineering and visual workspace
15. Complete Engineering IR links from CAD geometry and coordinate frames to wiring nets and simulation artifacts.
16. Build the full-screen HUD shell with main canvas and bottom chat, first using deterministic mock adapters.
17. Add live project registry, proof, experiment, CAD and agent activity projections.
18. Add voice I/O through the same chat/task protocol; test interruption, cancellation, transcript provenance and permission parity.
19. Add agentic planning/execution only after approval previews, cancellation, leases, receipts and independent verification work end-to-end.

### P4 — qualification and release
20. Run an end-to-end vertical slice: question -> hypothesis -> experiment -> receipt -> proof/verification -> graph -> HUD -> operator-approved artifact change.
21. Run restart/crash recovery and duplicate-delivery tests.
22. Run resource exhaustion, timeout and cancellation tests under MCFC budgets.
23. Publish a reproducible local install and one-command development setup; document optional runner integrations without requiring paid services.
24. Promote only after independent qualification, review and explicit operator approval.

## 8. Acceptance criteria for a first genuinely useful Merlin

- One command starts the local registry/API and HUD in development mode.
- User can ask a mathematical question in the bottom chat and receive a visible plan before execution.
- The planner can choose an analytical, numerical or formal route and explain why.
- A seeded numerical experiment runs within a declared budget and emits a reproducible receipt.
- A Lean candidate is marked formally proved only after the exact configured Lean toolchain checks it.
- The graph links the question, assumptions, experiment, artifact, theorem and engineering revision by immutable IDs/digests.
- The HUD distinguishes planning, approval, running, verifying, completed, blocked and failed states.
- Voice and text use the same request identity, permission checks and event ledger.
- Agent actions are cancellable and bounded; no merge/deploy or authority escalation happens without approval.
- A process restart does not lose pending events or falsely mark unacknowledged work complete.

## 9. Immediate next implementation slice

Do not add another disconnected architecture document after this one. Implement the following in the existing Merlin branch:
1. Registry read API contract and query tests.
2. Hypothesis ledger schema with assumptions, evidence links, counterexamples and status transitions.
3. Representation conversion registry with explicit invariants and error bounds.
4. Experiment planner scoring record that exposes all objective components and hard constraints.
5. HUD state/event contract and a minimal shell wired to the read-only API.

Keep one integration PR open while these cohesive commits accumulate. Cut a new PR only for a separate review boundary, a release milestone, or a change that needs independent ownership. Do not create a PR for every file or chat turn.

## 10. Governance

Capability grows, authority never expands. Mathematical novelty is not verification. Simulation is not empirical validation. Hash identity is not authenticity unless its retrieval provenance is authenticated. A passing test is scoped to the exact code and environment tested. All claims in the HUD must be traceable to receipts and carry their evidence class.