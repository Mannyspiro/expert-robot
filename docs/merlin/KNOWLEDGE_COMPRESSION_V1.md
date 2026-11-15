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

It now includes a strict UTF-8 text/Markdown extraction adapter, an optional bounded Hermes knowledge-extraction stage, and a provider-injected Ideonomy candidate enumerator. It does not yet provide PDF/image/video extraction, OCR, embeddings, model-based semantic compression, semantic deduplication, Hermes Ideonomy dispatch, Logos audits, independently trusted CACE verification, or production MCFC worker scheduling.

## 7. Exact-source reconstruction evaluator

Module: `python/merlin/knowledge_reconstruction.py`

Public entry point: `reconstruct_source_artifacts(registry, representation_ref, ...)`

The evaluator:
- re-reads the exact representation ArtifactRef through the canonical registry;
- requires immutable producer provenance for the knowledge-representation schema;
- validates the manifest fields, deterministic representation ID, logical path, transformation identity, source references and source locators;
- re-resolves and re-hashes each exact source ArtifactRef;
- returns the recovered original bytes separately from a JSON-safe, SHA-256-bound reconstruction report;
- enforces per-source and aggregate byte ceilings (25 MiB per source by default, 100 MiB aggregate by default, with a 1 GiB hard aggregate maximum).

The report explicitly says `semantic_equivalence=not_assessed`, `cace_verification=not_requested`, and `qualification=false`. It proves only that the exact original source bytes named by the representation were recoverable and matched their pinned ArtifactRefs at read time. It does not prove that a summary preserved meaning or that a transformation is reversible.

Tests cover exact recovery, multiple sources and locators, tampered manifest identity, missing/malformed source bindings, path substitution, and byte-budget enforcement.

## 8. Read-only retrieval integration

The existing `MerlinReadAPI` in `python/merlin/registry_queries.py` exposes:

`knowledge_representation(representation_ref)`

This method delegates manifest validation and exact source ArtifactRef resolution to `inspect_knowledge_representation`. It returns the manifest, producer provenance, exact source references, verified source-resolution metadata and locators. It does not return source bytes or mutate the registry, graph, hypotheses or outbox.

The query explicitly reports:
- `verification_scope=artifact-integrity-only`;
- `authority=derived-representation-only`;
- `qualification=false`;
- `source_bytes_included=false`.

The API verifies artifact identity and source reachability, not semantic correctness. Exact source bytes remain available through the separate bounded reconstruction operation.

Tests: `tests/test_knowledge_representation_queries.py` checks exact source bindings, verified resolution, no source-byte leakage, and read-only behavior of the existing registry and graph.

## 9. Source-located UTF-8 text extraction

Module: `python/merlin/text_extractor.py`

Public entry points:
- `extract_text_artifact(registry, source_ref, ...)` returns a deterministic extraction manifest.
- `store_text_extraction(registry, graph, source_ref, ...)` stores that manifest as a `text_extraction` representation through the existing canonical registry and graph.

The extractor:
- accepts exact ArtifactRefs and re-reads the pinned source bytes;
- enforces the existing 25 MiB artifact-read ceiling and a 5,000-segment limit;
- requires strict UTF-8 (no fallback encoding and no Unicode normalization);
- recognizes Markdown ATX headings, fenced code blocks, contiguous lists, blockquotes and paragraphs; plain text is grouped into paragraphs only;
- preserves original line endings and emits exact half-open byte ranges plus one-based inclusive line ranges;
- hashes each segment and assigns deterministic IDs;
- records an explicit whole-artifact source binding, including for empty files;
- fails closed on invalid UTF-8 or exceeded limits.

This is structural extraction, not semantic compression. It does not perform OCR or parse PDF, DOCX, HTML, code syntax trees, video or CAD. The source artifact remains authoritative.

Tests: `tests/test_text_extractor.py` covers multibyte UTF-8 and CRLF offsets, Markdown block classification, plain-text behavior, empty files, invalid UTF-8, resource limits, deterministic IDs, canonical storage and read-only query integration.

## 10. Hermes knowledge-extraction stage

The existing `python/merlin/hermes_stage_handlers.py` now supports an optional `knowledge_extraction` stage through `build_text_extraction_executor`.

Execution contract:
- The Hermes task must contain exactly one canonical source ArtifactRef, an explicit resource budget, and the existing approval/lease/authority fields required by `HermesWorker`.
- The executor bounds source bytes by both the extractor limit and one quarter of the task's declared memory budget, and honors cancellation checks before and after extraction.
- The executor calls `store_text_extraction`, which writes one deterministic source-bound representation through the existing registry and graph.
- The stage handler attaches that exact existing representation ArtifactRef to the hypothesis using `ResearchEvidenceRecorder.record_existing_artifact`; it does not copy the bytes into a second artifact.
- CACE is asked to verify the exact representation artifact with artifact kind `knowledge-representation` and schema `merlin-knowledge-representation/1`. If the verifier is unavailable, the result remains blocked/unverified and promotion authority remains false.
- The representation graph node is reused for the hypothesis evidence edge; no duplicate artifact node is created.

`ResearchEvidenceRecorder` now supports attaching existing ArtifactRefs and uses a deterministic idempotency key bound to the full ArtifactRef, hypothesis, evidence kind, description and source URL. This preserves distinct references even when their bytes match. `HypothesisLedger` adds a nullable unique idempotency-key column through an in-place SQLite migration; legacy ledgers remain readable. Replayed evidence writes return the same evidence record and can repair a graph projection after an interrupted attempt.

This is an optional stage handler, not an automatic production dispatch. The canonical Hermes outbox, approval validator, MCFC lease validator and worker must still be configured and invoked by the existing application composition.

Tests: `tests/test_hypothesis_ledger.py`, `tests/test_research_evidence.py`, and `tests/test_hermes_stage_handlers.py` cover migration, idempotency, exact ArtifactRef reuse, no duplicate bytes, graph linkage and the bounded stage contract.

## 11. Source-grounded Ideonomy candidate enumeration

Module: `python/merlin/ideonomy.py`

Public entry points:
- `ideonomy_capability(candidate_generator)` reports `unavailable` or `configured`, with `qualified=false` until an independent benchmark qualifies the generator.
- `enumerate_ideonomy_candidates(registry, text_extraction_ref, candidate_generator, ...)` verifies the exact source-bound text-extraction representation, supplies its segments and precise source-binding indexes to an injected generator, and validates the returned candidates.
- `store_ideonomy_candidate_set(registry, graph, candidate_set, ...)` revalidates the canonical candidate-set identity, stores it as an `ideonomy_candidates` representation, and idempotently projects candidate nodes and relations into the existing knowledge graph.

Enumeration includes concepts, claims, questions, methods, equations, procedures, counter-hypotheses, assumptions, definitions, theorems, experiments and datasets. Candidate relationships are restricted to the canonical graph's supported edge predicates.

Hard limits:
- 200,000 input characters;
- 2,000 precise source bindings;
- 500 candidates;
- 2,000 candidate relations;
- 20 source bindings per candidate.

Every candidate must cite one or more precise source locators. The generator receives source-binding indexes rather than being trusted to invent artifact paths or offsets. Candidate IDs and candidate-set IDs are deterministic. Confidence is explicitly labelled as a model estimate, not a truth probability. All candidates remain `unverified`, with `candidate_generation_only` authority; semantic verification and qualification remain false.

Graph projection creates typed candidate nodes, `contains` links from the candidate-set representation, `derived_from` links to exact source artifacts and the enumerated candidate relations. Repeated storage is idempotent. No source bytes are copied into the candidate set.

The generator is injected: there is no pretend/default AI provider. This module is not yet dispatched by Hermes and does not issue CACE receipts or promote hypotheses. A configured generator remains unqualified until held-out domain benchmarks and independent review pass.

Tests: `tests/test_ideonomy.py` covers exact source-binding constraints, deterministic identities, capability state, authority escalation rejection, graph relation validation, input budgets, idempotent graph projection, read-API retrieval and tamper rejection.

## 12. Next ranked implementation steps

1. **Exact-head CI:** run the focused representation, reconstruction and read-API tests plus full Merlin CI on the exact current branch head; retain logs and artifact digests.
2. **Additional extraction adapters:** add PDF, DOCX, code/AST, HTML, OCR/image and video extraction with exact source coordinates; the strict UTF-8 text/Markdown adapter is implemented.
3. **Hermes Ideonomy stage:** inject a configured candidate generator, schedule enumeration through the existing outbox/worker contract, and attach the stored candidate-set ArtifactRef without copying bytes.
4. **Logos skeptical audit:** challenge candidate claims, assumptions, alternative explanations and contradictions before any candidate is treated as supported.
5. **CACE verification:** independently verify exact producer artifacts and evidence bindings. Until a trusted transport is configured and a receipt is returned, status remains unverified.
6. **Additional extraction and domain paths:** PDF/DOCX, code/AST, HTML, OCR/image, video, mathematics, engineering/CAD/netlist and biological representations, each with separate benchmarks.
7. **Measured qualification:** compare methods on held-out retrieval, reconstruction, information-loss, storage, latency and compute tasks. Capability qualification and deployment remain separate approval steps.

## 13. Required invariants

- Never overwrite or delete original source artifacts as a compression side effect.
- Never merge distinct ArtifactRefs solely because their blob bytes match.
- Never silently merge conflicting claims or discard assumptions, caveats, uncertainty, units, coordinate frames, or source attribution.
- Never treat generated text, embeddings, hashes, simulations, or graph membership as proof.
- Never create a second canonical registry or duplicate the existing graph/outbox.
- Keep Avrea optional; local Linux x86-64 tests must remain possible, and OCI/other workers must implement the same bounded worker contract.
- Preserve all existing backup, snapshot-history, and exact ArtifactRef verification guarantees.
