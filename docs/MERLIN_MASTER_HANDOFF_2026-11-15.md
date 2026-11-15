# Merlin master handoff — 2026-11-15

**Purpose:** durable cross-chat, cross-agent and cross-repository project continuity. This is a navigation and engineering-state document, not proof evidence. Always re-query the referenced repositories, commits, workflow runs and artifact digests before relying on a status snapshot.

**Operating principle:** capability grows; authority never expands automatically.

## 1. Product objective

Build Merlin as a local-first, modular intelligence workbench that can research, teach, code, reason mathematically, develop engineering artifacts, generate media, and improve its own implementation under independent verification and explicit approval.

Merlin should eventually use itself to research, test and improve itself. It must not approve its own changes, promote its own candidates, or expand its own authority.

The product experience is a persistent voice/chat and agent workspace with:
- a central adaptive research canvas and evidence flow;
- visible agent assignments, jobs, resource state and results;
- an explorable knowledge graph and research branches;
- mathematics, formal proof, simulation and engineering objects as first-class artifacts;
- image/video generation and visual drafting;
- a mobile-capable Forge for projects, jobs, artifacts, evidence and controlled virtual-Git operations.

The UI should make thinking and doing inspectable without presenting simulations or animated visualizations as evidence.

## 2. Required operating method

Every Merlin engineering cycle follows the active production engineering plan:

1. Normalize user intent and repair high-confidence transcription errors without altering technical identifiers, hashes or quoted source.
2. Deduce contracts, data models, invariants, authority boundaries, failure states and acceptance criteria.
3. Induce from actual source code, workflow results, user interactions, provider behavior and failed attempts.
4. Reframe blocked problems through structural analogies while preserving constraints and invariants.
5. Use Ideonomy to enumerate distinct solution families, hypotheses, relationships, dependencies, falsifiers, feasibility, expected value, risk and verification cost.
6. Rank by merit and implement the highest-value reversible change that closes an observed gap.
7. Preserve exact commits, commands, toolchains, environments, results, logs, artifact digests and independent review evidence.
8. Update the engineering plan when observed evidence contradicts assumptions.
9. Require held-out evaluation, independent verification, rollback and explicit approval before promotion.

### Agent responsibilities

- **Ideonomy:** enumerate possible concepts, hypotheses, connections and alternative formulations before prematurely selecting one.
- **Planner:** maintain the dependency graph, acceptance criteria, ranked backlog and evidence-aware execution plan.
- **Hermes:** decompose tasks, teach and coach coding, implement bounded work, orchestrate agents and report exact results. Hermes is not an unrestricted shell or deployment authority.
- **Logos:** skeptical scientist and independent reviewer for all Merlin work. Search for counterexamples, missing assumptions, contradictions, overclaims and alternative explanations.
- **CACE:** independent typed verification, formal methods, exact artifact verification, policy enforcement and qualification. It must not sign its own evidence or accept self-reported digests as proof.
- **MCFC:** resource budgets, worker scheduling, leases, telemetry, concurrency and execution-fabric coordination.
- **Avrea:** preferred scalable runner when available; optional until availability is restored.
- **OCI:** alternate execution host with fixed, narrowly scoped jobs and non-destructive operating rules.
- **Council:** Systems Architect, Skeptical Scientist, Mathematician/Formal Methods Reviewer and Builder/Implementation Lead; voices remain distinct and evidence-aware.

## 3. Canonical architecture

One shared Merlin platform, not parallel product stacks:

- **Canonical registry:** project identity, artifact identity, immutable versions, provenance and lifecycle.
- **Knowledge graph:** typed concepts, claims, assumptions, hypotheses, equations, proofs, evidence, procedures, learning objectives and engineering objects.
- **Evidence and provenance:** immutable receipts binding exact source repository/commit, ArtifactRef, artifact digest, tool version, environment, result and signer.
- **Event outbox:** idempotent jobs, leases, heartbeats, acknowledgements, retries, cancellation and dead-letter handling.
- **Capability registry:** only `configured`, `unavailable`, or `unqualified`; configuration is not qualification.
- **Identity and policy:** verified principals, tenant isolation, least privilege, approvals and revocation.
- **Execution fabric:** Hermes routes; MCFC budgets and leases; Namespace/OCI/Avrea execute; CACE independently verifies.
- **Research and engineering:** source intake, Ideonomy, hypothesis ledger, math/Lean/numerical/counterexample loops, FreeCAD, engineering IR, wiring/netlists and ngspice.
- **Learning:** shared identity, graph, provenance and execution; curriculum, learner model, adaptive practice, faculty authoring and assessment.
- **HUD and Forge:** read-only canonical status/evidence views, jobs, graph exploration and controlled virtual repository operations.

CACE remains the typed source of truth for capability and verification contracts. Do not build a second duplicated JavaScript capability engine.

### Canonical artifact and knowledge ownership

The existing `MerlinRegistry` owns project artifacts, immutable content-addressed bytes, version history, exact `merlin-artifact-ref/1` references and producer provenance. The existing `MerlinKnowledgeGraph` owns typed knowledge relationships. The read-only `MerlinReadAPI` composes existing stores.

Do not create a second registry, artifact service, knowledge database, graph or event source of truth.

## 4. Current Expert Robot repository state

Primary repository: [Mannyspiro/expert-robot](https://github.com/Mannyspiro/expert-robot).

The latest inspected default branch is `main`. The repository contains multiple open draft PR stacks. Do not merge a stacked PR independently or out of dependency order. No deployment or production promotion is implied by a draft PR or CI pass.

### Active implementation threads

| PR | Scope | Current inspected state |
|---|---|---|
| [#165](https://github.com/Mannyspiro/expert-robot/pull/165) | Provenance-preserving knowledge representations | Draft; head `7fa1b109d52b9ab6a53de4fbb2a12b8ef0d7dbe0`; CI run `43756132171` SUCCESS |
| [#167](https://github.com/Mannyspiro/expert-robot/pull/167) | Exact-source reconstruction evaluator | Draft; head `9b8c74b76024bea77270b84edebcebb0c559f2b8`; CI run `43756841729` SUCCESS; all 6 new tests passed |
| [#168](https://github.com/Mannyspiro/expert-robot/pull/168) | Read-only knowledge representation query integration | Draft; head `53d3e9799256e3981e12e60ae7479dd4811b2041`; CI run `43757140668` SUCCESS; all 3 new tests passed |
| [#169](https://github.com/Mannyspiro/expert-robot/pull/169) | Source-located UTF-8 text extraction | Draft; head `eecaa93a96b913f9330673a41eba20065d9131c5`; CI run `43757628616` SUCCESS; all 7 new tests passed |
| [#170](https://github.com/Mannyspiro/expert-robot/pull/170) | Bounded Hermes knowledge-extraction stage | Draft; head `dc74a61dbe698189e1ece4105720261ccfa83548`; unified-platform run `43758293101` SUCCESS (236 tests); exact-head CI run `43758293058` SUCCESS (ledger 8, evidence 6, Hermes stage 7 tests) |
| [#164](https://github.com/Mannyspiro/expert-robot/pull/164) | Canonical backup recovery drill receipts | Draft; head `a5fea014fdc6f5991add69996aa6a49252e94eba`; stacked on #163 |
| [#163](https://github.com/Mannyspiro/expert-robot/pull/163) | Create-only OCI Object Storage backup transport | Draft; head `d873e1e419e78f10b9de83c7f56cd259a80b22fc`; adapter tests passed in run `43610431390`; live tenancy qualification outstanding |
| [#161](https://github.com/Mannyspiro/expert-robot/pull/161) | OCI Vault/KMS provider and deployment runbook | Draft; head `cdc22ab861ff71a27f4707887c2ef3772583398c`; CI run `43609808622` SUCCESS; live key/IAM round trip outstanding |
| [#159](https://github.com/Mannyspiro/expert-robot/pull/159) | Complete registry backup/restore package | Draft; head `32e877e8c5710cd9533b88b62530cee06b45a588`; CI run `43608688270` SUCCESS |
| [#158](https://github.com/Mannyspiro/expert-robot/pull/158) | Atomic qualification snapshot + Hermes outbox publication | Draft; head `079c3c82f273a80dd4fa5deabb90aaa3154a8e27`; CI run `43607987636` SUCCESS |
| [#150](https://github.com/Mannyspiro/expert-robot/pull/150) / [#149](https://github.com/Mannyspiro/expert-robot/pull/149) | Immutable qualification DAG history and read-only DAG runtime | Draft; exact heads and validation recorded in PRs |
| [#144](https://github.com/Mannyspiro/expert-robot/pull/144) | Artifact version lineage and ArtifactRef integration | Draft; current inspected head `5c61749cb1083e55804e0a3a9df2bad41f901f1b`; do not transfer earlier validation to this head without rechecking |
| [#143](https://github.com/Mannyspiro/expert-robot/pull/143) | Paired-state continuum simplex engine | Draft; current inspected head `a55865e120346a37e8d8545ccf90154b5ad583ae` |
| [#138](https://github.com/Mannyspiro/expert-robot/pull/138) | Persistent registry bootstrap and canonical knowledge graph | Draft; head `51577a9a34357a3b5de86778af2d09c8f07f4cd2`; bootstrap includes 58 mathematical ideas and 37 review-gated lesson blueprints |
| [#125](https://github.com/Mannyspiro/expert-robot/pull/125) | Adaptive mathematics foundations course and learner preferences | Draft; three learning paths: mathematician, mathematics programmer and computational hacker |
| [#123](https://github.com/Mannyspiro/expert-robot/pull/123) / [#120](https://github.com/Mannyspiro/expert-robot/pull/120) | Zero-first mathematics learning, Parrondo lesson/renderer, spaced repetition and strategy experiments | Draft; preserve existing learner persistence and pedagogical/formal authority separation |

PR #165 is stacked on #164 and therefore inherits its upstream dependency chain. It implements derived representations over the existing registry and graph; it does not create another store. Exact CI run #43756132171 passed, including all seven new knowledge-compression tests, the native build and C++ tests. The optional inference job was skipped. This is code/test evidence, not deployment or production qualification.

### Existing registry and graph capabilities

The current implementation already includes:
- SHA-256 content-addressed artifact bytes and project inventory;
- append-only artifact versions and per-version provenance;
- strict immutable ArtifactRefs with exact historical resolution and byte re-hashing;
- a typed provenance-aware knowledge graph;
- a read-only cross-domain query facade;
- an append-only qualification evidence DAG with deterministic snapshots;
- same-database atomic snapshot/outbox publication;
- idempotent worker/event outbox contracts;
- backup/restore verification for SQLite, referenced blobs, ArtifactRefs, DAG snapshots and outbox pointers.

PR #165 adds a deterministic source-bound derived representation manifest, exact source locators, tool/version metadata, a graph `object_view` and `derived_from` links. PR #167 adds bounded exact-source reconstruction; PR #168 exposes the verified manifest and source bindings through the existing read-only API; PR #169 adds strict UTF-8/Markdown extraction with exact byte and line locators. PR #170 adds an optional approval/lease-gated Hermes extraction stage, attaches the existing representation ArtifactRef to the hypothesis without copying bytes, and adds full-ArtifactRef-bound evidence idempotency. Lossy summaries remain derived and unverified; semantic equivalence is not assessed. Original artifacts remain immutable.

### Backup and recovery status

Local full-registry backup/restore is implemented and test-validated. KMS envelope encryption and OCI KMS/Object Storage adapter contracts are implemented and tested with controlled clients. The recovery receipt is an integrity-only preparation contract.

Not yet qualified:
- live OCI Vault/KMS GenerateDataEncryptionKey/Decrypt under the real instance principal;
- real Object Storage upload/read-back and bucket retention/IAM audit;
- independent CACE attestation of the exact recovery receipt;
- restore on a separate host with independently verified audit evidence and measured recovery time.

Never describe adapter tests as a live off-host backup or disaster-recovery drill.

## 5. Current CACE and RP2 formal-verification state

CACE repository: [morganaspim/Cace-app](https://github.com/morganaspim/Cace-app).

The active continuity/formal branch is PR [#102](https://github.com/morganaspim/Cace-app/pull/102), branch `fix/lean-proof-hole-guard-regex-20261113`. At the latest inspection its head was `cc76bef4761fcb5d8e409130efa1cbf7824cbd5a`, OPEN/DRAFT, based on `feat/merlin-continuum-oci-reproduction-20261112`.

### RP2 formalization

The quarantined file is `formal/cace_formal/CACEFormal/RP2ChainComplex.lean`.

The intended model is the six-vertex, fifteen-edge, ten-facet triangulation of real projective 2-space, with integral chain groups and boundary maps. Current source defines:
- the finite vertices, edges and facets;
- `boundary1` and `boundary2`;
- `boundary_squared_zero`;
- one-skeleton connectedness;
- linear boundary maps and homology objects `H0`, `H1`, `H2`.

The definitions of homology objects are not proofs of the desired group classifications. Required future results include integral `H0 ≅ ℤ`, `H1 ≅ ℤ/2ℤ`, and `H2 = 0`, with explicit assumptions and an independent Smith normal form/reference calculation.

### Latest exact-pin failure and correction status

CACE exact-pin run [#43741255348](https://github.com/morganaspim/Cace-app/actions/runs/43741255348) tested exact source head `88da2a15a9ed22b23c988354658a328a759a1b70`, Lean `leanprover/lean4:v4.32.1`, Mathlib commit `520045ab14e26149ee970e2e617ca04b09bde5d6`, with `compile_root=false`.

Observed:
- requested `CACEFormal.ContinuumSimplexCore` compiled successfully;
- the quarantined RP2 standalone compile failed in the two `map_smul'` proofs because the proof applied a Finset sum rewrite before explicitly normalizing the Fintype sum;
- `boundaryLinear_comp_zero` failed because tactic-selected extensionality reduced to a basis-map goal rather than an arbitrary 2-chain;
- audited root compilation was skipped;
- the run reported `qualification=false`.

The source was subsequently corrected on PR #102:
- commit `23552a46335c563d0bb84b6d49b21a1f493e6888`: explicitly convert the two Fintype sums to `Finset.univ` before factoring scalar multiplication and prove chain-map composition using `LinearMap.ext`;
- commit `669ca54e55f505e9d7a965ac30e8ef98f4e7747a`: add cheap regression checks for the proof shape;
- commit `7a713bc9e851887d4ef403966d5f31dd4e2dc120`: record the RP2 defect as F-035 (F-034 was already assigned to the exact-pin workflow input bug).

**The corrected RP2 source has not yet passed exact-head Lean compilation.** On exact PR head `aa02d4f9f916f9d38faf62beda09bb89f3b313ff`, CACE Collaboration Validation run `43756463757` succeeded; its Python regression suite and bug-sweep manifest passed (32 checked guard references, zero errors). This is not Lean compilation. Exact-pin runs `43756435490`, `43756455602`, and `43756463754` plus source-sanity runs `43756435479`, `43756455724`, and `43756463811` were cancelled before jobs started. The prior exact-pin failure on `88da2a15...` remains the latest actual Lean compile result. The RP2 module must remain quarantined. Do not claim the homology classification or formal qualification.

The exact-pin workflow supports pull-request path triggers and explicit workflow dispatch. The connected GitHub action surface does not expose a workflow-dispatch operation. The F-034 duplicate-ID collision was corrected by assigning the RP2 proof-shape defect F-035. On head `ee929fd708131fa5b85483395da2ee128e434fcc`, collaboration validation run `43757339436` succeeded: the F-035 source-shape guard passed, proof-policy validation passed, and the bug-sweep manifest reported zero errors. Exact-pin run `43757339510` compiled the requested module and reverse dependents but failed RP2 standalone compilation at lines 164 and 186 due product association not matching `Finset.mul_sum`; root was skipped and qualification remained false. Source commit `2256251f173df7e7d775731db5a38c372d708f99` adds `simp_rw [mul_assoc]`; guard commit `590ed1617226f5009bea8985fb9997faad14058a` requires association normalization and rejects `sorry`; F-035 is recorded in `c8e8519f0629b2df742843a9d93a43bf0a411be8`. A second orchestration defect (F-036) was identified: all three CACE workflows shared one concurrency group, so GitHub's single pending slot could cancel exact-pin before start. The workflows now use distinct exact-pin/source-sanity/collaboration groups, all with `cancel-in-progress: false`. Current head `cc76bef4761fcb5d8e409130efa1cbf7824cbd5a` has three pending runs: source sanity `43758690209`, exact pin `43758690226`, and collaboration `43758690153`. These are not passes yet. Do not claim RP2 proof success, homology classification or qualification until exact-pin compilation succeeds on this current head.

### Other CACE production gates

CACE ArtifactRef signing/verifying code exists, separate from the RSI reproduction verifier. PRs #103/#111 address signer-key filesystem custody; PR #108/#107 address independent trust-root and trust-store verification. These are draft branches, not live production configuration.

Still unavailable/unqualified:
- protected signer key and independent trust-root provisioning;
- live authenticated historical ArtifactRef resolution;
- live exact-byte attestation and verification through the deployed Merlin resolver;
- distinct protected main-only orchestrator run linked to exact OCI execution evidence;
- production CACE receipt bound to exact ArtifactRef/version and trusted signer identity.

CACE signatures establish provenance/integrity under a trusted key; they do not establish mathematical truth. The CACE ArtifactRef attestation contract uses verification-only authority and `proof_effect=none`.

### OCI runner safety and CI

CACE operational PRs include:
- #112: fail closed on skipped batched preflight stages;
- #113: instrument exact-pin cache restoration and require capacity headroom;
- #114: read-only inventory of existing OCI runner data.

Do not clean, overwrite, reinstall, delete or migrate runner caches based on stale inventory. Preserve existing OCI data. The latest exact-pin run restored the pinned Lean/Mathlib package tree successfully; that does not imply current free capacity or qualify a later host state.

## 6. Mathematics learning and research

Merlin has three connected learning paths:
1. mathematician;
2. mathematics programmer;
3. computational hacker/problem solver.

Teaching principles:
- zero-first and concrete-first explanations;
- one new concept at a time when appropriate;
- worked examples, hints, assessments, transfer prompts and progressive difficulty;
- separate pedagogical mastery from formal proof authority;
- learner identity must be authenticated and tenant-scoped;
- raw conversation text should not be silently copied into learner telemetry.

The current idea catalog and backlog are represented in the canonical graph; unpublished research candidates must not be promoted into established lessons. Parrondo-inspired strategy experiments should measure immediate accuracy, delayed retention, transfer and independent problem-solving, not optimize only short-term correctness.

The Math Discovery Engine should connect Ideonomy candidates to structured claims, explicit assumptions, falsifiers, Lean source, numerical experiments and finite counterexample search. Every result must bind exact inputs, source commit, toolchain, solver, seed, precision and output digest. A Python numerical reference is not a Lean proof or a CACE attestation.

Other open research includes equation-atlas work, mathematical transfer, continuum simplex, RP2 homology, formal theorem dependencies, numerical reproducibility and held-out evaluation. Preserve hypotheses as hypotheses until the relevant proof or experiment passes.

## 7. Engineering, CAD, wiring and simulation

Use one typed engineering representation for geometry, dimensions, units, coordinate frames, materials, constraints, topology and revision identity.

Existing work includes structural engineering IR, CAD assembly models, FreeCAD bridge/document adapters, coordinate frames, physical connectivity, wire routing, netlist exports and ngspice adapter work.

Important limits:
- a geometry preflight or rendered model is not a qualified CAD result;
- a netlist is not an electrical safety certificate;
- a simulation adapter test is not a verified external ngspice execution;
- production qualification requires exact tool versions, source/input digests, resource receipts, output digests and independent checks.

Future FreeCAD work must install/integrate the real Linux application and exercise real import/export and assembly operations. Do not describe structural metadata tests as a working FreeCAD runtime.

## 8. Image, video, voice, HUD and Forge

Image/video generation should be treated as a first-class artifact-producing capability, not a detached demo. Preserve source prompts, model and workflow identities, model licenses, generation parameters, seed where supported, tool version, input references and output digests. Use Linux x86-64-compatible open-source applications and workflows where practical. Do not commit large model weights or credentials to Git; keep model assets in ignored or external content-addressed storage with manifests and provenance.

Voice and council work should retain explicit stop/cancel behavior, honest unavailable states and bounded tool permissions. The HUD should show current project, active agent, job, resource budget, evidence and approval state. Visualizations of internal reasoning are explanatory UI, not literal proof of hidden model computation.

The virtual repository direction is a headless, internal Git-like system with SQLite commits, branches, diffs, virtual PRs, three-way merges, conflicts, rollback, isolated workspaces and CI receipts. GitHub PRs remain useful for source review and external collaboration but should not become the only user-facing workflow. No automated merge or deployment without explicit approval and passing evidence.

## 9. Runtime, compute and security constraints

- Target Merlin software and applications for Linux x86-64 unless a specific worker is explicitly ARM64.
- Avrea is assumed unavailable until the first of next month (2026-12-01) unless the user updates that assumption.
- Use the existing Namespace runner for ordinary Expert Robot CI where configured; use OCI only for the specific pinned workflows that require it.
- Avoid unnecessary runner retriggers, repeated heavyweight downloads, redundant model downloads, and speculative cloud work.
- Do not request routine manual workflows. Intervene manually only when permissions, protected credentials, approvals or an unavailable manual-dispatch action make it unavoidable.
- Never expose secrets, private keys, runner credentials or plaintext data keys in logs, Git or model-visible artifacts.
- Preserve existing OCI runner files and caches. No destructive cleanup without a separately verified backup and explicit approval.
- Capability may grow; authority must not expand automatically.
- No agent may self-approve, self-promote, bypass CACE, or turn a failed/ambiguous state into a pass.
- Keep Titan security/encryption research separate from the experimental invention graph.

## 10. Ranked next actions

1. **Complete the RP2 exact-head correction loop.** Run cheap source/guard checks on PR #102 head `aa02d4f...`; obtain one authorized exact-pin Lean dispatch on that exact head; inspect logs. If it passes, keep RP2 quarantined and proceed to homology classification. If it fails, fix only the observed failure and add a regression class.
2. **Complete the knowledge representation PR #165 review loop.** Its exact CI run `43756132171` passed. Next add an independent reconstruction evaluator and omission/contradiction benchmarks before introducing model-based semantic compression.
3. **Reconcile the stacked registry/backup chain.** Preserve #164 → #163 → #161 → #159 → #158 → #150 → #149 and its upstream dependencies. Do not merge individual stacked branches out of order. Complete live KMS/Object Storage and separate-host recovery qualification only when protected configuration and runner capacity are confirmed.
4. **Complete the Merlin–CACE ArtifactRef trust chain.** Reconcile signer-custody and trust-root PRs; verify live resolver-owned provenance and exact historical bytes; retain verification-only authority.
5. **Connect knowledge retrieval to existing APIs.** Extend `MerlinReadAPI`; do not add a parallel registry or database. Add source extractors with page/line/frame/timecode locators.
6. **Connect Ideonomy, Hermes, Logos and MCFC.** Add bounded, idempotent extraction/representation jobs with explicit leases, cancellation, budgets, failure classes and evidence receipts.
7. **Advance mathematics, engineering and media adapters by observed evidence.** Keep Lean, numerical, CAD, wiring, ngspice, image and video capabilities independently qualified by domain-specific benchmarks.
8. **Maintain one evolving production engineering plan and handoff.** Update this file and the detailed subsystem documents after meaningful changes; always re-query live GitHub state rather than treating this snapshot as current truth.

## 11. Read-first subsystem documents

- Expert Robot production plan: `docs/merlin/MERLIN_PRODUCTION_ENGINEERING_PLAN_V1_2.md`
- Artifact version lineage: `docs/merlin/MERLIN_ARTIFACT_VERSION_LINEAGE_V1.md`
- Qualification evidence DAG: `docs/merlin/QUALIFICATION_EVIDENCE_DAG_V1.md`
- Knowledge compression: `docs/merlin/KNOWLEDGE_COMPRESSION_V1.md` (introduced by PR #165)
- OCI backup deployment/qualification: `docs/merlin/OCI_KMS_BACKUP_DEPLOYMENT.md`
- CACE production handoff: `docs/MERLIN_PRODUCTION_HANDOFF.md` in `morganaspim/Cace-app`
- OCI runner operations: `docs/OCI_RUNNER_OPERATIONS.md` in `morganaspim/Cace-app`

When continuing, read these documents and inspect the exact current PR heads and workflow evidence before making changes.
