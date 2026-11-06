# Merlin Production Build Plan v1.1 — measured update

**Updated:** 2026-11-06  
**Status:** implementation in progress; not a production acceptance record.

## Operating protocol

For Merlin-related work, normalize likely spelling, transcription and speech-recognition errors when the intended term is strongly supported by project context. Preserve exact technical identifiers, repository names, branch names, hashes and quoted source text. When more than one interpretation remains plausible, state the ambiguity rather than silently rewriting it.

Use a combined engineering loop:

1. **Deductive:** derive contracts, invariants, permissions, failure states and acceptance tests from requirements and existing specifications.
2. **Inductive:** inspect source, logs, observed user workflows, measurements and failed runs; identify recurring requirements and revise the model.
3. **Analogy:** when blocked, restate the problem in a structurally equivalent domain while preserving constraints and invariants.
4. **Ideonomy:** enumerate materially distinct solution families, constraints, falsifiers and measurable outcomes; rank by expected value, dependency, feasibility, risk and verification cost.
5. **Implementation:** choose the smallest reversible change that closes the highest-ranked verified gap.
6. **Evidence:** retain exact source commit, tool versions, command, environment, logs, test results, artifact digest and reviewer receipt. A missing or cancelled run is not a pass.
7. **Learning:** turn outcomes into improvement hypotheses; require held-out evaluation and independent review before promotion. Never expand authority automatically.

## Observations and measurements

### Existing draft PRs

- [PR #108 — Merlin Learning course platform foundation](https://github.com/Mannyspiro/expert-robot/pull/108): open, draft, unmerged and undeployed. It contains tenant-scoped course storage, versioned manifests, review/publication lifecycle and adaptive recommendations. A real OIDC/SSO resolver, production migrations/backups, learner/faculty UI, assessments, privacy workflows, accessibility and interoperability remain incomplete.
- [PR #109 — canonical Merlin capability and graph contracts](https://github.com/Mannyspiro/expert-robot/pull/109): open, draft, unmerged and undeployed. Its core-contract workflow run **42248378299** checked out exact commit **30f7edfa33bcea1dc1ab8039d5ea536c0d3e8934**, compiled the contracts, and passed **33 tests in 2.41 seconds**. Logs and machine-readable results were uploaded as artifact **merlin-core-evidence-42248378299-1**, artifact ID **13517953699**, SHA-256 **741c7c65051ca72dac712e0797d46cdede880a1a2ed0f8f99e512823e5a8096c**. This is evidence for that exact commit only.
- On the same commit, the Avrea HUD workflow **42248378258**, general CI **42248378216**, and representation-spectrum workflow **42248378308** were cancelled. Attempts to retrieve cancelled-job logs returned BlobNotFound; therefore these runs have no usable test evidence and are not passes.

### New persisted-graph validation work

Branch: `feat/merlin-persisted-graph-validation-v01-20261106`  
Base: `30f7edfa33bcea1dc1ab8039d5ea536c0d3e8934`  
Current head: `77becd662853cf0d27dd4197a53c6884ebe20028`

Changes:
- Add a read-only GET `/api/graphs/validate` path that exports the configured canonical `MerlinKnowledgeGraph` snapshot and validates its node references and dependency cycles.
- Return the persisted snapshot digest separately from the validator's normalized graph digest.
- Fail closed with 503 when the canonical graph store is not configured or cannot be read.
- Preserve POST `/api/graphs/validate` as a caller-supplied preview and label its source `request_preview`; it is not canonical graph evidence.
- Wire the configured graph database into the HTTP handler only when the configured database file exists.
- Add integration tests for persisted graph validation, dependency-cycle detection, snapshot-digest change and the unconfigured fail-closed path.

**Verification state:** the branch changes and tests have been committed and the GitHub compare reports three commits ahead of the base, two files changed, 83 additions and 3 deletions. The new tests have **not yet been executed**. No new workflow run or CI pass is claimed for this branch.

## Updated ranked work

1. **Run focused validation on the new graph branch.** First compile and run the two added tests plus the existing capability/API tests; then the full relevant Merlin suite. Preserve logs and JSON results. Do not merge on the basis of the earlier 33-test run because it predates this branch.
2. **Identity and policy foundation.** Inspect the LMS identity resolver and app boundary; define issuer, audience, signature/key rotation, expiry, nonce/state, tenant, role, session revocation and service-identity contracts. Use a maintained OIDC/OAuth library and provider metadata/JWKS validation; do not implement JWT signature verification by hand. Keep all non-loopback and LMS routes fail-closed until a real issuer/client configuration and secrets are supplied and tested.
3. **Persisted capability qualification receipts.** Store immutable receipts binding capability ID/version, provider/model revision, environment, held-out test suite, result, timestamp, signer and artifact digest. A declaration or configuration flag must never count as qualification.
4. **Canonical registry and graph unification.** Add typed graph snapshot/validation receipts to the registry, preserve source provenance and exact digests, and make registry/graph/outbox use one stable project/artifact identity model.
5. **Hermes outbox lifecycle.** Verify idempotent publication, leases, heartbeats, cancellation, acknowledgement, retry and dead-letter behavior with fault-injection tests.
6. **Execution providers.** Qualify Avrea when the runner is available and has budget. Qualify OCI only from the user's `morganaspim` repository and only with a real run. Capture workspace isolation, pinned dependencies, resource usage, exit status and complete logs. Current evidence does not qualify either provider.
7. **CACE independent verification.** Bind signer identity, repository/commit, artifact digest, toolchain and verifier result; reject self-reported hashes and local test doubles as independent verification.
8. **Merlin research loop.** Connect ideonomy, engineered prompt contracts, source-aware literature intake, hypotheses, equation atlas, Lean, numerical experiments and finite counterexample search to registry/graph/evidence.
9. **Engineering virtual lab.** Complete real FreeCAD import/assembly, engineering IR, wiring/netlist generation and pinned ngspice execution; preserve simulation-versus-physical-test distinctions.
10. **Merlin Learning product completion.** Build learner/faculty experiences on the shared platform; finish assessment/rubric workflows, privacy/export/deletion, accessibility, institutional integration and faculty pilot.
11. **Controlled self-improvement and launch.** Held-out paired evaluations, independent assessment, staged release, rollback, backups/restore drills, monitoring, incident response and acceptance review.

## Resource and release constraints

- Avrea is preferred when available, but the latest Avrea workflow was cancelled and no direct Avrea runner action is exposed in the current tool session. Do not claim it was used.
- The OCI runner workflow has been located in `morganaspim/Cace-app`: `.github/workflows/cace-batch-exact-pin-lean-preflight.yml` targets `[self-hosted, cace, oci, aarch64]` with a 90-minute timeout and pinned Lean 4.32.1/Mathlib. This confirms a configured workflow target, not that a runner is currently online or that a run succeeded. No workflow-dispatch action is exposed in this session, so it has not been triggered or qualified.
- Do not introduce paid providers or claim new paid execution capacity. Do not merge or deploy draft PRs. Preserve the user's approval boundary for hosted Actions usage.
- Phone, headphones, smart-TV and general IoT remain future concepts only.
- Production is complete only after all critical paths have reproducible evidence, real identity and policy are configured, independent verification works, deployment/restore/monitoring are tested, and the acceptance gates are met.
