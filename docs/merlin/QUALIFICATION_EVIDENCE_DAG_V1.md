# Merlin qualification evidence DAG v1

**Status:** design contract for review; not a runtime implementation or qualification receipt.

## Purpose

Provide one deterministic, read-only dependency view over Merlin's existing source, artifact, execution, CACE, trust, and formal evidence. The graph is a projection, not a new registry or source of truth.

Canonical records remain authoritative:
- `MerlinRegistry` project/artifact rows, append-only artifact versions, and immutable producer provenance;
- existing research/RSI event and Hermes outbox lineage;
- exact Git commit and GitHub Actions run/attempt/artifact records;
- CACE signed ArtifactRef attestation and separate verification receipts;
- independently administered trust-root records;
- protected OCI execution and distinct protected orchestrator receipts;
- exact Lean source, Lean toolchain, Mathlib revision, and kernel compilation receipts.

A node may be projected only from a canonical record that can be independently retrieved and checked. A handoff document, UI status, self-reported SHA, or model-generated assertion is not evidence.

## Node identity

Each node has:
- `node_type`: source_commit, artifact_version, workflow_run, cace_attestation, trust_root, verification_receipt, oci_execution, protected_orchestrator, or lean_compile;
- `identity`: the complete type-specific immutable identity;
- `record_sha256`: digest of the exact canonical evidence record;
- `evidence_class`: the class supplied by its verifier, never inferred from graph connectivity;
- `status`: qualified, unqualified, stale, revoked, or blocked.

`node_id` is `sha256:` plus SHA-256 of canonical JSON containing `node_type` and `identity`. Identity fields are not abbreviated. Examples:
- source: repository + full 40-character commit;
- artifact: project + logical path + version + digest + size;
- workflow: repository + workflow ID + run ID + attempt + exact head SHA + conclusion + artifact digest;
- CACE: signed statement digest + verifier ID + key ID + purpose + complete ArtifactRef binding;
- trust: independent authority ID + immutable trust-root version + root digest;
- Lean: target module + source digest + Lean version + Mathlib revision + compile result.

Two different versions of the same path are distinct nodes even if their bytes/digest are identical.

## Edge semantics

An edge is stored from a **dependent** node to a **prerequisite** node. The relation names the dependency:
- `derived_from`: artifact or result depends on its source commit or input artifact;
- `built_by`: artifact depends on the exact successful workflow run that produced it;
- `attests`: CACE attestation depends on the exact ArtifactRef and EvidenceBundle;
- `verifies`: independent verification receipt depends on the attestation, artifact bytes, and trust root;
- `executes`: OCI execution depends on the exact task/input artifact references and runner profile;
- `qualifies`: qualification depends on the exact execution, orchestrator receipt, and required verifier evidence.

Edges are immutable within an issued snapshot. Missing prerequisites are explicit blocked conditions, not omitted assumptions.

## Deterministic snapshot rules

1. Canonicalize each node and edge using UTF-8 JSON with sorted object keys, fixed separators, no NaN/Infinity, and exact string/number types.
2. Sort nodes by `node_id`; sort edges by dependent ID, prerequisite ID, then relation.
3. Reject duplicate node IDs, duplicate edges, unknown endpoints, self-edges, malformed identities, and cycles.
4. Compute `snapshot_sha256` over the canonical snapshot excluding the `snapshot_sha256` field itself.
5. Preserve source-record digests and retrieval metadata; the graph digest does not replace or sign the underlying receipts.

## Status and invalidation

A graph cannot create qualification. A node is qualified only when its own authoritative receipt says so and every required prerequisite is qualified. Missing, incomplete, cancelled, stale, or non-exact-head evidence yields blocked/unqualified status.

When an upstream identity changes, traverse reverse dependency edges (from prerequisite to dependents) and invalidate only reachable downstream nodes:
- source commit change invalidates dependent artifacts, runs, attestations, and qualifications;
- a newer artifact version does not rewrite a historical version's identity or currentness;
- reverting to old bytes creates a new artifact-version node and new downstream lineage;
- trust-root revocation invalidates dependent verification and qualification nodes, but not unrelated numerical experiments or independent engineering evidence;
- a cancelled or incomplete run cannot satisfy a `built_by` or `executes` prerequisite.

Status precedence for a dependent node is `revoked` > `stale` > `blocked` > `unqualified`; `qualified` is possible only when the authoritative node receipt and all required prerequisites qualify. A node with no direct qualifying receipt remains unqualified even if all prerequisites qualify.

## Authority boundary

The DAG is read-only. Graph edges, node counts, connectedness, or a green HUD state never grant capabilities, signing rights, proof validity, deployment authority, or promotion authority. CACE artifact-integrity attestation, independent trust verification, Lean kernel compilation, OCI execution, protected orchestrator qualification, and promotion approval remain distinct evidence types and gates.

## Acceptance tests for implementation

- deterministic digest under input permutation;
- reject duplicate node IDs/edges, cycles, self-edges, unknown endpoints, malformed digests and non-finite numbers;
- selective transitive invalidation on source/artifact/trust changes;
- historical version preservation and A → B → A reversion lineage;
- revoked trust invalidates only dependent receipts;
- cancelled/incomplete/stale workflow runs cannot satisfy required edges;
- concurrent append preserves acyclicity and immutable snapshot history;
- API/HUD exposes provenance and qualified/unqualified/stale/revoked/blocked states;
- independent implementation reproduces the same canonical snapshot digest.

## Existing work to integrate

- Merlin PR #46: exact-source qualification binding.
- Merlin PR #130: authenticated Hermes failure and RSI candidate lineage.
- Merlin PR #144: append-only ArtifactRef version lineage and producer provenance.
- Merlin PR #147: canonical failure-class registry links to external CACE signer-custody regressions.
- CACE PR #100: separate signer authority and protected orchestrator evidence.
- CACE PR #102/#103 and issue #104: ArtifactRef attestation, signer custody, and independently administered trust-root requirement.

Do not build a second artifact registry, failure registry, or event ledger. Implement the DAG as a verified projection over those canonical systems.


## Initial runtime implementation (2026-11-14)

The first pure-Python runtime projection is implemented in `python/merlin/qualification_evidence_dag.py` with focused tests in `tests/test_qualification_evidence_dag.py`.

Implemented:
- Canonical UTF-8 JSON encoding with sorted keys, compact separators, and rejection of non-finite/unsupported values.
- Type-specific immutable node identities and SHA-256 node IDs.
- Exact ArtifactRef validation for CACE attestation, verification receipt, and OCI task/input references.
- Exact node/edge envelope validation, duplicate and unknown endpoint rejection, self-edge rejection, and cycle detection.
- Deterministic node/edge ordering and snapshot SHA-256.
- Prerequisite-first topological ordering.
- Reverse-edge transitive invalidation that affects only downstream dependents.
- Status propagation with `revoked > stale > blocked > unqualified`; a node cannot become qualified merely because its prerequisites are qualified.

Still not implemented:
- Trusted retrieval/verification adapters for GitHub, MerlinRegistry, CACE, trust service, OCI and Lean records. The module deliberately accepts only already verified projection records and does not fetch or authenticate them.
- Persistent immutable snapshot history, concurrent append coordination, API/HUD integration, or a background invalidation worker.
- Independent second implementation and property-based/fuzz qualification.
- An explicit required-prerequisite policy per node type. Missing required evidence must be represented by a blocked status from the authoritative adapter; the graph must never guess omitted edges.

The module is a read-only projection. It does not sign, verify signatures, execute code, compile Lean, grant capability, or authorize deployment/promotion. CI on the exact runtime PR head is required before treating the implementation as validated.


### Exact producer and execution binding
The runtime now rejects CACE attestation nodes unless their identity includes:
- the complete schema-validated `ArtifactRef`;
- full source repository and 40-character source commit;
- producer `artifact_id`, `artifact_kind`, and `artifact_schema`;
- signed statement digest, verifier identity, key ID, and attestation purpose.

Protected orchestrator node identities also require the exact execution receipt digest, not merely an execution label. OCI execution identities require schema-validated task and input ArtifactRefs. This makes the graph identity reflect the evidence lineage contract rather than an opaque status string.


## Persistent snapshot history implementation (2026-11-14)

The next increment adds `SnapshotHistory` in the same module. It stores canonical snapshot JSON and its digest in an append-only table inside the existing `MerlinRegistry` SQLite database; it refuses to initialize against a missing or unrelated database.

- `BEGIN IMMEDIATE` serializes concurrent appenders.
- An exact snapshot replay is idempotent and returns the original sequence.
- Digest collisions or same-digest/different-byte substitutions fail closed.
- Update/delete triggers make snapshot rows append-only.
- Reads re-run snapshot validation, canonicalization, and digest verification.
- History listing is bounded; sequence lookup is exact.
- Tests cover concurrent writers, replay, update/delete rejection, tampered stored bytes, and refusal to create a second registry database.

This is local SQLite persistence only. It does not yet provide multi-host consensus, backup/restore qualification, event/outbox coupling, authenticated source adapters, or API/HUD exposure. A multi-host deployment must not assume SQLite's local writer serialization is a distributed lock.


## Exact-head CI receipts

- Runtime PR #149 exact head `d5f0c7fe2c43599850aa980cbc08797ce9bfe482`: CI run `43604937482` **SUCCESS**. Diagnostics artifact `14117398094`, SHA-256 `00e870bc5ccc0983fd05e8cf4178be0f2b5a0a5546c590693f343b7dd37758c0`.
- Snapshot history PR #150 exact head `97107bbf38f2e68823fe7c3c7c18599656b7005f`: CI run `43605192756` **SUCCESS**. Diagnostics artifact `14118372468`, SHA-256 `aad40e4f92affdf10927f3e7c40bce8bc8fad534078add67b56d087a6582324d`.
- The latter exact-head run includes the DAG runtime test suite in the canonical CI workflow.
- Both PRs remain draft/stacked. These are engineering test receipts, not production qualification or independent evidence verification.


## Backup and restore qualification increment (2026-11-14)

`SnapshotHistory.backup_to` now creates a consistent SQLite online backup from the existing MerlinRegistry database. It publishes into an already-existing destination directory through a same-directory temporary file and atomic, non-overwriting hard-link publication. It refuses to overwrite an existing file or symlink.

Before publication, `verify_backup` opens the backup read-only and verifies:
- canonical MerlinRegistry project and artifact-version tables;
- qualification snapshot history and both append-only triggers;
- SQLite `integrity_check`;
- every stored snapshot's schema, canonical JSON bytes, and SHA-256 digest.

The returned backup receipt contains the backup file SHA-256 and the number of snapshots checked. Tests exercise a multi-snapshot backup/readback, overwrite rejection, and tampered snapshot rejection.

This is a local filesystem backup primitive, not an off-host backup service or disaster-recovery guarantee. Production qualification still needs encrypted off-host retention, restore into an isolated target, restore-point objectives, and periodic recovery drills. The API intentionally does not overwrite or mutate the source registry during restore.


## Adversarial and recovery follow-through (2026-11-14)

- Fixed a discovered OCI identity type contradiction: `task_ref` is a schema-validated ArtifactRef object, not text. Added acceptance and negative tests for both task and input references.
- Added a second, independent test implementation of the snapshot digest calculation using Python's JSON encoder and SHA-256, rather than calling the production canonicalization helper.
- Added 25 deterministic randomized acyclic graph cases. Each checks permutation-invariant snapshots, independently recomputed digests, and prerequisite-first topological order.
- Added local consistent backup, integrity verification, append-only trigger verification, non-overwrite publication, snapshot-by-snapshot digest checking, and tamper rejection.
- These checks strengthen the local projection and storage layer; they do not establish cross-host consistency, authenticated upstream retrieval, CACE signature validity, or production promotion authority.


### Failure-driven test correction
The first backup-verification CI run correctly rejected a deliberately tampered database because the tamper fixture had removed an append-only trigger. That exercised the earlier trigger-integrity guard rather than the intended stored-snapshot digest guard. The test now restores the expected trigger after injecting the tampered row, so the verifier must reach and reject the invalid snapshot itself. No production verifier behavior was weakened.


### Backup trigger authenticity
A further source review found that checking only SQLite trigger names would accept a same-name no-op replacement. Backup verification now compares normalized SQL definitions for both append-only guards, and a regression test replaces one guard with a same-name no-op trigger and confirms rejection. This preserves the distinction between a trigger being present and the intended enforcement actually being present.


### Trust-root lineage in verification nodes
Verification-receipt node identity now requires the trust authority ID, positive root version, Ed25519 root key ID, root public-key digest, positive trust-store version, signed trust-store digest, source authority, and retrieval identity in addition to the exact ArtifactRef and receipt digest. Trust-root node identity likewise binds a positive version, key ID, and public-key digest. This makes a root rotation or trust-store change a distinct graph identity and gives revocation/invalidation a concrete prerequisite node to target.


## Atomic snapshot-to-Hermes publication (2026-11-14)

The DAG snapshot ledger and the existing `MerlinEventOutbox` can now share the canonical MerlinRegistry SQLite database. `QualificationSnapshotPublisher` validates the snapshot, opens one `BEGIN IMMEDIATE` transaction, appends or replays the immutable snapshot, and enqueues a deterministic `merlin.qualification.snapshot` notification before committing. The event carries the snapshot digest, sequence, node count, and edge count; Hermes resolves the immutable snapshot by digest rather than trusting caller-supplied graph content.

The publisher rejects an outbox configured against a different database. If event idempotency conflicts after the snapshot insert, the same transaction rolls back both writes. Exact publication replay returns the same snapshot sequence and event identity. Hermes consumption remains at-least-once with explicit acknowledgement; handlers must remain idempotent.

This closes the local single-database dual-write gap only. It does not provide multi-host SQLite coordination, remote event delivery guarantees, encrypted off-host backup, source authenticity, CACE verification, or qualification authority. Existing independently hosted outboxes remain separate until explicitly migrated to the canonical registry database.


## Full MerlinRegistry backup and restore package (2026-11-14)

`MerlinRegistryBackup` packages a consistent SQLite database snapshot together with every content-addressed blob referenced by the database. It verifies blob path/digest/size while copying without following symlinks, records a canonical manifest, and publishes the ZIP without overwriting an existing destination. Package verification rejects duplicate/traversal paths, symlinks, malformed/noncanonical manifests, digest/size mismatches, missing/extra blobs, foreign-key failures, provenance digest drift, and invalid DAG snapshot history.

When the shared event outbox exists, verification also checks that each `merlin.qualification.snapshot` event's deterministic idempotency identity and payload point to the exact stored snapshot sequence/digest and matching node/edge counts. Restore verifies the complete package first, extracts into a fresh sibling staging directory, rechecks every restored blob, and atomically renames the new registry root into place without overwriting an existing target.

This is a local verified recovery package, not an encrypted or off-host backup. Production off-host qualification still requires independently provisioned encryption keys, authenticated object-storage transport, retention/immutability policy, access separation, and a timed restore drill on a separate host.


## KMS-wrapped encrypted backup envelope (2026-11-14)

`MerlinBackupEncryption` adds an authenticated, chunked AES-256-GCM envelope for verified registry backup ZIPs. It obtains a fresh 256-bit data-encryption key from an injected `BackupKeyProvider`, stores only the wrapped key and key-version identity in the canonical envelope header, and authenticates the complete header plus each chunk index as associated data. Nonces combine a random per-envelope 64-bit prefix with a monotonic 32-bit chunk counter. Decryption checks exact frame lengths, authentication tags, truncation/trailing bytes, plaintext size/digest, and then re-verifies the complete registry backup before publishing the plaintext archive.

The interface deliberately has no local-key fallback. Tests use a deterministic fake key provider solely to test envelope behavior. There is not yet a production OCI Vault/KMS adapter, independently provisioned key, object-storage transport, retention lock, or separate-host restore drill. Therefore this code qualifies the envelope format and failure behavior only; it does not qualify production encryption/key custody or off-host backup.
