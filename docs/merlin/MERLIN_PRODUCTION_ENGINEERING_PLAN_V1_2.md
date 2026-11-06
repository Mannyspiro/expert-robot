# Merlin Production Engineering Plan v1.2

**Updated:** 2026-11-06  
**Status:** active implementation; not a production acceptance record.

## Operating method

Every Merlin-related build cycle uses this loop:

1. **Normalize intent:** correct high-confidence spelling, speech-recognition and transcription errors using project context. Preserve technical identifiers, hashes and quoted source.
2. **Deduce contracts:** derive data models, invariants, authorization boundaries, failure states and acceptance criteria from stated requirements.
3. **Induce from evidence:** inspect actual code, logs, user workflows, provider results and failed attempts. Update the plan when observations contradict assumptions.
4. **Reframe by analogy:** if blocked, map the problem to a structurally equivalent domain while preserving constraints and invariants.
5. **Ideonomy:** enumerate distinct solution families, dependencies, falsifiers, expected value, feasibility, risk and verification cost.
6. **Implement reversibly:** choose the highest-ranked change that closes a verified gap without expanding authority.
7. **Measure and preserve:** record exact commit, command, environment, toolchain, exit status, logs, test results, artifact digest and independent reviewer evidence.
8. **Learn under governance:** treat observations as hypotheses; require held-out evaluation, independent review, rollback and user/policy approval before promotion.

## Architecture target

One shared Merlin platform, not separate product stacks:

- **Canonical registry:** projects, artifacts, versions, relationships, ownership and lifecycle.
- **Knowledge graph:** typed concepts, hypotheses, equations, proofs, evidence, engineering objects and learning objectives.
- **Evidence/provenance:** immutable receipts binding exact source, repository/commit, artifact digest, tool version, environment, result and signer.
- **Event outbox:** idempotent jobs, leases, heartbeats, acknowledgements, retry, cancellation and dead-letter lifecycle.
- **Capability registry:** only `configured`, `unavailable`, `unqualified`; configuration is not qualification.
- **Identity and policy:** verified principals, tenant isolation, least privilege, approval gates and revocation.
- **Execution fabric:** Hermes plans/routes, MCFC budgets/leases/scheduling, Avrea preferred runner, OCI alternate, CACE independent verification.
- **Research and engineering:** source intake, ideonomy, hypothesis ledger, math/Lean/numerical/counterexample loops, FreeCAD, engineering IR, wiring/netlists and ngspice.
- **Learning:** shared identities, graph, provenance and execution; curriculum, learner model, adaptive practice, faculty authoring and assessment.
- **HUD and Forge:** read-only canonical status/evidence views, jobs, graph exploration and controlled virtual-Git operations.

## Observed implementation and evidence

### Merlin core and persisted graph
- PR #109: [capability registry and graph contracts](https://github.com/Mannyspiro/expert-robot/pull/109), draft/unmerged/undeployed. Exact commit `30f7edfa33bcea1dc1ab8039d5ea536c0d3e8934` passed compile and 33 tests in 2.41 seconds in run [42248378299](https://github.com/Mannyspiro/expert-robot/actions/runs/42248378299).
- PR #110: [persisted canonical graph validation](https://github.com/Mannyspiro/expert-robot/pull/110), draft/unmerged/undeployed. Exact head `031958f237b085be74344e2bdf5d853e4c99ff62` passed compile and 35 tests in 3.11 seconds in run [42252451838](https://github.com/Mannyspiro/expert-robot/actions/runs/42252451838). Artifact [13521436513](https://github.com/Mannyspiro/expert-robot/actions/runs/42252451838/artifacts/13521436513), SHA-256 `a8a76669605beecfc3c12e3320c140b4b61ef07bb14fc9da3c80d2900d679092`.
- Persisted graph GET validates canonical snapshot, reports its digest, and fails closed when store is missing. Caller-provided POST remains preview-only.
- The separate HUD workflow run [42252451395](https://github.com/Mannyspiro/expert-robot/actions/runs/42252451395) remained in progress at last observation. General CI, Avrea and representation-spectrum workflows for that branch were cancelled and are not passes.

### Merlin Learning
- PR #108: [Learning foundation](https://github.com/Mannyspiro/expert-robot/pull/108), draft/unmerged/undeployed. Exact head `555afc087c0018807726c64e3f0b10b5ff952688` passed compile and 20 tests in 0.85 seconds in run [42247116487](https://github.com/Mannyspiro/expert-robot/actions/runs/42247116487). Artifact [13518152181](https://github.com/Mannyspiro/expert-robot/actions/runs/42247116487/artifacts/13518152181), SHA-256 `e38efc348ebea01e1f9f7f9cc0e4d5cc2ec4c8da9675d9bdfaa7d1cd27211294`.
- Existing foundation has tenant-scoped SQLite course catalog, immutable published versions, instructor/reviewer lifecycle, enrollment and adaptive recommendation.
- `make_handler` accepts a trusted `learning_identity_resolver`; missing resolver returns 503 for LMS routes. The standalone `serve()` previously did not expose an injection parameter.
- PR #112: [OIDC identity integration](https://github.com/Mannyspiro/expert-robot/pull/112), draft/unmerged/undeployed. It is correctly based on the Learning foundation branch. It adds a host-injected verifier contract, strict issuer/audience/expiry/not-before/subject/tenant/role mapping, optional token revocation, fail-closed behavior, and a `serve()` injection parameter.
- The identity adapter intentionally does not parse or cryptographically verify JWTs. Production requires a maintained OIDC/OAuth library to validate signatures, allowed algorithms, issuer metadata/JWKS, key rotation and token profile. Authorization-code state/nonce validation must happen in the OIDC client transaction.
- PR #111 was an initial identity attempt based on the core branch without the Learning module. Its hosted tests failed at collection with `ModuleNotFoundError: python.merlin.learning_platform`. This is a branch dependency/integration error, not a successful identity test. PR #112 corrects the base dependency. Keep PR #111 draft and do not merge it.
- PR #112's initial hosted runs at heads `a540de79167f02388e4e34df28cdbeb5f87b9f5d` and `b34ec75330bf846b0a43b263473200db393264fa` exposed two literal backslash-n syntax errors in the `serve()` edits; both compile workflows failed before tests and retained logs/results. Both formatting defects were corrected. Corrected code head `4c6d72d59792c62b56794713744f684b7d1c99ca` passed the dedicated Learning identity workflow [42254417304](https://github.com/Mannyspiro/expert-robot/actions/runs/42254417304): compile succeeded and **21 tests passed in 0.92 seconds**. After updating the plan document, the current PR head `efaff5b4d0b5aa8ddc6a317932924fa847e3c92a` was retested: identity run [42254587186](https://github.com/Mannyspiro/expert-robot/actions/runs/42254587186) passed compile and **21 tests in 0.80 seconds**, artifact [13522740297](https://github.com/Mannyspiro/expert-robot/actions/runs/42254587186/artifacts/13522740297), SHA-256 `e0f2f9fbe5021058aa1a07ec373d77449d0b33375b26656774ea9f134350897a`. The current head also passed Learning platform run [42254587187](https://github.com/Mannyspiro/expert-robot/actions/runs/42254587187): compile and **20 tests in 0.89 seconds**, artifact [13522066119](https://github.com/Mannyspiro/expert-robot/actions/runs/42254587187/artifacts/13522066119), SHA-256 `6ec4b8eb590238bc26266d31ab908082cca4ee7b674085b1593820d5b087f58e`. The earlier `4c6d` run artifacts are retained too. These suites are separate and should not be summed as unique tests. PR #111 remains a superseded draft and should not be merged.

### Runner and verification observations
- Avrea is preferred, but the latest related Avrea jobs were cancelled. No successful Avrea run is established here.
- OCI workflow exists in `morganaspim/Cace-app` at `.github/workflows/cace-batch-exact-pin-lean-preflight.yml`, targeting `[self-hosted, cace, oci, aarch64]` and pinned Lean 4.32.1/Mathlib. This proves workflow configuration only, not runner availability or qualification.
- No CACE production transport receipt is yet established. Local test doubles are not independent CACE verification.
- Do not assume old Avrea quota, machine capacity, cache persistence or provider health without a fresh run.

## Unified integration branch

- PR #113: [unified Learning, identity, capability and canonical graph](https://github.com/Mannyspiro/expert-robot/pull/113), draft/unmerged/undeployed.
- Exact tested code head: `6e7c754b4da9045caebf36f267919c39eee4b211`.
- Unified workflow [42255514469](https://github.com/Mannyspiro/expert-robot/actions/runs/42255514469): compile succeeded; **56 tests passed in 4.03 seconds**. Artifact [13523195538](https://github.com/Mannyspiro/expert-robot/actions/runs/42255514469/artifacts/13523195538), SHA-256 `1b1db57657d86d0ed70ea888daeae3749e8414a3a4111b8b34b1d694b4237e84`.
- Identity workflow [42255514208](https://github.com/Mannyspiro/expert-robot/actions/runs/42255514208): **21 tests passed in 0.89 seconds**. Artifact [13522666381](https://github.com/Mannyspiro/expert-robot/actions/runs/42255514208/artifacts/13522666381), SHA-256 `f16f2f0ee1b4db72affd62ff75ff8ec2f0b27c05775347992cd0860442383f4c`.
- Learning workflow [42255514264](https://github.com/Mannyspiro/expert-robot/actions/runs/42255514264): **20 tests passed in 0.91 seconds**. Artifact [13522416740](https://github.com/Mannyspiro/expert-robot/actions/runs/42255514264/artifacts/13522416740), SHA-256 `b0ddf36194f51e15498370b6d36a7b9a7a420d9e18cdf0d08535aa428c64d878`.
- These suites overlap by design; do not sum them as unique tests. The unified suite is the authoritative combined regression signal for the listed contracts.
- HUD focused workflow [42255514220](https://github.com/Mannyspiro/expert-robot/actions/runs/42255514220) was still running at last observation; do not claim it passed until its logs and result artifact are available.
- General CI and Avrea qualification were cancelled. Neither is a pass. No real identity provider or verifier is configured, so the resolver remains host-injected and the standalone server fails closed.

### Qualification evidence persistence added

The integration branch now extends `MerlinRegistry` with an append-only capability qualification receipt table.

- Receipt records bind capability ID/version, provider/model revision, held-out suite, environment digest, evidence artifact digest, result, signer and signed time.
- Evidence artifact bytes are verified against the content-addressed SHA-256 blob before receipt insertion.
- SQLite triggers reject updates and deletes; same-receipt replay is idempotent and reusing an ID with changed content is rejected.
- A newly stored receipt always returns `pending_independent_verification` and `qualified: false`. This is deliberate: storage of a runner's claim is not CACE verification and cannot promote a capability.
- CACE-originated verification receipts and a trusted verifier transport remain future work.

Updated unified evidence on exact code head `06ece19e01b115a8d10da7e919b91ba131296267`:
- Run [42256217705](https://github.com/Mannyspiro/expert-robot/actions/runs/42256217705): compile succeeded; **61 tests passed in 3.66 seconds**.
- Artifact [13523455717](https://github.com/Mannyspiro/expert-robot/actions/runs/42256217705/artifacts/13523455717), SHA-256 `e45c237705ff2dda29f15536063f4bef71ab870b728330a41a7be84f566919f5`.
- This replaces the earlier 56-test run as the latest combined regression signal for this branch.

### CACE adapter and outbox regression added

- The unified workflow now also compiles `cace_adapter.py` and `event_outbox.py`, and runs the existing CACE adapter and outbox suites.
- The CACE adapter contract tests exercise exact repository/commit/artifact/theorem binding, independent verifier identity, proof receipt checks, generic artifact verification, graph linkage, outbox events and fail-closed missing transport. They use injected test transports; they do **not** establish a live CACE service connection.
- The outbox tests cover idempotency, payload conflicts, lease/acknowledgement, expired-lease recovery, stale-token rejection, retry/quarantine and topic filtering.
- Latest combined evidence on exact code head `4875501ea93de14405f553a2b6b14f13a492800c`: run [42256655592](https://github.com/Mannyspiro/expert-robot/actions/runs/42256655592), compile succeeded; **73 tests passed in 4.12 seconds**. Artifact [13522158574](https://github.com/Mannyspiro/expert-robot/actions/runs/42256655592/artifacts/13522158574), SHA-256 `487f1984fd6014f207982103ae07e93ab7f2e7f4801d1752e149c757de72508d`.
- CACE repository observation: `morganaspim/Cace-app` describes itself as a research/development system and explicitly says production readiness is not established. Its `docs/STATUS.md` says the canonical v3.30 continuum-proof claim is not current-head qualified and the v3.36 candidate is intentionally unqualified pending exact-head qualification. The inspected repository documents a CLI/portable qualification path; a production HTTP verifier endpoint and authenticated transport contract have not yet been established in this integration. Therefore CACE remains unqualified as a live remote service.

### OIDC/JWKS verifier advanced and tested

- Added a production JWT verifier using pinned `PyJWT[crypto]==2.15.1` and `PyJWKClient`, with an explicit asymmetric algorithm allowlist, HTTPS-only issuer/JWKS URLs (loopback HTTP only for development), signature/issuer/audience/exp/iat/nbf validation, required subject and maximum token lifetime.
- Added environment-based construction through `MERLIN_OIDC_ISSUER`, `MERLIN_OIDC_AUDIENCE`, `MERLIN_OIDC_JWKS_URL` and optional policy variables. The standalone server remains fail-closed if required settings are absent or invalid.
- Added an append-only SQLite `jti` revocation store for single-instance use. Multi-instance deployment must inject a shared revocation checker.
- Configuration guide: `docs/merlin/MERLIN_OIDC_CONFIGURATION.md`.
- No real provider issuer, audience, JWKS URL, tenant claim or role claim is configured. No live provider token has been validated. This is a tested integration mechanism, not production SSO completion.
- Exact tested code head `8d6335acb491ad3b02f91da9dc3a2d69c5b69e39`: unified run [42257763371](https://github.com/Mannyspiro/expert-robot/actions/runs/42257763371) compiled the integrated modules and passed **82 tests in 4.69 seconds**. Artifact [13522923401](https://github.com/Mannyspiro/expert-robot/actions/runs/42257763371/artifacts/13522923401), SHA-256 `a407e86eb360be7dee37c2b3cb3601233872adcf1baaa7ce8bdc2a919dea3eab`.
- Identity-focused run [42257763347](https://github.com/Mannyspiro/expert-robot/actions/runs/42257763347) passed **30 tests in 1.13 seconds**. Artifact [13523781333](https://github.com/Mannyspiro/expert-robot/actions/runs/42257763347/artifacts/13523781333), SHA-256 `fdc35b86d36842450ada2c21481cea3f95539ab94a3f54e4f33d2e6b35f9808d`.
- These tests use generated RSA keys and a fake JWKS client to exercise PyJWT signature and claim validation; they do not contact a real identity provider. The combined 82-test run is the authoritative integration suite.

### Outbox worker API and Hermes integration advanced

- Added authenticated HTTP endpoints for per-worker claim, heartbeat, acknowledgement, retry/quarantine and status. Worker identity is bound to an independent high-entropy token from the trusted server environment; comparisons are constant-time and the worker ID cannot be changed independently of its token.
- Added durable metadata audit records for worker claim and lifecycle actions without storing bearer or lease tokens.
- Added six HTTP integration tests covering unauthenticated access, token/worker binding, claim-heartbeat-acknowledgement round trip, cross-worker lease rejection, retry/quarantine and fail-closed missing outbox.
- The first run [42268148088](https://github.com/Mannyspiro/expert-robot/actions/runs/42268148088) exposed six failures: Hermes imported the same outbox module under a second package namespace, causing a Python class-identity mismatch. The fix changed the import to package-relative form. This failed run is retained as engineering evidence.
- Exact passing head `89b19250ef99b2277694eb1dc0d48070a790aae8`: [run 42268417875](https://github.com/Mannyspiro/expert-robot/actions/runs/42268417875) compiled the integrated modules and passed **94 tests in 8.30 seconds**. Artifact [13528675991](https://github.com/Mannyspiro/expert-robot/actions/runs/42268417875/artifacts/13528675991), SHA-256 `a57d74ec67e89135fede3196e4ed98ff0e2e789abf3b1febc8548654d8560858`.
- Worker API guide: `docs/merlin/MERLIN_OUTBOX_WORKER_API.md`.
- The API is still loopback-hosted and uses a server-side credential map; no production secrets, HTTPS gateway, shared multi-host database or continuously running Hermes worker supervisor is configured.
- Outbox cancellation remains cooperative and there is no authenticated administrative cancellation endpoint. External processes must check their lease and stop themselves. Do not claim process-level cancellation until this is implemented and fault-tested.

## Ranked next implementation steps (updated from measured requirements)

1. **Run a real end-to-end Hermes task through a worker process.** Add a supervised worker executable with bounded concurrency, topic allowlists, deadlines, heartbeat, graceful shutdown, child-process cancellation and durable result receipts. Start with a deterministic no-shell task handler, then a bounded provider adapter.
2. **Make worker execution evidence complete.** Bind every attempt to event ID, exact source commit, artifact digest, command/adapter version, environment, resource limits, timestamps, exit status, stdout/stderr digests, output digest, retry/cancel state and worker identity.
3. **Connect Avrea and OCI as separately qualified runners.** Discover the actual runner APIs and credentials from the connected repositories; run harmless capability probes first. Never equate hosted GitHub Actions with Avrea/OCI qualification. Record unavailable/no-credit/cancelled states accurately.
4. **Complete independent CACE verification.** Establish the real verifier service contract and authenticated transport, verify signer identity and exact artifact/commit/toolchain binding, then require CACE-originated receipts. Injected test transports do not count as live qualification.
5. **Finish OIDC/SSO deployment.** Configure a real issuer, audience, JWKS URL, tenant/role mapping and token policy; validate a provider-issued token and test key rotation, revocation, tenant isolation and account lifecycle. No production provider is configured yet.
6. **Persist qualification and provider receipts in the canonical registry.** Bind provider/model revision, immutable test suite, environment, exact evidence digest, signer, reviewer and expiry; distinguish configured, unavailable, unqualified and qualified.
7. **Complete canonical project/artifact/graph integration.** Ensure every artifact, graph edge, prompt, experiment and execution result resolves to one canonical project identity and provenance chain; add migration/restore tests.
8. **Connect the research loop.** Ideonomy must enumerate candidate spaces and attach assumptions, mechanisms, observables, constraints, falsifiers and experiment plans; connect literature, equation atlas, Lean, numerical solvers and finite counterexample search without promoting unverified conjectures.
9. **Complete engineering virtual lab.** Real FreeCAD import/assemblies, engineering IR, units/constraints/materials, wiring/netlist generation, pinned ngspice and reproducible simulation receipts.
10. **Complete Merlin Learning product.** Learner/faculty UI, server-owned assessments/rubrics, accessibility, privacy/export/deletion, cohort governance and LTI/QTI/Caliper/CASE/Edu-API integration.
11. **Govern self-improvement.** User interaction data is purpose-limited and privacy-preserving; derived hypotheses need held-out evaluation, independent review, staged promotion and rollback. Capability may grow; authority must not automatically expand.
12. **Production operations and release acceptance.** Deployment, database migrations/backups/restore drills, observability, rate limits, incident response, disaster recovery, load tests, accessibility and documented acceptance criteria.

## Product and release constraints

- Merlin Learning must share identity, registry, graph, evidence and execution; do not fork a second agent platform.
- User interactions may improve hypotheses and aggregate system design; raw private conversation content is not automatically training data.
- No autonomous promotion of generated code, grading, permissions or production changes.
- Capability may grow; authority must not expand automatically.
- Phone, headphones, smart-TV and IoT remain backlog ideas, not current MVP dependencies.
- Draft PRs are not deployed software. Production is complete only after real identity, persisted state, independent verification, provider qualification, operational recovery and end-to-end acceptance are demonstrated.
