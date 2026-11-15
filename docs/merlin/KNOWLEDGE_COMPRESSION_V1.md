# Merlin provenance-preserving knowledge representations v1

**Status:** initial implementation on `feat/merlin-knowledge-representations-v1-20261115`; exact-head CI and production integration are pending. This document is a contract, not a production acceptance record.

## 1. Architectural fit

This feature extends Merlin's existing canonical stores. It does **not** introduce a second artifact registry, knowledge graph, database, event ledger, or verification authority.

- `MerlinRegistry` owns projects, immutable artifact bytes, version history, ArtifactRefs and producer provenance.
- `MerlinKnowledgeGraph` owns typed concepts, claims, source references and relationships. Graph membership is not truth.
- `MerlinReadAPI` remains the read-only cross-domain query facade.
- `SnapshotHistory` and `QualificationSnapshotPublisher` own immutable qualification-DAG snapshots and their same-database Hermes outbox publication.
- Hermes schedules bounded work; MCFC supplies resource budgets and execution leases.
- Logos challenges interpretations and identifies omissions or contradictions.
- CACE independently verifies exact artifacts and evidence. This module does not issue CACE receipts or mark representations qualified.

The implementation stores each derived representation as a normal versioned artifact in the existing `MerlinRegistry`. It adds an `object_view` node to the existing knowledge graph and `derived_from` edges to exact source-artifact reference nodes.

## 2. Representation contract

Schema: `merlin-knowledge-representation/1`.

A representation manifest contains exactly these semantic fields:

- `schema`: schema identifier.
- `project_id`: canonical Merlin project.
- `representation_type`: `summary`, `atomic_claims`, `concept_index`, `symbolic`, `procedure`, `media_index`, `embedding_metadata`, or `other`.
- `payload`: JSON-compatible derived content.
- `source_artifacts`: one or more exact `merlin-artifact-ref/1` references.
- `source_bindings`: one or more source locations, each bound to one declared ArtifactRef.
- `transformation`: tool identity and version.
- `loss_character`: `lossy`, `unknown`, or `reversible_claim`.
- `representation_id`: SHA-256 of the canonical JSON body excluding this field.

Supported source locator types are `page`, `section`, `line_range`, `byte_range`, `frame`, `timecode`, `node_id`, and `whole_artifact`. Locator payloads remain source-format-specific; future schema revisions should introduce typed locator contracts where exact coordinate semantics are needed.

All source ArtifactRefs are resolved through the existing registry before storage. This rechecks their exact project/path/version/digest identity, blob bytes and size. A client-supplied digest is never accepted as proof by itself.

## 3. Storage and graph projection

The deterministic registry path is:

`knowledge/representations/<representation_id>.json`

The artifact is written with the existing immutable producer-provenance contract:

- source repository;
- full source commit;
- producer artifact ID;
- producer artifact kind;
- representation schema.

The graph projection uses:

- `object_view` for the derived representation;
- `artifact_reference` for each exact source ArtifactRef;
- `derived_from` edges from the representation to each source reference.

Source graph-node identity hashes the complete canonical ArtifactRef, not only the blob digest. The same bytes registered at two logical paths or versions therefore remain distinct source references.

Repeated identical writes are deterministic and idempotent. Changed payload, source version, locator, or tool version produces a different representation identity and a new immutable registry artifact.

## 4. Failure and transaction semantics

The registry and knowledge graph currently use separate SQLite databases. A cross-database atomic transaction is not claimed.

The write sequence is deliberately recoverable:

1. Validate the representation contract and all source references.
2. Re-resolve and hash every exact source ArtifactRef.
3. Store the canonical manifest as an immutable registry artifact.
4. Resolve and verify the newly stored representation ArtifactRef.
5. Idempotently create the graph nodes and edges.

If the process stops between steps 3 and 5, the registry artifact remains intact. Replaying the same operation repairs the missing graph projection. A conflicting graph node or edge fails rather than overwriting prior content.

A later integration should publish a durable outbox event only after both projections are complete, or use a repairable projection-job protocol. Do not claim a cross-database transaction by reusing the qualification snapshot publisher: that publisher is atomic only for its own single registry database.

## 5. Epistemic and authority boundaries

- A representation is marked `derived_unverified`.
- The return value reports `verification: not-verified` and `authority: derived-representation-only`.
- `reversible_claim` is a producer declaration, not a reconstruction proof.
- A semantic summary is not the original source.
- An embedding is a retrieval aid, not evidence.
- A source hash proves byte identity, not truth.
- Graph edges describe asserted relationships, not independently established facts.
- No claim is automatically promoted, no proof is inferred, and no CACE receipt is fabricated.

Original artifacts remain in the canonical registry. Lossy representations may improve retrieval but must never replace the source.

## 6. Current implementation surface

Module: `python/merlin/knowledge_compression.py`

Public entry point: `store_knowledge_representation(...)`

Tests: `tests/test_knowledge_compression.py`

The initial implementation covers deterministic serialization and IDs, strict source-reference and locator validation, source re-resolution, canonical registry storage, provenance, graph projection, idempotent replay, changed-payload identity, and fail-closed behavior for malformed or mismatched sources.

It does not yet provide HTTP endpoints, extraction, embeddings, model-based compression, semantic deduplication, automatic claim decomposition, Logos audits, CACE verification, Hermes dispatch, or MCFC worker scheduling.

## 7. Next ranked implementation steps

1. **Exact-head CI:** run the focused knowledge-representation tests and full Merlin CI on the exact branch head; retain logs and artifact digests.
2. **Reconstruction evaluator:** define exact-source recovery tests and explicit lossy-summary omission/contradiction benchmarks. A `reversible_claim` must not be upgraded without a successful independent reconstruction receipt.
3. **Read-only retrieval integration:** extend the existing `MerlinReadAPI` to retrieve representation manifests and their source bindings without adding another query store.
4. **Extraction adapters:** add text/PDF/code/JSON extractors that produce source-bound locators and never alter source bytes.
5. **Ideonomy and Hermes:** enumerate candidate concepts/claims, then schedule bounded extraction and representation jobs through the existing outbox and worker contracts.
6. **Logos and CACE:** challenge derived claims and verify exact producer artifacts with a configured, independently trusted CACE transport. Until then, status remains unverified.
7. **Domain-specific paths:** mathematical/formal, code, engineering/CAD/netlist, biological and multimodal representations, each with separate benchmarks.
8. **Measured promotion:** qualify compression methods against held-out tasks, retrieval quality, reconstruction, storage, latency and compute. Capability qualification and deployment remain separate approval steps.

## 8. Required invariants

- Never overwrite or delete original source artifacts as a compression side effect.
- Never merge distinct ArtifactRefs solely because their blob bytes match.
- Never silently merge conflicting claims or discard assumptions, caveats, uncertainty, units, coordinate frames, or source attribution.
- Never treat generated text, embeddings, hashes, simulations, or graph membership as proof.
- Never create a second canonical registry or duplicate the existing graph/outbox.
- Keep Avrea optional; local Linux x86-64 tests must remain possible, and OCI/other workers must implement the same bounded worker contract.
- Preserve all existing backup, snapshot-history, and exact ArtifactRef verification guarantees.
