# Merlin production: bounded decomposition and translation plan (2026-11-21)

Parent checkpoint: `docs/evidence/merlin-release-gate-checkpoint-20261121.md`.
This is an append-only engineering proposal, **not** a declaration of release readiness.

## Observable goal
A clean machine extracts the Merlin ZIP, starts a loopback-only server, opens `/studio`, answers a task using an independently supplied local model offline, records a content-addressed evidence artifact, restarts, and reads back the same conversation and evidence. When online, separately authorized public browsing is available. Failed recovery must stop rather than replay a user's request.

## Decomposition: minimal executable contracts
| Workstream | Smallest observable contract | Negative control | Prerequisite |
| --- | --- | --- | --- |
| Packaging | zip member manifest hashes match extracted files | altered member fails | Python >=3.10 |
| Bootstrap | one command starts localhost health route | no model reports not-ready, not success | packaging |
| Studio | browser loads static shell and persisted conversation | corrupted DB refuses unsafe migration | bootstrap |
| Model | a real model produces one bounded response | missing model is explicit unavailable | Studio |
| Tools | public URL fetch produces source+content digest | private IP/redirect is denied | browser service |
| Recovery | restart restores same artifact references | interrupted lease blocks new repair | persistence |
| Evidence | unique receipt per gate, digest verified | reuse, tamper, path escape fail | release checker |
| Release | independent review reconciles all gates | unknown/failed gate blocks promotion | all above |

## Analogue mapping
1. **CI failure as a diagnostic decision tree (exact for status classification, not exact for root cause):** runner did not start / checkout failed / compile failed / tests failed / package failed. Each branch needs a job step and a captured log. A failed run alone cannot distinguish them. Translation-back: reproduce the failing stage on the same commit and runner class.
2. **Release evidence as a chain of custody (partial analogue):** receipt path -> bytes -> SHA256 -> source commit -> task-specific checker. Byte integrity is exact within SHA256 assumptions; scientific truth and independent execution are not implied. Translation-back: validate one real native acceptance artifact with an independent checker.
3. **Offline restart as a state machine (exact for declared state transitions):** stopped -> starting -> ready -> serving -> stopping; interrupted or unverified recovery -> blocked. Translation-back: kill process during a persisted run and verify the post-restart ledger without replay.
4. **Agent tools as capability tokens (partial analogue):** one authorized operation with bounded scope, time and output; no permission inheritance across tasks. Translation-back: prove negative network and filesystem controls under the real runtime.

## Ranked execution and stop conditions
1. Resolve failing GitHub Actions runs with actual step-level evidence; local pass vs CI failure is unresolved. Do not weaken controls.
2. Reconcile retained browser socket/lease and run real Unix peer-credential tests on the intended host.
3. Validate full Studio Python 3.10+ tests and archive inspection against the exact packaged bytes.
4. Bind a user-provided local model and verify a single end-to-end offline task, evidence readback, restart, and rollback.
5. Verify online public research and a separately checked scientific result.
6. Review and promote only the tested source with rollback and deployment receipts.

## Scientific lens disposition
- Simplex: deferred for runtime scheduling; irrelevant to Boolean authorization.
- n-ality: applied to independent dimensions (source, host, provider, state, model, evidence).
- Continuum: deferred until latency/throughput measurements exist; no invented bounds.
- Fuzzy: applicable to research relevance ranking, not release authorization or integrity.
- Induction: CI failures are observations, not proof of a specific defect.
- Deduction: missing mandatory gate evidence entails not-ready under the release policy.
- Abduction: runner availability, environment, source, and test defect remain competing hypotheses.

## Explicit nonclaims
No production merge, deployment, real local-model inference, native socket qualification, or complete standalone ZIP acceptance is established by this plan.
