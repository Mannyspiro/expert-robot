# Hermes to RSI authenticated induction bridge

## Scope

This change connects the existing bounded Hermes worker to the RSI research pipeline.
Hermes remains an execution agent. It can report an observed failure, but it cannot
create a qualified skill, approve a candidate, or promote anything to production.

The bridge is deliberately fail-closed. Missing source identity, signing material,
trusted public keys, or a valid receipt means no RSI seed is accepted.

## Failure record v2

The worker emits a merlin-hermes-failure/2 envelope only when the task carries
all three source identity fields:

- source_repo in owner/name form;
- exact lowercase 40-character source_commit;
- exact lowercase SHA-256 artifact_sha256.

The envelope also carries task/run/worker/stage identity, failure class,
bounded summary, normalized failure signature, trigger condition, and up to ten
corrective steps. The record is canonicalized and SHA-256 hashed. An Ed25519
receipt from issuer hermes signs claims binding the record digest and the
source repository, commit, artifact digest, and failure class.

The worker's signing key is injected at runtime using
HERMES_FAILURE_SIGNING_KEY_ID and HERMES_FAILURE_SIGNING_KEY_PEM.
Merlin verifies against its issuer trust store. Private keys are never committed.
If either side lacks configured key material, the capability remains unavailable;
test fixtures use ephemeral keys only.

## Ingestion and idempotency

ingest_hermes_failure verifies the complete record digest, not merely a subset
of its fields. A modified summary, trigger condition, corrective step, task ID,
or source locator invalidates the receipt.

Accepted failures are appended to the hash-chained AppendOnlyLedger as
rsi.induction_seeded events. A repeated event ID with the same authenticated
record digest is an idempotent replay. Reuse of an event ID for different
evidence is rejected.

The worker records an RSI ingestion status in its telemetry event. If source
identity is absent, the task still follows its normal retry/quarantine path but
does not become an RSI induction seed.

## Induction threshold

HermesRSIBridge reconstructs FailureTrajectory objects from authenticated
ledger entries. It will induce only when at least two distinct failure events
come from distinct run IDs, share the same failure signature, and provide
non-empty corrective steps with a non-empty common intersection. At most one
trajectory per run is admitted, preventing repeated retries in one run from
inflating the evidence count.

The restored RSI kernel produces a declarative SkillProcedure. The candidate
has no execution authority and no promotion authority. Candidate identity is
content-addressed. Its canonical JSON bytes are stored in the append-only
rsi_artifacts table, with immutable rows and a 10 MiB inline limit aligned to
the current CACE verifier transport limit. Larger artifacts require a separate
content-addressed object-store adapter and remain unqualified until available.

Candidate lineage binds the parent candidate, exact artifact digest, all
induction seed event hashes, source failure IDs, generator identity, and a
separate Merlin-source signature. Candidate provenance is not a proof of
correctness.

## Evaluation and promotion

The fixed five-domain held-out manifest remains
config/benchmarks/merlin_rsi_multidomain_holdout_v1.json: 25 cases, five each
for mathematics, Lean, research, coding, and engineering. The pipeline validates
case identity, domain coverage, frozen manifest digest, and evaluator receipts.
The evaluator must not expose reference outputs to the candidate generator.

Evaluation events and case outcomes are appended to the ledger. Optional GEPA
and Inspect adapters remain disabled unless they are installed and demonstrate
paired improvement on at least 20 identical held-out cases, with a conservative
lower 95% confidence bound above the configured gain threshold. A measured gain
only makes an adapter eligible for a controlled experiment; it does not promote
a candidate.

The current Merlin pipeline verifies the CACE attestation locally and requires
a separate signed merlin-approver receipt before promotion. The independent
CACE-native verifier tool is being added in the CACE OCI MCP service. Production
promotion must additionally require its exact-artifact verification result over
an authenticated MCP transport. Until that transport is connected and returns a
matching verification result, independent CACE verification is unavailable and
the candidate must not be promoted.

## Metadata retrieval

Crossref DOI and arXiv metadata retrieval uses a persistent SQLite cache,
response digests, bounded response sizes, explicit timeouts, a descriptive
User-Agent, and conservative host spacing (Crossref at least one second;
arXiv at least three seconds). Metadata is discovery/provenance context, not
proof that a research claim is true. Full article text is not copied into the
cache.

## Operational acceptance

1. Hermes failure receipt verifies against the configured trusted Hermes key.
2. Tampering with any record field is rejected.
3. Duplicate delivery of the same signed record is idempotent.
4. RSI induction requires distinct runs and convergent corrective steps.
5. Candidate artifact bytes and all seed hashes are persisted in the immutable ledger.
6. Held-out evaluation binds exact suite and candidate digests.
7. GEPA/Inspect remain disabled without paired evidence of improvement.
8. Independent CACE verification is required before a separate approval can promote.
9. Missing production keys, transports, evaluators, or artifact stores are reported
   as unavailable rather than simulated as successful.
