# Merlin production coverage and backlog — 2026-11-17

This plan preserves the supplied project corpus and ranks production closure. It is a planning record, not a claim that the full Merlin platform is deployed, independently verified or assigned to an active owner. The parent deployment task owns current service verification; this pass performed no network, VM, merge or deployment actions.

The machine-readable companion is [`dot-production-coverage-20261117.json`](../config/merlin/dot-production-coverage-20261117.json). It retains every captured repository document, relevant Drive asset and supplied PR snapshot without copying raw private chat content or unrelated personal document titles.

## Coverage and evidence boundary

| Source set | Preserved/reviewed in this plan | Limit |
| --- | --- | --- |
| Repository docs/configs | 191 individual records; all 191 captured byte sizes and Git blob hashes match; SHA-256 recorded | Byte identity does not establish current implementation or qualification |
| Full content review | Four master documents listed below | The other 187 are indexed and queued, not semantically reviewed |
| Drive document listing | 283 metadata entries over three supplied pages; 112 project-relevant entries retained | The supplied complete flag applies to that listing, not all Drive contents |
| Known Merlin folder | All 36 metadata records retained | Folder membership is not validation or executable readiness |
| Useful asset union | 134 unique Drive file IDs | Metadata inventory plus one reviewed bounded OBJ intake report; remaining content hashes unknown |
| PR snapshots | 100 records, including 88 open at capture | Not a complete/current PR census; no active ownership, merge or deployment inferred |
| Parent project chat/context set | 41 records acknowledged as available to the parent | Not every account chat or every raw transcript; not reread in this planning pass |

The four sources read fully for this synthesis are:

- `config/merlin/project_catalog.v1.json` — Git blob `36312197c82d46a57513b9c04cdf461d5dd631ce`; [exact captured source](https://api.github.com/repos/Mannyspiro/expert-robot/git/blobs/36312197c82d46a57513b9c04cdf461d5dd631ce).
- `docs/merlin/MERLIN_MASTER_IDEA_REGISTRY_AND_SYSTEM_MAP_V1.md` — Git blob `672bab43b15f2336865762c599ed387585ee7b3e`; [exact captured source](https://api.github.com/repos/Mannyspiro/expert-robot/git/blobs/672bab43b15f2336865762c599ed387585ee7b3e).
- `docs/merlin/MERLIN_PRODUCTION_ENGINEERING_PLAN_V1_2.md` — Git blob `fb05e051b5a2b181c2823bbce986da1c8a756ba7`; [exact captured source](https://api.github.com/repos/Mannyspiro/expert-robot/git/blobs/fb05e051b5a2b181c2823bbce986da1c8a756ba7).
- `docs/research/MERLIN_MASTER_CHAT_IDEA_LEDGER_2026-11-04.md` — Git blob `188f3d4c047384c40fce522b50cee52263ee97de`; [exact captured source](https://api.github.com/repos/Mannyspiro/expert-robot/git/blobs/188f3d4c047384c40fce522b50cee52263ee97de).

Their older test counts, run IDs, branch names and capability statuses remain historical reports. They are not carried forward as evidence for the current deployed source. The original project catalog already labels its archive intake and raw-chat coverage partial.

## Ranked production closure

| Rank | Track | Concrete acceptance target | Related open PRs at capture |
| --- | --- | --- | --- |
| P00 | Private OCI service and operational recovery | A narrowly granted private service whose exact source, runtime, state and recovery are inspectable. | [#79](https://github.com/Mannyspiro/expert-robot/pull/79), [#81](https://github.com/Mannyspiro/expert-robot/pull/81), [#82](https://github.com/Mannyspiro/expert-robot/pull/82), [#124](https://github.com/Mannyspiro/expert-robot/pull/124), [#136](https://github.com/Mannyspiro/expert-robot/pull/136), [#159](https://github.com/Mannyspiro/expert-robot/pull/159), [#161](https://github.com/Mannyspiro/expert-robot/pull/161), [#163](https://github.com/Mannyspiro/expert-robot/pull/163), [#164](https://github.com/Mannyspiro/expert-robot/pull/164) |
| P01 | Source-complete project context and retrieval | Dot resumes from source-cited project context with visible coverage, supersession and review state. | [#138](https://github.com/Mannyspiro/expert-robot/pull/138), [#144](https://github.com/Mannyspiro/expert-robot/pull/144), [#165](https://github.com/Mannyspiro/expert-robot/pull/165), [#166](https://github.com/Mannyspiro/expert-robot/pull/166), [#167](https://github.com/Mannyspiro/expert-robot/pull/167), [#168](https://github.com/Mannyspiro/expert-robot/pull/168), [#169](https://github.com/Mannyspiro/expert-robot/pull/169), [#170](https://github.com/Mannyspiro/expert-robot/pull/170), [#177](https://github.com/Mannyspiro/expert-robot/pull/177) |
| P02 | Identity, scopes and separation of authority | Read, request, execute, sign and deploy roles remain separate and bound to real host-owned identities. | [#111](https://github.com/Mannyspiro/expert-robot/pull/111), [#112](https://github.com/Mannyspiro/expert-robot/pull/112), [#113](https://github.com/Mannyspiro/expert-robot/pull/113), [#118](https://github.com/Mannyspiro/expert-robot/pull/118), [#139](https://github.com/Mannyspiro/expert-robot/pull/139), [#140](https://github.com/Mannyspiro/expert-robot/pull/140) |
| P03 | Real two-coder and independent-evaluator improvement loop | Two configured coders produce reviewable alternatives that are evaluated independently and resumably. | [#119](https://github.com/Mannyspiro/expert-robot/pull/119), [#130](https://github.com/Mannyspiro/expert-robot/pull/130), [#131](https://github.com/Mannyspiro/expert-robot/pull/131), [#132](https://github.com/Mannyspiro/expert-robot/pull/132), [#133](https://github.com/Mannyspiro/expert-robot/pull/133), [#135](https://github.com/Mannyspiro/expert-robot/pull/135), [#171](https://github.com/Mannyspiro/expert-robot/pull/171), [#172](https://github.com/Mannyspiro/expert-robot/pull/172), [#175](https://github.com/Mannyspiro/expert-robot/pull/175), [#176](https://github.com/Mannyspiro/expert-robot/pull/176) |
| P04 | Hermes orchestration and MCFC execution fabric | One real bounded task completes through canonical outbox, leases, isolated worker and versioned result. | [#83](https://github.com/Mannyspiro/expert-robot/pull/83), [#84](https://github.com/Mannyspiro/expert-robot/pull/84), [#94](https://github.com/Mannyspiro/expert-robot/pull/94), [#96](https://github.com/Mannyspiro/expert-robot/pull/96), [#128](https://github.com/Mannyspiro/expert-robot/pull/128), [#129](https://github.com/Mannyspiro/expert-robot/pull/129), [#130](https://github.com/Mannyspiro/expert-robot/pull/130), [#158](https://github.com/Mannyspiro/expert-robot/pull/158), [#170](https://github.com/Mannyspiro/expert-robot/pull/170), [#172](https://github.com/Mannyspiro/expert-robot/pull/172) |
| P05 | Independent CACE and formal evidence closure | An independent verifier checks exact artifacts and emits authenticated, policy-bound receipts. | [#85](https://github.com/Mannyspiro/expert-robot/pull/85), [#139](https://github.com/Mannyspiro/expert-robot/pull/139), [#140](https://github.com/Mannyspiro/expert-robot/pull/140), [#148](https://github.com/Mannyspiro/expert-robot/pull/148), [#149](https://github.com/Mannyspiro/expert-robot/pull/149), [#150](https://github.com/Mannyspiro/expert-robot/pull/150), [#156](https://github.com/Mannyspiro/expert-robot/pull/156), [#157](https://github.com/Mannyspiro/expert-robot/pull/157), [#158](https://github.com/Mannyspiro/expert-robot/pull/158) |
| P06 | Native CAD, wiring and simulation round trip | A single canonical engineering revision survives native CAD and electrical simulation with reproducible artifacts. | [#77](https://github.com/Mannyspiro/expert-robot/pull/77), [#139](https://github.com/Mannyspiro/expert-robot/pull/139), [#140](https://github.com/Mannyspiro/expert-robot/pull/140), [#141](https://github.com/Mannyspiro/expert-robot/pull/141), [#143](https://github.com/Mannyspiro/expert-robot/pull/143), [#173](https://github.com/Mannyspiro/expert-robot/pull/173), [#174](https://github.com/Mannyspiro/expert-robot/pull/174) |
| P07 | HUD, Forge, voice and Merlin Learning | Useful visible workflows consume canonical state and reviewed content, rather than parallel truth stores. | [#88](https://github.com/Mannyspiro/expert-robot/pull/88), [#95](https://github.com/Mannyspiro/expert-robot/pull/95), [#98](https://github.com/Mannyspiro/expert-robot/pull/98), [#106](https://github.com/Mannyspiro/expert-robot/pull/106), [#108](https://github.com/Mannyspiro/expert-robot/pull/108), [#112](https://github.com/Mannyspiro/expert-robot/pull/112), [#113](https://github.com/Mannyspiro/expert-robot/pull/113), [#115](https://github.com/Mannyspiro/expert-robot/pull/115), [#120](https://github.com/Mannyspiro/expert-robot/pull/120), [#125](https://github.com/Mannyspiro/expert-robot/pull/125), [#137](https://github.com/Mannyspiro/expert-robot/pull/137) |
| P08 | Model loading, context efficiency and measured optimization | Choose a reproducible capability/cost/latency tradeoff on the actual hardware. | [#116](https://github.com/Mannyspiro/expert-robot/pull/116), [#118](https://github.com/Mannyspiro/expert-robot/pull/118), [#123](https://github.com/Mannyspiro/expert-robot/pull/123), [#135](https://github.com/Mannyspiro/expert-robot/pull/135) |
| P09 | Advanced research and source-grounded discovery | Preserve ambitious ideas while advancing small falsifiable, independently checked studies. | [#75](https://github.com/Mannyspiro/expert-robot/pull/75), [#80](https://github.com/Mannyspiro/expert-robot/pull/80), [#87](https://github.com/Mannyspiro/expert-robot/pull/87), [#90](https://github.com/Mannyspiro/expert-robot/pull/90), [#91](https://github.com/Mannyspiro/expert-robot/pull/91), [#92](https://github.com/Mannyspiro/expert-robot/pull/92), [#93](https://github.com/Mannyspiro/expert-robot/pull/93), [#97](https://github.com/Mannyspiro/expert-robot/pull/97), [#119](https://github.com/Mannyspiro/expert-robot/pull/119), [#131](https://github.com/Mannyspiro/expert-robot/pull/131), [#134](https://github.com/Mannyspiro/expert-robot/pull/134), [#141](https://github.com/Mannyspiro/expert-robot/pull/141), [#142](https://github.com/Mannyspiro/expert-robot/pull/142), [#143](https://github.com/Mannyspiro/expert-robot/pull/143), [#171](https://github.com/Mannyspiro/expert-robot/pull/171) |

Dependencies are explicit in the JSON. Context review, identity hardening and harmless engineering tests can proceed alongside service closure. A downstream gate that needs independent verification cannot be called complete from an upstream local test. PR links identify possible dependencies or overlap; they do not assign ownership or recommend bulk merging.

### P00 — Private OCI service and operational recovery

- **P00-1: Record deployed source and route inventory.** Capture exact commit/module hashes, interpreter/platform, service unit, granted peer UIDs/tools, socket owner/mode and dependency versions; distinguish private host access from a direct ChatGPT dot connection.
- **P00-2: Exercise real service acceptance.** On the intended OCI host, retain health, permitted/denied tool calls, peer-identity checks, socket replacement/stale-path checks and restart recovery; skipped local socket tests do not count.
- **P00-3: Prove non-destructive recovery.** Back up exact canonical artifact versions and state; restore to an isolated location and resolve pinned references; compare source/backup/restored bytes before any retention cleanup.
- **P00-4: Keep observability and capacity evidence.** Bound logs and payloads, preserve failed attempts, measure free disk/inodes/CPU/RAM, and exercise supervised graceful shutdown without touching unrelated runner data.

**Acceptance gates:**

- Exact deployed source and environment identify every accepted result.
- Unauthorized UIDs/tools and mutation requests fail before handlers run.
- Restart and isolated restore drills reproduce pinned artifacts.
- No public listener, unconfigured provider or historical CI run is silently treated as live production capability.

### P01 — Source-complete project context and retrieval

- **P01-1: Reconcile all 191 document records.** Retain each exact blob identity and content hash; review in deterministic bounded shards; map each material claim to code/tests/receipts, preserving indexed-versus-reviewed status.
- **P01-2: Evaluate retrieval against a fixed reference set.** Predeclare representative cross-project questions, correct source versions and byte locators; test namespace isolation, stale-version retrieval, corruption, missing sources and complete response budgets.
- **P01-3: Preserve full-context boundaries.** Reconcile the parent-held 41-record project chat/context set by source identity and coverage; report absent raw transcripts and duplicates. Do not call it every account chat or silently use private conversations as training data.
- **P01-4: Review useful Drive assets without running intake code.** Keep all in-scope metadata and known-folder items. Fetch only selected useful sources through approved access, verify actual bytes/MIME/rights and append lineage; filenames and claimed telemetry do not establish functionality.

**Acceptance gates:**

- Every captured repo document is individually recoverable by identity and review status.
- A fixed held-out retrieval evaluation resolves exact references without cross-namespace disclosure.
- Context coverage and missing-history boundaries remain explicit.
- Raw private conversation content is purpose-limited and not automatically training or shared-runner data.

### P02 — Identity, scopes and separation of authority

- **P02-1: Audit UID/tool grant matrix.** Treat a shared Linux runner UID as that UID, not a GitHub workflow identity. Default it to reviewed engineering/demo reads; keep private chat state and mutations outside its grants.
- **P02-2: Complete any remote OAuth/OIDC boundary separately.** If a remote connection is required, configure a real issuer, resource/audience, subject/tenant/role map and scope policy. Test provider-issued tokens, expiry, rotation, revocation and cross-tenant denial; do not invent credentials.
- **P02-3: Separate request intake from execution authority.** Bind any pending-only request to the authenticated principal and immutable inputs; verify replay/conflict behavior and ensure neither request acceptance nor model output authorizes dispatch/signing/promotion.

**Acceptance gates:**

- Negative tests prove reads cannot request, requests cannot execute, and workers cannot sign or promote.
- Real identity-provider evidence is required before claiming SSO or a remote dot connection.
- Credential and trust-root custody are independent from producer/model configuration.

### P03 — Real two-coder and independent-evaluator improvement loop

- **P03-1: Bind real provider adapters.** Pin coder A, coder B and evaluator identity/revision plus prompt/config/adapter hashes, resource ceilings and allowed tools; demonstrate actual calls separately from deterministic test doubles.
- **P03-2: Run one controlled improvement episode.** Choose one measured failure, freeze parent/baseline and development/held-out suites, produce two bounded proposals, preserve skeptical findings and independently measure correctness/regressions/cost/latency.
- **P03-3: Prove safe resume and rollback.** Persist invocation intent and exact results; reconcile ambiguous in-flight calls without automatic repeat; replay completed stages, reject identity conflicts and restore the parent when acceptance fails.

**Acceptance gates:**

- Provider declarations are not mistaken for authenticated provenance or independence.
- The evaluator cannot tune the same held-out outcomes used to select changes.
- A repeatable measured gain plus regression review is required before proposing adoption.
- No automatic code/skill/model adoption, merge, authority expansion or model-weight change occurs.

### P04 — Hermes orchestration and MCFC execution fabric

- **P04-1: Compose canonical worker runtime.** Reuse existing Hermes/outbox/MCFC/registry contracts; validate exact input/output ArtifactRefs and full execution-budget identity before dispatch.
- **P04-2: Enforce budgets outside the model.** Demonstrate OS/process CPU, memory, time, filesystem, network and concurrency enforcement; terminate process trees on cancellation/lease loss and retain bounded logs.
- **P04-3: Exercise failure and recovery.** Test crashes before/after checkpoint, duplicate delivery, stale acknowledgements, heartbeat loss, cancellation, quarantined malformed results and restore without duplicate provider side effects.
- **P04-4: Qualify each actual runner route.** Measure availability and capacity and run a harmless exact-source probe before a workload; preserve free-compute policy and record unavailable/cancelled/no-credit states without relabeling them as passes.

**Acceptance gates:**

- One trace binds task/event/attempt, exact source, input/output versions, worker, environment, limits, exit state and logs.
- A budget field or lease alone is not OS enforcement.
- Generic outbox claims cannot consume the dedicated Hermes task topic.
- Historical runner labels, quota notes and hosted CI do not establish current provider qualification.

### P05 — Independent CACE and formal evidence closure

- **P05-1: Reconcile producer/verifier contracts.** Compare canonical Merlin ArtifactRef and CACE request/receipt schemas, explicit claim scope, source commit, toolchain, policy hash and failure states across repositories.
- **P05-2: Establish independent trust and custody.** Use real verifier-issued transport credentials and an independently pinned signer/trust policy with revocation. Repository SSH access and matching hashes are not signer authentication.
- **P05-3: Verify exact-head evidence and negative paths.** Retain a real success and a structured failure; reject forged/stale/wrong-artifact/unsigned evidence. Formal work additionally checks pinned Lean/mathlib, root reachability, assumptions, axiom audit and canonical qualification drift.

**Acceptance gates:**

- CACE-originated receipts bind exact project/path/version/digest and real independent verifier identity.
- Compilation, artifact integrity, numerical success, formal statements and physical validity remain separate statuses.
- Absent/skipped/stale/failed evidence remains visible and cannot promote a claim.

### P06 — Native CAD, wiring and simulation round trip

- **P06-1: Separate reusable ideas from broken assets.** Preserve the Drive modeler as a proposal/forensic source. Its syntax errors and identity-matrix/zero-displacement/first-candidate placeholders block deployment until a repaired implementation passes independent tests.
- **P06-2: Establish native fixtures.** The supplied search found no FCStd/STEP/STL/FCMacro files; acquire or create a small reviewed native fixture. Retain the available torus OBJ as mesh data, not a native FreeCAD document or validated design.
- **P06-3: Complete geometry and wiring fidelity.** Pin FreeCAD/kernel and importer versions; preserve units, frames, instances, constraints and topology through import/export. Compare geometry and authoritative pin/net metadata, including missing/invalid input paths.
- **P06-4: Complete pinned simulation evidence.** Use explicit electrical values and ground, an exact netlist, bounded pinned ngspice execution and independent reference checks. Keep the current ideal-rational DC comparison as a limited model test, not evidence that native CAD/ngspice ran.
- **P06-5: Retain physical-release boundaries.** Record ERC/DRC, tolerances, current/thermal/fault/clearance/manufacturing assumptions and qualified review before any physical release; generated images, meshes and AABB checks do not certify hardware.

**Acceptance gates:**

- One versioned IR/geometry/netlist/input/output provenance chain survives a real native round trip.
- A repaired modeler cannot pass through constant/identity/first-candidate stub behavior.
- Native runtime/version and actual solver execution are evidenced separately from export generation.
- Simulation and CAD outputs never self-issue physical safety or fabrication approval.

### P07 — HUD, Forge, voice and Merlin Learning

- **P07-1: Wire the research HUD to real recorded state.** Show sources, equations, CAD/netlist results, jobs, failures and evidence with honest status; visualize recorded graphs/telemetry rather than fictional hidden cognition.
- **P07-2: Complete one learning vertical slice.** Use shared identity/registry/graph, server-owned assessments, source-reviewed lessons, learner privacy, accessibility, delayed retention and transfer measures; add faculty/reviewer lifecycle before broad course expansion.
- **P07-3: Keep Forge and voice capability-scoped.** Verify virtual repository history/diffs/rollback and approved merge gates; test actual chat/voice providers and cancellation separately from UI screenshots and generated audio placeholders.

**Acceptance gates:**

- Read-only UI actions cannot alter scientific or qualification semantics.
- Tenant isolation and assessment integrity have adversarial tests.
- Course/voice/Forge source and exact runtime behavior are tested before product-readiness claims.

### P08 — Model loading, context efficiency and measured optimization

- **P08-1: Establish real model/hardware baseline.** Pin model/adapter hashes, licenses and compatible runtime; measure quality, p50/p95 latency, memory, disk, load/switch cost, cancellations and failures on versioned tasks.
- **P08-2: Compare bounded alternatives.** Evaluate one memory/context strategy and one inference engine at a time; quantify local quantization, streaming/offload, KV/context compression, retrieval and CPU-kernel effects at matched quality.
- **P08-3: Test strategy switching rather than assume it helps.** Compare standalone A/B against fixed, random and context-conditioned routing on matched tasks/seeds; include overhead and regressions and keep Pareto alternatives.

**Acceptance gates:**

- Copied source or a smaller memory footprint is not installed capability or faster inference.
- Any accepted optimization beats the best baseline by a predeclared useful margin at matched quality.
- No paid compute, credential invention or authority expansion is implied by this plan.

### P09 — Advanced research and source-grounded discovery

- **P09-1: Reconcile formal and mathematical objects.** Preserve theorem statements/assumptions/dependency DAGs, successor-theorem tests, axiom audits and exact-coordinate invariants; distinguish frame consistency from geometric holonomy.
- **P09-2: Review Xenomaths and representation programs.** Use canonical typed object/view/map/invariant identities, explicit glyph semantics and partial domains; finite rewrite checks do not prove global confluence or establish novelty.
- **P09-3: Expand research sources and atlas with review.** Reuse public academic source stores, rights-aware passage locators, specialist scholarship and equation metadata. Resolve authored-entry/count conflicts before claiming a complete 001–100 atlas.
- **P09-4: Preserve cross-domain hypotheses without claiming discoveries.** Keep collective/SOM-X, fractal/lacunarity, photonics/materials, biology, time-crystal/spacetime and THTG/UFT tracks as separate scoped hypotheses with units, controls, uncertainty, counterexamples and independent replication.
- **P09-5: Preserve humanistic and teaching research.** Maintain cultural/historical logic lenses, source translation caveats, science/history/philosophy and educational outcomes; formal operator lemmas do not validate historical, medical or cultural interpretations.

**Acceptance gates:**

- Every selected study states a concrete question, competing explanations, observable prediction and falsifier.
- Literature provenance, model adequacy, numerical observations and formal proofs remain distinct.
- No speculative theory, quantum advantage, clinical effect or universal alien mathematics is promoted through documentation.

## Ideas and assets preserved

The JSON retains the historical catalog’s 13 project groups, 20 platform layers, 10 mathematical programs, integration map, archive snapshots and incomplete skill-manifest recovery. It also preserves all 30 deduplicated chat-origin idea statements from the reviewed master ledger. These remain linked ideas and historical statuses, not a new parallel implementation registry.

The idea portfolio includes research-to-engineering workflow; canonical provenance and recovery; multi-representation mathematics and coordinate invariants; XMG/glyph semantics and confluence; proof search and theorem dependency graphs; equation-atlas coverage; collective/SOM-X and fractal/lacunarity research; spacetime/time-crystal and THTG/UFT hypotheses; photonics, materials, biology and simulation; CAD/wiring/thermal/manufacturing; public-source academic research; cultural/historical logic lenses; local models and measured strategy switching; independent research council; mobile HUD, voice, Forge and adaptive learning. Research hypotheses remain hypotheses.

The useful Drive inventory keeps project-tagged Merlin/CACE/MCFC/Xenomaths/CAD/wiring sources and all known Merlin-folder assets, including code/bundle proposals, handoffs, UI references, theorem/data tables and meshes. It omits 171 unrelated titles from the supplied Drive listing. Originals are neither executed nor deleted.

The supplied native-file search returned zero FCStd/STEP/STL/FCMacro hits. Torus OBJ mesh records are present. This establishes an asset gap in the searched/captured scope, not global absence. The parent retrieved one torus OBJ read-only: 257,799 bytes, SHA-256 `233ddd6f8945daed900752b04fd8da263ee7bacda497e43ced6b1f4fe021c8ee`, 1,568 vertices, 3,136 faces and 4,704 edges, Euler characteristic 0, with every reported edge incident to two faces. Units remain undeclared. The reviewed intake report is `merlin-documentation-corpus/drive-torus-intake.json`; these are bounded byte/topology observations, not native solid validation, FreeCAD execution or physical qualification.

The reported Drive modeler contains syntax and placeholder behavior; preserve its design intentions separately and require repaired transformations, meaningful displacements, genuine candidate evaluation and regression tests before deployment.

## Private corpus and deployment boundary

The complete documentation corpus remains in the Expert Robot/private project context. Automatic approval review blocked copying the 191 private documents into CACE. The parent instead reports successful upload of a small runtime-only package with two synthetic context records. This coverage plan does not claim private chats or the full documentation corpus are on that server, and does not re-verify service deployment. Selected private retrieval requires its own explicit scope and custody controls.

## Review and completion rules

- Every one of the 191 documents has a source URL, Git blob SHA-1, content SHA-256, byte size, review state and queued current-code/evidence reconciliation. Path-derived topic tags are navigation only.
- Review deterministic source shards; never exceed 800 repository files in one context pull. Read selected documents fully before making semantic claims.
- Reuse the existing canonical registry, graph, outbox, idea catalogs and evidence stores. Resolve ancestry and duplicates before adding another subsystem.
- Preserve old reports, failures, rejected hypotheses, absent evidence and rollback references. A source citation, hash, mock, export, compiled theorem, runtime success and independent signed receipt are different kinds of evidence.
- Set an accountable owner only through a real assignment. All tasks and PR ownership in this plan remain unassigned.
- The plan grants no credential, signing, dispatch, merge, promotion, deletion, paid-compute or public-exposure authority. Existing user authorization and canonical policy govern each action.
- Finish a production track only after its exact-source tests, intended runtime round trip, independent review, security/privacy and recovery gates are recorded. Documentation coverage alone never closes those gates.
