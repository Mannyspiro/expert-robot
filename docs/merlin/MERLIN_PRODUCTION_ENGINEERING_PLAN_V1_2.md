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
- PR #112's dedicated Learning identity workflow run [42253622657](https://github.com/Mannyspiro/expert-robot/actions/runs/42253622657) was queued/in progress at last observation. Its result is pending.

### Runner and verification observations
- Avrea is preferred, but the latest related Avrea jobs were cancelled. No successful Avrea run is established here.
- OCI workflow exists in `morganaspim/Cace-app` at `.github/workflows/cace-batch-exact-pin-lean-preflight.yml`, targeting `[self-hosted, cace, oci, aarch64]` and pinned Lean 4.32.1/Mathlib. This proves workflow configuration only, not runner availability or qualification.
- No CACE production transport receipt is yet established. Local test doubles are not independent CACE verification.
- Do not assume old Avrea quota, machine capacity, cache persistence or provider health without a fresh run.

## Ranked next implementation steps

1. **Finish PR #112 hosted evidence.** Inspect the dedicated Learning identity job logs and artifact. Resolve any test failures before adding further identity behavior.
2. **Qualify a real OIDC provider adapter.** Select a maintained library after dependency inventory; configure trusted issuer, audience/client, JWKS discovery, permitted algorithms, token profiles, session/cookie or bearer policy, state/nonce, logout/revocation and tenant/role mapping. Keep routes fail-closed until real configuration is supplied. Never invent secrets or issuer values.
3. **Reconcile PR branches.** PR #108 Learning, PR #109 core registry and PR #110 persisted graph are sibling branches. Create a deliberate integration branch, reconcile `app.py` and tests, then rerun the combined suite. Do not merge sibling PRs independently if their application files conflict.
4. **Persist capability qualification receipts** and bind them to registry identity, provider/model revision, held-out test suite, environment, signer and digest.
5. **Unify canonical project/artifact/graph identity** and add provenance-aware graph mutations and snapshots.
6. **Complete Hermes event lifecycle** with idempotency, leases, acknowledgements, retry, dead-letter, cancellation and fault injection.
7. **Qualify Avrea and OCI** with real isolated jobs, pinned dependencies, resource budgets, complete logs and independently checked results.
8. **Complete CACE bridge** with signer identity, exact commit/artifact/toolchain binding and verifier-originated receipts.
9. **Connect research loop:** ideonomy, engineered prompts, literature sources, hypotheses, equation atlas, Lean, numerical solvers and finite counterexample search.
10. **Complete engineering virtual lab:** FreeCAD import/assemblies, engineering IR, units/constraints/materials, wiring/netlist generation, pinned ngspice and simulation receipts.
11. **Complete Learning product:** learner/faculty UI, assessments/rubrics, accessibility, privacy/export/deletion, cohort governance and LTI/QTI/Caliper/CASE/Edu-API integration.
12. **Governed self-improvement:** interaction learning with consent/purpose limits, aggregation/redaction, held-out evaluation, independent review, staged promotion and rollback.
13. **Production operations:** deployment, database migrations/backups/restore drills, observability, rate limits, incident response, disaster recovery and formal acceptance.

## Product and release constraints

- Merlin Learning must share identity, registry, graph, evidence and execution; do not fork a second agent platform.
- User interactions may improve hypotheses and aggregate system design; raw private conversation content is not automatically training data.
- No autonomous promotion of generated code, grading, permissions or production changes.
- Capability may grow; authority must not expand automatically.
- Phone, headphones, smart-TV and IoT remain backlog ideas, not current MVP dependencies.
- Draft PRs are not deployed software. Production is complete only after real identity, persisted state, independent verification, provider qualification, operational recovery and end-to-end acceptance are demonstrated.
