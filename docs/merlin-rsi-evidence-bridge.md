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
authority. The append-only ledger acts as the durable outbox. The
dispatch_rsi_induction_seed boundary submits the seed with an idempotency key
and records dispatch only after a separately trusted merlin-rsi-worker Ed25519
acknowledgement binds the exact seed event and episode. Missing transport or
trust anchors fail closed. A live worker transport and its production key
distribution remain unconfigured.

## Candidate lineage and evaluation

Candidate creation requires a real Ed25519 merlin-source receipt binding
candidate ID, artifact digest, source repository, and exact source commit.
When a candidate originates from a Hermes failure, the receipt must additionally
bind the exact authenticated induction-seed event hash; the seed must already
exist in the canonical episode history. Parent candidate IDs must already exist.
Production APIs do not accept caller-injected signature verifiers. Tests use
ephemeral Ed25519 keypairs and exercise the same cryptographic verification path.

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

## OCI and CI validation status (2026-11-11)

The Cace-app repository's typed OCI gateway successfully executed the fixed
read-only MCP probe on runner cace-oci-a1. The probe confirmed the local MCP
endpoint at 127.0.0.1:8765 and successful read-only responses from
get_control_capabilities and get_cace_runtime_status. The live registry did
not expose get_github_runner_status or an artifact-verification operation.
The gateway currently allowlists inventory_snapshot and mcp_readonly_probe;
it does not execute arbitrary repository tests or shell commands.

The pinned RSI Python bridge was subsequently executed on the OCI runner
without package installation or persistent host changes:

- run 43122831275, runner cace-oci-a1 (Oracle Linux 9.8, ARM64);
- source commit fce180371c006debd8916b4a2be7f9b75bb0b03c;
- 10/10 Python tests passed, including real Ed25519 receipts, Hermes seed-to-
  candidate lineage, cache integrity, frozen-suite coverage, and CACE
  EvidenceBundle digest compatibility;
- Python 3.9.25 and preinstalled cryptography 36.0.1;
- uploaded artifact SHA-256:
  eaed9cd1bf9162c393764ab0a2f5305707b58c8ae71cb521302ee53a3eb9733a.

A separate OCI CACE contract run (43121546574) matched the CACE EvidenceBundle
v1 identity implementation. It produced bundle digest
0898289d4c6267dbc8de6e595e56f8f035ad0344b65431f8deb11be0972b0272 and
manifest digest
75a55dcb8d863afb50f2d9614444f36424049598cb243727ba51c11795bb8c74.
Its scope was bundle identity only, not a signed attestation or candidate
verification.

The C++ ledger test profile was attempted on OCI (run 43122690856) but returned
unavailable because the runner has no SQLite development header. No packages
were installed. The Avrea build check also reports no Avrea credits; the
dedicated hosted GitHub Actions jobs have not provided usable execution logs.
The C++ smoke tests therefore remain unverified on a live compiler.

No live CACE artifact attestation has been obtained for an Expert Robot
candidate. The CACE verification adapter remains fail-closed until a real
independent attestation and its independently distributed public-key pin are
available. No production promotion has occurred.
