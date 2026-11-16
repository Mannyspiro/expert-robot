# Merlin Logos Source-Bound Review Stage v1

## Purpose

The `logos_review` stage is a skeptical, non-authoritative review pass over one exact stored Ideonomy candidate-set ArtifactRef. It does not establish truth, proof, semantic entailment, CACE verification, qualification or promotion.

## Input contract

- Exactly one canonical ArtifactRef to a `knowledge-representation` whose representation type is `ideonomy_candidates`.
- The candidate-set representation manifest and every source ArtifactRef must pass canonical registry inspection.
- The embedded source extraction ArtifactRef must resolve to a `text_extraction` representation with the exact source representation identity recorded by Ideonomy.
- Every candidate source locator must be present in the inspected extraction manifest. Candidate identities are recomputed from their source representation ID, full generator provenance and candidate content before the reviewer is called.
- Runtime-owned reviewer provenance is required before any provider call: reviewer ID/version, immutable provider revision, prompt digest, generation configuration digest and adapter build digest.
- The reviewer receives the exact candidate-set ArtifactRef/digest, candidate payload, verified source refs and bounded resource metadata.

The reviewer response is restricted to complete per-candidate reviews, typed findings, counter-hypotheses, falsifiability questions and limitations. It cannot supply or replace reviewer provenance.

## Finding semantics

- `quotation`: must cite one or more exact source-binding indexes. A quotation without a locator is rejected.
- `interpretation`: an interpretation, not a direct source statement.
- `hypothesis`: a reviewer-generated possibility, not source evidence.

Every candidate must receive exactly one disposition:
- `retain_for_testing`
- `challenge`
- `insufficient_source`
- `source_conflict`

There is deliberately no `verified`, `accepted`, `proven` or `promote` disposition. Counter-hypotheses and falsifiability questions remain prompts for later experiments or proofs.

## Persistence and replay

The validated review is stored through the existing canonical knowledge-representation store, linked to the exact candidate-set representation and its underlying source artifacts. The graph records a `reviews` edge from the derived review representation to the candidate-set representation. The existing Hermes stage journal checkpoints the validated review before registry/graph projection and caches completed results under the task idempotency key.

The review identity includes runtime-owned reviewer provenance. A replay with changed candidate inputs or reviewer provenance is rejected by the journal's immutable request digest.

## Epistemic and trust boundary

The stored result remains:
- `authority=skeptical_review_only`
- `epistemic_status=unverified`
- `semantic_verification=not_established`
- `qualification=false`
- `promotion_authority=false`
- `evidence_refs=[]`

Runtime-owned provenance is tamper-evident configuration, not provider-authenticated attestation. Logos is not an independent CACE verifier. The stage must not mutate hypothesis status or evidence. Independent CACE verification of the exact candidate-set and review ArtifactRefs remains a separate gate.

## Operational blockers

The stage journal provides replay after the validated review checkpoint, but it does not provide OS-level resource isolation or exactly-once provider execution during an in-flight crash. Production execution still requires the external MCFC/worker supervisor to enforce deadlines, process-tree termination, memory/CPU limits, secret/network/filesystem isolation and concurrency leases. No production dispatch or capability qualification is implied by this source implementation.

## Validation status

Regression tests are authored for full candidate coverage, exact quotation locators, disallowed authority dispositions, candidate identity tampering and immutable reviewer provenance. Tests have not been executed; this change is source-authored and source-reviewed only.
