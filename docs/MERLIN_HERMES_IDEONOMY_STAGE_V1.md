# Hermes Ideonomy Stage v1

## Purpose

The `ideonomy_enumeration` stage connects the source-grounded Ideonomy engine to Hermes without turning generated candidates into research evidence.

## Input contract

- Exactly one canonical `ArtifactRef` pointing to a verified `text_extraction` representation.
- A canonical Hermes resource budget containing `memory_bytes`.
- Optional bounded limits: `max_candidates` (1–500), `max_relations` (0–2,000), and `max_input_characters` (1–200,000).
- An injected candidate generator. No provider is silently selected or simulated.

The effective character budget is the smaller of the requested limit and one quarter of the stage memory budget. The generator receives the verified extracted segments and precise source-binding indexes from the Ideonomy contract. Every candidate must cite one or more of those bindings.

## Output and persistence

The stage stores one immutable `ideonomy_candidates` knowledge representation with the generator identity/version, exact source representation and ArtifactRefs, source bindings, deterministic candidate-set identity, and candidate relations. Candidate graph nodes retain their source links and are classified as `unverified_candidate`.

The hypothesis is linked to the candidate-set representation by a neutral `uses` graph edge with `relationship_class=candidate_discovery`. The stage intentionally does not call `ResearchEvidenceRecorder`, add hypothesis evidence, or change hypothesis status.

## Epistemic boundary

- `authority=candidate_generation_only`
- `epistemic_status=unverified`
- `semantic_verification=not_assessed`
- `qualification=false`
- `evidence_refs=[]`
- `promotion_authority=false`

A candidate is a prompt for subsequent skeptical review, not an assertion of truth. Logos review and independent CACE verification remain separate downstream stages. A CACE artifact receipt, if later requested, must bind the exact candidate-set ArtifactRef and must not by itself promote any candidate or hypothesis.

## Operational boundary

Cancellation is checked before enumeration and again before persistence. Enumeration is bounded by the resource budget and the existing Ideonomy input/candidate/relation limits. The stage uses the existing registry, graph and hypothesis ledger; it creates no parallel store.

The stage is registered by supplying `ideonomy_candidate_generator` to `build_merlin_hermes_handlers`. If no generator is injected, no Ideonomy handler is registered and the capability remains unavailable rather than silently substituting a fake model.
