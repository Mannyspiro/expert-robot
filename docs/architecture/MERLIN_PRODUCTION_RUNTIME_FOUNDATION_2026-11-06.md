# Merlin production runtime foundation — 2026-11-06

## Objective

Establish one durable execution contract shared by Hermes orchestration, MCFC scheduling, Avrea workers, CACE verification, the research canvas, and future adapters. The model is not the system of record: durable state, authorization, idempotency, and evidence are deterministic application responsibilities.

## Implemented in this increment

`python/merlin/runtime_contracts.py` defines:

- `RunRecord`: immutable request/run identity, conversation and request IDs, idempotency key, capability/version, policy hash, state, creation time, and positive step/runtime/cost budgets.
- `RunEvent`: append-only ordered event with run identity, sequence, actor, timestamp, structured payload, previous hash, and SHA-256 event hash.
- `append_event` / `verify_event_chain`: canonical JSON hashing, sequence/run continuity, timezone-aware timestamps, and tamper detection.
- `ApprovalRecord`: approval bound to exact run, step, action digest, policy hash, approver, and decision timestamp.
- `authorize_side_effect`: fails closed unless the approval is granted and every bound field matches exactly.
- `check_idempotency`: exact request replay is recognized; reuse of the same key for a different request is rejected.

The module is storage/provider-neutral. It does not yet persist records to SQLite/Postgres or drive live workers. That integration is the next engineering stage; do not present this contract module as a deployed durable scheduler.

## Required event vocabulary

The initial allow-list includes run lifecycle events, step lifecycle events, tool request/completion, approval required/granted/denied, and artifact creation. Events must be appended by the trusted service boundary, not authored by an LLM. Large payloads should be stored as artifacts and referenced by digest.

## Target production flow

1. API authenticates the user, validates request shape, resolves tenant/session context, and records the request.
2. Capability registry resolves an explicitly qualified capability version and policy hash.
3. Orchestrator creates a run with correlation/request IDs, idempotency key, and hard budgets.
4. Planner emits a typed plan; deterministic validation checks schema, capability allow-list, resource budget, and action class.
5. MCFC acquires a bounded lease; Avrea executes in an isolated worker; all steps emit correlated events.
6. Tool outputs become immutable artifacts with source/tool/version/input/output digests.
7. CACE independently verifies eligible artifacts and returns a signed receipt; missing transport or invalid receipts fail closed.
8. A consequential side effect pauses at a durable approval boundary. Approval is bound to the exact action digest and policy version.
9. The run resumes, completes, fails, or is cancelled with terminal events and retained logs/results.
10. Read-only HUD and research views project canonical run, event, artifact, approval, and evidence records.

## Non-negotiable invariants

- One durable run ID and correlation ID across all subsystem handoffs.
- At-least-once delivery is assumed; side effects require idempotency or explicit reconciliation.
- The worker is disposable; durable state and artifacts survive worker loss.
- Retries, cancellation, deadlines, fan-out, token/cost budgets, and lease expiry are explicit.
- Human approval is a server-enforced state transition, never a prompt instruction.
- Approval binds exact action digest, policy hash, run, and step; any change invalidates it.
- CACE receipt binds exact artifact and tool/runtime provenance; a hash alone is not verification.
- Capability qualification is distinct from authorization; authority never expands as a side effect of learning.
- Private user data is partitioned from public partner/research datasets and excluded from public telemetry by default.
- Model-generated plans, source claims, and evaluations are untrusted until deterministic validation and evidence checks pass.

## Next ranked implementation steps

1. Persist `RunRecord`, events, approvals, idempotency keys, and artifacts in a transactional SQLite-backed registry with schema migrations and append-only event writes.
2. Add transactional outbox/inbox with idempotent acknowledgements and replay-safe Hermes dispatch.
3. Add MCFC lease acquisition/heartbeat/expiry, worker capacity limits, cancellation, and retry policy.
4. Add Avrea adapter that returns signed execution manifests and immutable artifact references; qualify OCI as a second runner using the same contract.
5. Connect CACE verifier transport and reject unverifiable or mismatched receipts.
6. Add failure-injection/recovery drills: kill worker, replay delivery, expire lease, revoke approval, corrupt artifact, and restart orchestrator.
7. Build read-only operational HUD projections: run timeline, agent assignments, queues, leases, resource budgets, approval waits, artifacts, CACE receipts, and errors.
8. Add evaluation datasets and held-out scoring for task completion, factual grounding, tool choice, cost, latency, and recovery. Do not learn from private content without a separate policy and user consent.
9. Only after the single-run path is reproducible, add bounded multi-agent collaboration, prompt engineering/dispatch, and self-optimization.

## CI contract

`.github/workflows/ci.yml` runs the opportunity, procurement, source-status, partner-qualification, partner-evidence, and runtime-contract suites. It captures verbose output, per-suite exit codes, and machine-readable result JSON; artifact upload uses `if: always()`. A green partner test job is not a substitute for the Avrea/C++/CACE end-to-end pipeline.


## CI verification — partner + runtime contracts

GitHub-hosted fallback job completed successfully on workflow run [#2752](https://github.com/Mannyspiro/expert-robot/actions/runs/42174071127), attempt 2.

- Partner/runtime test job: `success`.
- Six suites passed: 13 opportunity, 6 procurement-readiness, 5 source-status, 7 partner-qualification, 8 partner-evidence, and 9 runtime-contract tests — **48 tests total**.
- Every per-suite exit code is `0`; aggregate result JSON is `exit_code: 0`.
- The retained artifact includes verbose logs, exit-code file, and result JSON.
- Artifact ID: `13482995327`; artifact digest: `sha256:1409d394424f4d5d0694eb65fb60efb2a40683a97fcc50891191017f301daa8d`.
- The job tested the pull-request merge ref `c79b335a54df0a5f363e7e338792e786070f76dc`; the workflow run's PR head was `845a644bc6001f29356db21ddaad5565b8da61ec`.
- The separate `build-and-smoke` job remains cancelled because Avrea has no available credits. Therefore the fallback's 48 tests pass, but the complete Avrea/C++/CACE pipeline is not yet green.


## SQLite persistence adapter — implementation added

`python/merlin/sqlite_registry.py` now persists the runtime contracts in a transactional SQLite database:

- Versioned schema metadata.
- Immutable run identity, capability version, policy hash, budgets, and unique idempotency key.
- Append-only ordered event rows with hash-chain verification on reads and before appends.
- Approval records bound to exact run, step, action digest, and policy hash.
- Atomic idempotency replay: same key + same request digest returns the original run; same key + different digest is rejected.
- Approval decisions can transition only from pending, and only to approved or rejected.

Tests cover persistence across store reopen, exact replay, key conflict, event ordering and verification, unknown-run rejection, and one-time approval decisions. CI now includes `test_sqlite_registry.py`.

**Scope limitation:** this is a single-node SQLite persistence adapter. It is not yet a multi-process distributed queue, a lease manager, a transactional outbox, or a production deployment. Before multi-runner concurrency, add explicit outbox/inbox tables, lease ownership and expiry, worker heartbeats, and a tested migration path; then move to a shared transactional database if deployment topology requires it.

The next implementation priority is now the transactional outbox/inbox and Hermes dispatch lifecycle, followed by MCFC leases and worker recovery.


## SQLite registry CI verification — workflow #2759

The updated GitHub-hosted partner/runtime job passed after adding the SQLite persistence adapter:

- [Workflow run #2759](https://github.com/Mannyspiro/expert-robot/actions/runs/42174272836), attempt 2.
- Partner evidence and proposal pipeline job: `success`.
- Seven suites passed: 13 opportunity, 6 procurement readiness, 5 source status, 7 partner qualification, 8 partner evidence, 9 runtime contracts, and 7 SQLite registry tests — **55 tests total**.
- Every suite exit code is `0`; aggregate JSON `exit_code: 0`.
- Artifact ID: `13482805948`.
- Artifact digest: `sha256:992799b8fbe4e55de4173452880a6e626bd796e1f70b1bba95ea19a8ab035ede`.
- The ZIP was downloaded and inspected; it contains the verbose test log, seven-suite exit-code file, and result JSON. The result JSON reports tested PR merge ref `b4ded6716a0a167d39a6ed2748914c6b0279284b`.

The overall workflow remains cancelled because the separate Avrea `build-and-smoke` job did not execute. This is a passing result for the seven Python suites, not a complete Avrea/C++/CACE integration pass.
