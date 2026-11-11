# Merlin RSI evidence bridge

## Current architecture

The Python ingress adapter writes directly to the same SQLite table and hash
format used by the C++ ResearchEpisodeLedger:

- table: research_episode_events;
- per-episode sequence starts at zero;
- payload identity is SHA-256 of canonical UTF-8 JSON;
- event identity is the C++ episode hash material, including episode ID,
  sequence, event type, payload digest, and previous event hash;
- writes use BEGIN IMMEDIATE;
- SQLite update/delete triggers make event history append-only.

The C++ GenerationLineageStore separately persists candidate ancestry,
evaluation records, and promotion decisions. Its candidate, evaluation, and
promotion tables now reject UPDATE and DELETE. The episode ledger carries the
full provenance receipts and benchmark bindings, allowing the C++ reader to
verify the same history. The Python adapter does not create a parallel RSI
event table.

## Hermes failure to RSI induction

A Hermes failure is accepted only when a recent Ed25519 receipt verifies
against a configured trusted Hermes key and binds the exact event ID, failure
class, source repository, 40-hex commit, and artifact SHA-256. The event ID is
the stable episode ID, making retries idempotent. A replay with changed evidence
is rejected.

An accepted event creates an induction seed that requests generalization,
counterexample generation, regression-test proposals, and alternative
representation search. It grants no candidate, evaluator, or promotion
authority. The current bridge persists the seed; dispatching the seed into a
live model-backed RSI worker remains a separate orchestration integration.

## Candidate lineage and evaluation

Candidate creation requires a signed merlin-source receipt binding candidate
ID, artifact digest, source repository, and exact source commit. Parent IDs must
already exist in the canonical episode history.

Evaluation requires a signed merlin-evaluator receipt binding candidate ID,
candidate digest, frozen benchmark manifest digest, metrics digest, and
pass/fail status. Metrics must be finite. Candidate and evaluation events are
written to the same C++ research episode chain.

## CACE verification and controlled promotion

CACE verification uses the existing cace-signed-attestation-v1 Ed25519
profile and CACE EvidenceBundle v1 digest rules. The attestation must bind the
candidate ID, exact candidate digest, benchmark manifest digest, evaluator
receipt digest, source repository, source commit, and
authority=verification-only.

The embedded public key is not trusted by itself. The verifier key ID must
match an independently configured allowlist mapping the key ID to verifier
identity cace. A valid signature authenticates the attestation; it does not
prove mathematical truth or replace Lean, numerical, or engineering checks.

Promotion additionally requires a separate signed merlin-approver receipt
bound to the same candidate, artifact, benchmark, and CACE attestation digest.
The candidate must have a passing evaluation, a prior CACE verification event,
and a valid episode hash chain. No automatic promotion is performed.

Until Hermes, evaluator, CACE, and approver trust anchors are provisioned and
reviewed through their respective trust channels, those capabilities remain
unavailable. Do not treat embedded keys, local mocks, unsigned JSON, or a
successful inventory probe as CACE verification.

## Crossref and arXiv

ResearchMetadataCache retrieves public Crossref DOI metadata and arXiv Atom
metadata. It stores canonical JSON plus a response digest in SQLite, checks
cache integrity, and uses a 30-day default TTL. A SQLite-backed per-host request
clock enforces minimum intervals across processes: at least one second for
Crossref and three seconds for arXiv. HTTP 429 and transient 5xx responses have
a bounded retry budget. Metadata is research-discovery provenance, not proof.

## Fixed held-out suite v1

config/benchmarks/merlin_rsi_multidomain_holdout_v1.json freezes 25 cases:
five each for mathematics, Lean, research, coding, and engineering. Its
manifest digest must be attached to every evaluation receipt. Any changes to
cases or scoring require a new versioned manifest; v1 is never silently edited.

This first manifest is a fixed task set and contract, not yet a fully calibrated
universal ranking benchmark. Domain evaluator implementations, blind reference
outputs, inter-rater calibration, and a sufficiently large paired corpus remain
qualification work. Results must be reported per domain; no single aggregate
score may hide a domain regression.

## GEPA and Inspect

GEPA and Inspect remain optional. The base runtime does not install them or
depend on them. An adapter is eligible only after at least 20 paired held-out
cases across all five domains, a lower 95% confidence bound above 1% aggregate
gain, and no negative mean gain in any domain. Eligibility is not production
routing or promotion approval. Measure quality, latency, compute cost, failure
rate, and reproducibility before a controlled trial.

## Production gaps that remain explicit

1. Connect the authenticated induction seed to the live Hermes/RSI dispatch
   worker and collect a worker execution receipt.
2. Provision and pin reviewed Hermes, evaluator, CACE, and approver public keys.
3. Implement the five domain evaluators and blind reference outputs, then run
   paired baseline/candidate evaluations on the frozen suite.
4. Connect the Python episode adapter to the service's configured
   research_episodes.sqlite3 path and reconcile candidate events into the
   C++ GenerationLineageStore projection.
5. Add an independently operated CACE job that fetches the exact candidate
   artifact, verifies it, constructs the CACE EvidenceBundle, and signs the
   exact bound attestation.
6. Add key rotation/revocation and durable evidence retention before enabling
   production promotion.

The workflow added with this change validates the Python bridge, benchmark
manifest, and C++ append-only stores on hosted CI. It does not claim a live
CACE verification or production promotion.
