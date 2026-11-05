# Merlin system test and evidence map

Status: canonical engineering context for Merlin agents, Hermes dispatch, repair workers, CACE review, Avrea jobs and the read-only HUD.
Version: 1.1
Policy: consult this file and the subsystem's current tests before proposing, dispatching, modifying or declaring a system verified. This file is a map, not a substitute for execution evidence.

## Global execution rules

- Discover the repository, branch, commit SHA, working tree, toolchain and relevant test commands before a run.
- Bind every result to exact repository, commit, artifact digest, tool/version, command, environment, start/end time and exit status.
- Distinguish unit, integration, end-to-end, live-provider and independent-verification evidence. A unit test never proves a live provider path.
- Never infer success from a queued job, accepted dispatch, empty job list, green unrelated workflow, or caller-supplied hash.
- Preserve logs, stdout/stderr, exit code, generated artifacts and environment metadata as immutable evidence artifacts.
- Do not merge, deploy, promote, overwrite canonical paths, delete refs or purge recovery material without the applicable explicit approval.
- On missing dependency, timeout, worker crash, lease expiry, hash mismatch or inconclusive verifier response: stop, preserve evidence, mark inconclusive and leave canonical state unchanged.
- All recovery restores land in unique quarantine paths. Promotion is a separate approved CAS operation.
- Capability grows; authority never expands.

## Subsystem test matrix

| Subsystem | Local/CI contract tests | Integration / live evidence required |
|---|---|---|
| Project registry | `tests/test_project_registry.py`; `python3 -m unittest discover -s tests -p "test_project_registry.py" -v` | SQLite migration from representative legacy DB copies; transactional rollback after injected history-insert failure; idempotent retry; missing/corrupt blob fail-closed; direct SQL bypass; concurrent CAS writers; exact blob rehash |
| FoundationStore | `tests/test_foundation_store.py`, `tests/test_foundation_store_cas.py` | Graph lineage and registry CAS receipt bound to exact commit |
| Archive intake | `tests/test_archive_intake.py` | Original ZIP retained; member inventory and bytes rehashed; archive/member limits and duplicate/unsafe paths exercised |
| Change manifests | `tests/test_preservation_recovery.py` | `GitRecoveryAdapter.audit_history(base, head)` audits each first-parent commit with full tracked-tree manifests and rename/copy-aware change records; separately inventory untracked/ignored files; reviewer-approved retirement only |
| Recovery adapters | `tests/test_preservation_recovery.py` | Git pinned commit/path, ZIP archive/member, registry blob exact-byte restore; verify source and destination digests; restore to quarantine; repeat restore and compare |
| Hermes outbox | Existing Hermes/outbox tests and `tests/test_repair_supervisor.py` | Real event publish/ack cycle, idempotency key, duplicate delivery, crash between claim and ack, retry and dead-letter behavior |
| Repair supervisor | `tests/test_repair_supervisor.py` | `tests/test_repair_supervisor.py` covers injected worker crash/retry, lease expiry after enqueue, duplicate failure event idempotency and rejected-candidate rollback boundary; a real isolated Avrea worker run remains separately required |
| MCFC leases | `tests/test_workload_leases.py`, `tests/test_workload_scheduler.py` | Real lease issuance/renewal/expiry/revocation, resource budget enforcement, no dispatch after expiry |
| Avrea adapter | `tests/test_avrea_adapter.py` | Live accepted dispatch receipt; pinned worker image/tool versions; bounded resources; retained job output; worker exit status; exact result bundle; crash/timeout recovery |
| CACE adapter | `tests/test_cace_adapter.py` | Independent verifier invocation on exact artifact bytes, commit, tool identity and manifest; signed receipt; reject/inconclusive cases; receipt signature and artifact rehash |
| HUD projector | Existing read-only HUD/outbox projection tests | Read-only `executions`, `recoveries` and CACE `verification` projections bind Avrea job IDs, runner IDs, event IDs, CACE verifier/commit/artifact/receipt refs and quarantine paths; stale/duplicate/out-of-order events; no control actions exposed |
| Git provenance | Git adapter tests and commit/PR receipt tests | Full pinned commit/tree; branch/tag/PR refs; `audit_history` first-parent per-commit rename/copy/delete records and tree digests; untracked and ignored files inventoried separately |
| Lean/proof observatory | Existing Lean receipt, theorem DAG and proof observatory suites in CI | Exact Lean/mathlib toolchain, source commit, assumptions and axiom audit; reproducible proof result |
| Engineering IR / CAD | `test_engineering_ir.py`, project store, CAD assembly, coordinate frames, connectivity, routing, qualification and export tests listed in CI | FreeCAD import/export round trip; engineering-IR hash; netlist generation; ngspice exact version, input deck, logs and reproducible output |
| Equation atlas / simulation | equation-atlas dimensional/symbolic checks and `test_merlin_simulation_engine.py`, composed models, signal/stochastic/biological complexity suites | Reproducible input/output artifacts, units, solver/tool version, seeds and numerical tolerances |
| Quantum/public API research | API contract tests and bounded provider adapter tests before any live call | Provider endpoint and terms verified, request/response retained, no credential leakage, simulator-vs-hardware evidence distinguished; no unsupported claim of hardware execution |

## Mandatory test sequence before an autonomous change

1. Read this matrix and the subsystem's current tests and contracts.
2. Identify all touched modules, consumers, workflows and data formats from imports, references and repository manifests.
3. Run syntax/static checks and narrow unit tests first.
4. Run the relevant subsystem test suites.
5. Run cross-subsystem integration tests for every changed boundary.
6. Run exact-head CI and inspect job-level logs; preserve failing output.
7. For provider integrations, perform a bounded isolated live run only when credentials, approval, lease and resource caps are actually available.
8. Ask CACE to independently rehash and verify the exact evidence bundle.
9. Publish the receipt and lifecycle state to the read-only HUD.
10. Keep the PR draft/unmerged until evidence is complete and a human approves promotion.

## Recovery-specific acceptance criteria

- Git: pinned full commit SHA; enumerate every tree entry; compare every commit in the audit range; report additions/modifications/deletions/renames/mode changes; restore a deleted file from its pinned source commit and verify exact SHA-256.
- ZIP: preserve original archive bytes; identify exact member unambiguously; reject traversal and duplicate member names; hash member bytes before and after registry write.
- Registry: verify content-addressed blob bytes and metadata; missing or corrupt blobs block migration/recovery; old versions remain readable.
- Restore: unique quarantine destination; no canonical head change; exact bytes verified independently; repeatable restore receipt.
- Repair: event identity, lease, approval, base commit, worker/tool versions and candidate digest bound together; crash/expiry/duplicate delivery must not cause a second canonical mutation.
- Rollback: rollback is a new versioned CAS operation, never mutation/deletion of prior history.

## Current known limitations to carry forward

- PR #82 remains draft and unmerged. GitHub Actions runs #42101528061 and #42102299010 both ended `failure` with zero job records and zero check runs; there are no job logs to inspect. The workflow's primary job requests `avrea-ubuntu-latest-8-vcpu`. The available GitHub connection cannot read the repository runner-registration/permissions endpoints, so the exact reason for the no-job failure is not yet established. Do not label CI as a test failure or a pass.
- Avrea dispatch/collection still use injected transport interfaces. No live provider dispatch, runner identity, worker exit status or retained output bundle has been evidenced in this session.
- CACE adapter checks receipt fields and a canonical `receipt_sha256` content hash. That hash is not a cryptographic signature and does not authenticate the verifier identity. A production signed-receipt profile still needs a pinned verifier key/identity and signature verification. No live independent CACE invocation has been evidenced.
- The Git adapter inventories tracked tree entries. Untracked/ignored files require a separate filesystem inventory with explicit scope and permissions.
- A local/CI test does not prove the user's OCI runner, Avrea worker, Hermes process or HUD deployment is connected.
- The HUD now projects Avrea execution records, CACE verification identity/subject/receipt references and recovery quarantine state from source-bound telemetry. It remains a read-only in-memory projection; a deployed persistent HUD feed is not yet proven.
- The HUD is read-only; it must never imply that telemetry grants repair or promotion authority.
