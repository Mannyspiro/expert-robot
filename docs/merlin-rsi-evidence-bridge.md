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

The embedded public key is not trusted by itself. The CACE verifier key ID
must match a server-loaded, digest-pinned allowlist in
MERLIN_CACE_TRUST_STORE_JSON / MERLIN_CACE_TRUST_STORE_SHA256. The trust-store
document uses schema merlin-cace-trust-store-v1 and contains active key IDs
bound to verifier identity cace. Callers cannot pass their own CACE allowlist.
Hermes, merlin-source, merlin-evaluator, merlin-rsi-worker, and merlin-approver
public keys are likewise loaded from the digest-pinned
MERLIN_ISSUER_TRUST_STORE_JSON / MERLIN_ISSUER_TRUST_STORE_SHA256 registry.
Missing stores, unknown issuers, invalid Ed25519 keys, or digest mismatches
fail closed. A valid signature authenticates provenance; it does not prove
mathematical truth or replace Lean, numerical, or engineering checks.

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

The Cace-app repository's typed OCI gateway successfully executed fixed
read-only MCP probes on runner cace-oci-a1. The probe confirmed the local MCP
endpoint at 127.0.0.1:8765 and successful read-only responses from
get_control_capabilities and get_cace_runtime_status. The live MCP registry
exposed only CACE control-plane tools (runtime status, logs, OCI summary,
attached NSG inspection, and ingress/restart controls); it did not expose an
artifact-verification, attestation-signing, or GitHub-runner-status operation.
No control-plane mutations were invoked. The gateway executes only its
allowlisted fixed profiles; it does not enable arbitrary shell commands.

The current pinned RSI bridge was executed on OCI:

- Python run 43124286254, runner cace-oci-a1 (Oracle Linux 9.8, ARM64);
- exact source commit 70269acb55093c2071f204c6b2607c11ec2ae99f;
- 15/15 tests passed, including real Ed25519 receipt verification, trust-store
  digest tampering and self-approval rejection, authenticated Hermes failure
  dispatch and worker acknowledgements, candidate lineage, Crossref/arXiv
  caching and rate limiting, CACE bundle parity, and controlled promotion gates;
- frozen benchmark manifest: 25 cases across five domains;
- Python 3.9.25 and preinstalled cryptography 36.0.1;
- no package installation or persistent host mutation;
- artifact SHA-256:
  ded6c5796ea53f70544e6ff1f205af173dd9cbe23a292219f7c7f2e5c790e9d9.

The C++ ledger profile also passed on the same source commit:

- run 43124335696 on cace-oci-a1;
- both generation-lineage and research-episode C++20 smoke tests compiled
  and executed successfully;
- Python-to-C++ SQLite interoperability passed: Python appended a canonical
  episode and the C++ ResearchEpisodeLedger independently verified its root;
- GCC 11.5.0 linked the runner's existing libsqlite3.so.0;
- because the runner has no development header, the test workspace used a
  pinned declaration-only SQLite ABI shim. This is test-only infrastructure,
  not a production SQLite header or vendored implementation;
- no package installation or persistent host mutation;
- artifact SHA-256:
  8a66907020431a550dae9ced35761ec87a96e9931f69fd86285f2502c42654a9.

Separate trust-store validation profiles also passed on OCI (runs 43123886846
and 43123913124), exercising the active CACE and issuer trust-store contracts.
The CACE EvidenceBundle identity profile (run 43121546574) matched the pinned
CACE implementation. Its scope remains bundle identity only.

The Avrea build check still reports no Avrea credits, and hosted GitHub Actions
checks have not supplied usable logs; the fixed OCI profiles are therefore the
current execution evidence.

No live CACE artifact attestation has been obtained for an Expert Robot
candidate. The current OCI MCP surface has no artifact-verification or
attestation-signing operation. The RSI adapter therefore remains fail-closed
until a separately operated CACE verifier is wired to the exact EvidenceBundle,
issues a real signed attestation, and its public-key fingerprint is delivered
through the independently controlled CACE trust-store channel. The Hermes,
source, evaluator, worker, approver, and CACE trust-store environment values
are not provisioned by this code change. No production promotion has occurred.
