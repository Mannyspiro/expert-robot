# Hermes Ideonomy Stage v1

## Purpose

The `ideonomy_enumeration` stage connects the source-grounded Ideonomy engine to Hermes without turning generated candidates into research evidence.

## Input contract

- Exactly one canonical `ArtifactRef` pointing to a verified `text_extraction` representation.
- A canonical Hermes resource budget containing `memory_bytes`.
- Optional bounded limits: `max_candidates` (1–500), `max_relations` (0–2,000), and `max_input_characters` (1–200,000).
- An injected candidate generator plus a separate runtime-owned provenance object. The generator response may contain only candidates and relations; any model-returned `generator` metadata is rejected. No provider is silently selected or simulated.

The effective character budget is the smaller of the requested limit and one quarter of the stage memory budget. The generator receives the verified extracted segments and precise source-binding indexes from the Ideonomy contract. Every candidate must cite one or more of those bindings. Runtime provenance is validated before invoking the generator, so missing or mutable provider identity fails closed without making a provider call.

## Output and persistence

The stage stores one immutable `ideonomy_candidates` knowledge representation with the generator identity/version, immutable provider revision, prompt/configuration/adapter digests supplied by the configured runtime, exact source representation and ArtifactRefs, source bindings, deterministic candidate-set identity, and candidate relations. Provenance is passed separately from the generator output so model-generated text cannot self-assert its provider identity. These declarations are still not provider-authenticated attestations. Candidate graph nodes retain their source links and are classified as `unverified_candidate`.

The hypothesis is linked to the candidate-set representation by a neutral `uses` graph edge with `relationship_class=candidate_discovery`. The stage intentionally does not call `ResearchEvidenceRecorder`, add hypothesis evidence, or change hypothesis status.

## Epistemic boundary

- `authority=candidate_generation_only`
- `epistemic_status=unverified`
- `semantic_verification=not_assessed`
- `qualification=false`
- `evidence_refs=[]`
- `promotion_authority=false`

A candidate is a prompt for subsequent skeptical review, not an assertion of truth. Runtime-owned provenance improves reproducibility and prevents model output from rewriting its declared identity; it does not prove that the provider actually served that revision. Logos review and independent CACE verification remain separate downstream stages. A CACE artifact receipt, if later requested, must bind the exact candidate-set ArtifactRef and must not by itself promote any candidate or hypothesis.

## Operational boundary

A durable SQLite stage journal, stored alongside the canonical registry, binds the task idempotency key to the immutable request digest. It checkpoints the exact generated candidate set before registry/graph projection and caches the completed result. If a worker crashes after generation or during projection, replay resumes from that checkpoint; graph projection is designed to be idempotent. The stable idempotency key is also passed to the generator adapter so a provider can deduplicate a call if it supports that feature. This does not guarantee exactly-once provider execution: a crash during an in-flight provider call may still require a retry, and concurrent expired-lease workers may overlap. The memory budget applies a conservative 32-bytes-per-input-character admission estimate, not an operating-system memory sandbox. The external MCFC/worker supervisor must still enforce process memory/CPU limits, deadlines, process-tree termination, and secret/network/filesystem isolation.

The stage is registered by supplying both `ideonomy_candidate_generator` and `ideonomy_candidate_generator_provenance` to `build_merlin_hermes_handlers`. Supplying only one fails closed. If no generator is injected, no Ideonomy handler is registered and the capability remains unavailable rather than silently substituting a fake model.
