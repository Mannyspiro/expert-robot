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
