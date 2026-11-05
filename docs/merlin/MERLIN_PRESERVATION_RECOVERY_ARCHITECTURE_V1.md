# Merlin Preservation, Recovery, and Non-Destructive Change Architecture

Status: proposed P0-P3 architecture; implementation and runtime qualification are separate gates.
Baseline: `Mannyspiro/expert-robot` PR #77 head `694b34722a337fc2a7cc51321d6aedab8f16d5b2`.
Branch: `feat/merlin-preservation-recovery-p0-20261105`.

## 1. Non-negotiable invariant

Merlin MUST NOT destroy, overwrite, prune, garbage-collect, rename away, or make unreachable any user or project artifact unless all of the following hold:

1. The exact prior bytes and metadata have been captured in immutable, independently addressable storage.
2. The proposed change has a complete before/after manifest and an explicit reason.
3. A preservation check proves every pre-existing artifact is either retained, intentionally superseded with a recoverable successor, or explicitly approved for retirement.
4. The operation is compare-and-swap against the version observed by the planner; concurrent changes cause a conflict, never last-writer-wins.
5. A rollback/recovery path has been exercised or its limitation is explicitly recorded.
6. Required approval is present. Automated agents may create isolated candidates and recovery copies; they may not permanently purge or replace canonical work.

Default is DENY. Missing metadata, uncertain ownership, incomplete inventories, failed hashes, unavailable backup, or ambiguous intent means no destructive operation.

## 2. Existing foundation to reuse

Do not create a parallel artifact store or duplicate the canonical registry.

Existing components discovered at the baseline:
- `python/merlin/project_registry.py`: SHA-256 blob storage and project/logical-path mapping.
- `python/merlin/foundation_store.py`: foundation store used by archive intake.
- `python/merlin/archive_intake.py`: safe ZIP intake; stores original archive and member bytes as artifacts without extracting member paths onto the host.
- `python/merlin/event_outbox.py`: durable, idempotent events, leases, retries and acknowledgements.
- `python/merlin/cace_adapter.py`: sends exact registry-verified bytes to an injected independent verifier.
- `python/merlin/hypothesis_ledger.py` and `knowledge_graph.py`: research lifecycle and typed evidence relationships.
- Hermes worker and MCFC admission boundary: bounded task execution.

Important discovered limitation: `MerlinRegistry.put_artifact()` currently updates the `project_artifacts` row for an existing `(project_id, logical_path)` to a new digest. Although the blob itself is content-addressed, the logical-path pointer is mutable and there is no built-in version history/CAS guard in this method. This is a concrete overwrite hazard and must be addressed before enabling autonomous repair or recovery writes to canonical paths.

## 3. Target data model

Keep immutable blob bytes separate from mutable, versioned names:

- `artifact_blobs(digest, size, media_type, storage_location, created_at)`: write-once bytes; digest is identity.
- `artifact_versions(version_id, project_id, logical_path, digest, parent_version_id, created_at, actor, operation_id, state)`: append-only version history.
- `artifact_heads(project_id, logical_path, version_id, generation)`: current pointer updated only with compare-and-swap on expected generation/version.
- `change_operations(operation_id, actor, intent, base_commit, manifest_digest, policy_decision, approval_ref, status)`.
- `change_items(operation_id, path, old_version, new_version, change_kind, disposition, rationale)`.
- `recovery_points(recovery_id, scope, manifest_digest, storage_receipt, verified_at, retention_class)`.
- `tombstones(path, version_id, reason, actor, approval_ref, recoverable_until)`: hide/retire without erasing bytes.
- `restore_operations(restore_id, source_version, destination, expected_head, result_version, verifier_receipt)`.

Never update old artifact bytes or old version rows. A logical path may point to a newer version only after CAS; its prior pointer remains in history. Prefer a new path for generated candidates, e.g. `repairs/<operation-id>/...`, until promotion is approved.

## 4. Change transaction protocol

Every repair, generated file, dependency update, rename, migration, cleanup or merge uses this protocol:

1. **Inventory:** enumerate Git tracked/untracked/ignored state where available, registry artifacts, branches/tags, worktrees, databases, archive intakes, proof outputs, CAD and simulation assets.
2. **Snapshot:** capture immutable recovery point and canonical manifest (path, type, size, digest, source, commit, owner/lineage, retention).
3. **Plan:** produce a machine-readable diff with additions, modifications, deletions, renames, binary changes, schema migrations and generated outputs.
4. **Impact analysis:** identify imports, references, tests, workflow consumers, documentation links, Lean dependencies, CAD assembly references, netlist references, research graph edges and external artifact references.
5. **Preservation proof:** every old item receives one disposition: retained unchanged; superseded by a verified successor; renamed with redirect/alias; tombstoned but recoverable; or proposed retirement awaiting human approval.
6. **Isolated execution:** apply only in a disposable worktree/container or candidate namespace. Never run repair scripts against the only copy.
7. **Validation:** compare expected and actual manifests; run targeted and full tests; check that unrelated files and outputs remain unchanged; verify hashes and restore test.
8. **Independent verification:** CACE checks exact before/after manifests, artifact bytes, commit identity, preservation dispositions and recovery point. CACE must not trust caller-supplied hashes without reading/recomputing bytes.
9. **Promotion:** use CAS against the original commit/version. If the branch, artifact head, or source changes concurrently, abort and replan.
10. **Post-promotion:** retain predecessor, candidate, receipt, logs and rollback pointer. Monitor for regression.
11. **Retirement:** deletion means tombstone first. Physical purge is a separate, delayed, explicitly approved operation after retention and dependency checks.

No partial transaction may silently leave a mixed state. Failed stages preserve both old and candidate data and emit a durable event.

## 5. Recovery sources and priority

Search and reconcile, do not assume a single backup source:
1. Git object database: commits, trees, blobs, tags, refs, PR heads and closed/unmerged branches.
2. GitHub PR patches, review comments, workflow artifacts and release assets.
3. Existing Merlin content-addressed registry and foundation store.
4. Original ZIP archives ingested by `archive_intake.py`, including member manifests.
5. OCI/Avrea workspaces, runner artifacts and retained job outputs, when available.
6. Local worktrees, runner caches and explicitly configured backup snapshots.
7. User-provided archives and handoff bundles.

Recovery confidence labels:
- **Exact:** byte-for-byte digest match to a known prior artifact.
- **Reconstructed:** recreated from source/history, with provenance and differences disclosed.
- **Partial:** some bytes or metadata missing.
- **Unverified:** candidate only; never restore over canonical work.

Recovery always writes to a quarantine/recovery namespace first. Compare and validate before offering promotion. Never overwrite a current file just because an older version was requested; restore to a new path by default.

## 6. Deletion and overwrite audit

For every commit range and proposed merge:
- Enumerate net added/modified/deleted/renamed paths.
- Inspect per-commit changes where net comparison can hide delete-then-recreate history.
- Compare full Git trees and registry inventories at base and head.
- Identify missing tracked files, dangling references, removed tests, reduced proof coverage, lost workflow triggers and orphaned artifacts.
- Classify deletion as necessary, redundant, accidental, superseded, or unresolved; require evidence for the classification.
- Never infer that a file is unnecessary merely because it is unused, old, unreferenced, or not imported by Python.
- A deletion is "necessary" only when a documented replacement/migration exists, dependencies are understood, tests pass, preservation is verified, and an authorized reviewer accepts it.

## 7. Autonomous repair permissions

Observe: read-only inventory, alerts, diagnostics, recovery recommendations.
Repair: create recovery points, candidate files, isolated branches/worktrees, tests and draft PRs.
Operate: merge, deploy, migrate canonical data, alter branch protections, change credentials, delete refs, or physically purge artifacts. Requires explicit scoped approval.

Autonomous repair may automatically:
- retry transient failures within MCFC limits;
- create an isolated repair candidate;
- restore missing files into quarantine from exact verified history;
- run regression and integrity checks;
- open a draft PR with evidence.

It may not automatically:
- force-push, rewrite shared history, delete branches/tags, or remove workflow files;
- overwrite canonical logical paths without CAS and preservation receipt;
- purge blobs or archives;
- alter credentials, signer trust, approval policy, or its own authority;
- treat a passing test as proof that removed work was unnecessary.

## 8. P0-P3 delivery plan and acceptance criteria

### P0 — Stop destructive loss and qualify the baseline
- Freeze merges/deployments while auditing.
- Inventory branch, PR, tree, workflow, registry and archive state.
- Fix registry logical-path overwrite behavior with append-only versions and CAS.
- Add pre-change snapshot and complete before/after manifests.
- Add no-delete/no-overwrite default policy and fail-closed tests.
- Ensure PR CI runs on the actual feature branch and exact head.
Acceptance: a concurrent write conflicts; a failed repair leaves original bytes intact; every changed path has a disposition; restore test verifies exact digest.

### P1 — Recovery engine and receipts
- Implement recovery-source adapters for Git, registry/foundation store and ZIP intake first.
- Restore to quarantine, compare manifests, then open recovery PR.
- Add authenticated repair/recovery receipts binding actor, repository, commit, path, old/new digests, operation, verifier and approval.
- CACE independently re-hashes exact bytes and validates manifest coverage.
Acceptance: delete a fixture in a disposable repo, recover exact bytes from Git/archive/store, verify digest and provenance, and prove canonical target was not overwritten.

### P2 — Proactive repair and lifecycle
- Integrate detector → diagnosis → isolated repair → regression → CACE → draft PR.
- Persist repair attempts and failed hypotheses in canonical registry/ledger.
- Add rollback pointer, post-repair monitoring and recurrence detection.
- Test crash/restart, duplicate events, expired leases, concurrent updates and partial failures.
Acceptance: a seeded non-production failure is repaired reproducibly; regression is caught; rollback restores prior state; no physical deletion occurs.

### P3 — Full project coverage and operations
- Add OCI/Avrea artifact and runner recovery adapters where retention permits.
- Include Lean proof sources/build manifests, CAD native files/assemblies, ngspice netlists/results, datasets, model checkpoints and research notes.
- Add retention tiers, encrypted off-runner backups, restore drills and disaster-recovery objectives.
- Expose recovery status and lineage in the read-only HUD.
Acceptance: documented restore drills for source, database, research artifact, proof bundle and engineering project; every result has independent evidence.

## 9. Required tests

- Existing logical path update cannot silently replace its prior version.
- CAS rejects stale generation and concurrent writer.
- Missing snapshot or failed hash blocks mutation.
- Deleted tracked file is restored to quarantine from Git blob.
- ZIP intake restores original archive/member with exact digest.
- Unknown/untracked file is preserved rather than pruned.
- Rename preserves lineage and old path tombstone.
- Failed repair and worker crash preserve original and candidate.
- Rollback restores prior version pointer without deleting newer evidence.
- CACE rejects incomplete manifests, mismatched bytes, self-verification and unsigned/untrusted receipts.
- Garbage collection cannot remove referenced blobs or artifacts under retention.
- CI path filters cannot silently skip required preservation tests.

## 10. Current baseline findings and limits

The current PR #77 is open and draft. The branch head is `694b34722a337fc2a7cc51321d6aedab8f16d5b2`; its base is `aa41db4b1ca3f3707bb50e830be036b9c003acda`. The branch compare reports 218 commits ahead, 0 behind, and the net file comparison returned added/modified paths but no deleted paths. This establishes **no net deletions in that base-to-head comparison**, not that no intermediate commit deleted and recreated a path, and not that historical deletions elsewhere in the repository were necessary.

The current `.github/workflows/ci.yml` push branch list includes `main` and `feat/merlin-lean-proof-optimization-atlas-20261104`, but not `feat/merlin-provenance-outbox-20261104`. Pull-request events are configured separately. Add branch coverage or prefer PR-triggered exact-head checks; do not claim push CI coverage for the integration branch until verified.

The latest inspected PR-head commit had no combined status entries and no workflow runs returned by the connector. This is an absence of returned run evidence, not proof that no run exists anywhere.

No deletion is declared necessary by this audit. No historical deletion has been individually certified. A full per-commit and cross-repository deletion audit remains required.

## 11. Governing rule

Preserve first. Change in isolation. Verify independently. Promote with compare-and-swap. Retain every predecessor. Recover before reconstructing. Purge only with explicit authorization.

Capability grows; authority never expands.
