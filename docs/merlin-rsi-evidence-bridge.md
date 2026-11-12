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

The production bridge is implemented in `python/merlin/hermes_rsi_bridge.py`
and `python/merlin/hermes_worker.py`. A Hermes failure uses the bounded
`merlin-hermes-failure/2` envelope. Its Ed25519 receipt binds the complete
record digest, event identity, source repository/commit, artifact SHA-256,
and failure class. The RSI ingress verifies the digest-pinned issuer trust
store and signature before idempotent ingestion into the canonical append-only
evidence ledger. Replays with changed content are rejected.

Induction is stricter than merely observing repeated errors. It requires at
least two distinct authenticated failure events from independent runs, with
unique receipt digests and one normalized failure signature. The inducer
computes the ordered intersection of corrective steps; it does not invent
repairs, execute generated text, or grant promotion authority. Candidate bytes
are canonicalized and content-addressed. A separate Merlin-source Ed25519
receipt binds the candidate digest, source commit, induction seed event hashes,
source failure IDs, and parent lineage.

The worker submits a signed failure record before retry/quarantine when both
the signer and ingestion sink are explicitly injected. Missing source identity
or missing signing configuration fails closed; no unsigned induction seed is
created. The durable outboxes use idempotency keys, expiring leases, fenced
acknowledgements, bounded retries, and quarantine/dead-letter states. The
worker itself is bounded execution only and cannot promote a candidate.

The production trust-store and signing-key environment variables are not
provisioned by this PR. The bridge code and tests are present, but production
Hermes signing and live ingestion remain unavailable until issuer public keys
are independently pinned and private signing secrets are configured. The
separate CACE verification and signed-approval gates remain mandatory.

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

CACE artifact-integrity attestation and independent-reproduction verification
are separate evidence classes. The loopback MCP attestor can issue only an
artifact-integrity statement after exact artifact-byte verification; it is
recorded as candidate.cace_integrity_attested and is never promotion evidence.
Only a separately produced CACE independent-reproduction attestation can be
recorded as candidate.cace_verified. The latter uses the existing
cace-signed-attestation-v1 Ed25519 profile and CACE EvidenceBundle v1 digest rules.
It must bind the
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

The production integration uses CaceMcpVerifier over the loopback-only CACE
MCP endpoint. It submits the exact bundle, attestation, expected bindings, and
base64 artifact bytes to verify_merlin_rsi_attestation, checks the structured
CACE response against locally reconstructed bundle and attestation digests,
then repeats local pinned-key verification before appending candidate.cace_verified.
The artifact-integrity attestor is a separate operation and cannot satisfy this
verification path.

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

The current RSI bridge and its CACE MCP verification client were executed on OCI:

- run 43130141075 on cace-oci-a1 (Oracle Linux 9.8, ARM64);
- exact Expert Robot source commit 1822a54226d9d1045769b696e264ff8f3edd7de6;
- Python 3.9.25; compile passed; 22/22 RSI tests passed;
- tests include authenticated Hermes failure ingestion, signed worker ACK/idempotency,
  append-only candidate/evaluation lineage, independent-reproduction versus
  artifact-integrity separation, a CACE MCP verifier client contract, strict
  separate approval for promotion, and optional adapter paired-gain gates;
- frozen benchmark manifest SHA-256
  543dbb105d6baf62dbfee54cdd8c7e483f2a9ab799e651dddda8066ce0f5a36f,
  with 25 cases across mathematics, Lean, research, coding, and engineering;
- Python compile and unit tests ran without package installation or host mutation;
- OCI job receipt marks qualification=false and proof_implication=none.

A separate live public-metadata probe passed on OCI (run 43130444733):

- Crossref DOI 10.1038/nature12373 resolved to “Nanometre-scale thermometry in a living cell”;
- arXiv 1706.03762 resolved to “Attention Is All You Need”;
- exactly one HTTP request per provider; each second lookup was served from the
  SQLite cache (two cache-hit replays);
- response digests were persisted, and per-host request clocks were written for
  api.crossref.org and export.arxiv.org;
- only those two public metadata hosts were allowlisted; this is discovery
  provenance, not mathematical proof.

The C++ ledger profile passed on OCI (run 43128137652):

- generation-lineage and research-episode C++20 smoke tests compiled and ran;
- Python-to-C++ SQLite interoperability passed: Python appended a canonical
  episode and the C++ ResearchEpisodeLedger independently verified its root;
- GCC 11.5.0 linked the runner's existing libsqlite3.so.0;
- because the runner has no development header, the test workspace used a
  pinned declaration-only SQLite ABI shim, not a production header or vendored
  SQLite implementation;
- no package installation or persistent host mutation.

Earlier OCI trust-store validation profiles (runs 43123886846 and 43123913124)
and the CACE EvidenceBundle identity profile (run 43121546574) also passed.
Those scopes remain limited to trust-store contract and bundle identity.

The Avrea build check still reports no Avrea credits. The fixed OCI profiles
are the current execution evidence; none of these runs is a production
qualification or proof receipt.

No live CACE artifact attestation has been obtained for an Expert Robot
candidate. The live OCI MCP service still has no artifact-verification or
attestation-signing operation. A CACE-native verifier and narrowly scoped artifact-integrity signer have
been implemented in Cace-app PR #93
(https://github.com/morganaspim/Cace-app/pull/93). They delegate EvidenceBundle
and Ed25519 semantics to CACE core, require exact artifact bytes (10 MiB
aggregate cap), exact candidate/binding digests, and a separately pinned CACE
key ID. The signer creates a one-time Ed25519 identity and signs only after
CACE verifies every bundle artifact byte. The attestation purpose is
`artifact-integrity`, not independent mathematical reproduction; proof effect
remains none and promotion authority remains separate. CACE regression tests
passed on cace-oci-a1 in runs 43127067362, 43128003745, and 43128015130.
The latest passing run includes the strict independent-reproduction purpose
gate. The PR has not been deployed, and no live signing key or trust-store
entry has been provisioned. The RSI adapter remains fail-closed until the verifier/signer is
deployed, its CACE key is initialized, and its public-key fingerprint is pinned
through the independently controlled CACE trust-store channel. The Hermes,
source, evaluator, worker, approver, and CACE trust-store environment values
are not provisioned by this code change. No production promotion has occurred.

### Cross-repository CACE verifier qualification (2026-11-12)

Cace-app PR #93 adds `ops/oci_mcp/merlin_rsi_verifier.py` and
`tests/test_merlin_rsi_cace_verifier.py`. The verifier delegates canonical
bundle parsing, artifact hashing, and Ed25519 signature validation to CACE's
own `cace_studio.core.evidence_ledger` and `cace_studio.core.attestation`
implementations. It checks the exact candidate ID, complete expected bindings,
active digest-pinned CACE key, independent-reproduction purpose, and supplied
artifact bytes (10 MiB aggregate cap). Its return value is explicitly
`authority=verification-only` and `proof_effect=none`.

The reproduction attestor now checks the successful CACE OCI run's request
operation, exact source commit, workflow source pin, GitHub job/runner identity,
retained job-artifact digest, and the Git blob SHA-1 of the exact RSI module,
test file, and frozen benchmark at the requested Expert Robot commit. It
includes these run facts as `cace_runner_provenance` inside the signed
independent-reproduction statement; the verifier rejects such a statement if
the provenance is absent, malformed, or inconsistent. CACE tests cover this
path with a deterministic GitHub API fixture, not a live candidate attestation.

The CACE collaboration-validation workflow explicitly runs
`tests/test_merlin_rsi_cace_verifier.py`; runs 43129186420 and 43130550343
completed successfully on `cace-oci-a1`. The test exercises valid CACE-native bundle/attestation
verification, missing or tampered trust stores, unpinned keys, claim/binding
mismatch, wrong purpose, altered artifact bytes, and size limits. This is
CACE-side implementation and regression evidence, not evidence that a live
Expert Robot candidate has already been submitted to a deployed CACE verifier.

Expert Robot now has a distinct `CaceMcpVerifier` client. It sends the
exact EvidenceBundle, attestation, bindings, and artifact bytes to the
read-only CACE MCP verifier, validates the returned bundle and attestation
digests, and then independently repeats pinned-key verification before
appending `candidate.cace_verified`. The artifact-integrity signer remains a
separate endpoint and cannot satisfy this path. The fixed OCI RSI suite passed
22/22 tests for source commit 1822a54226d9d1045769b696e264ff8f3edd7de6
in run 43130141075. Its CACE MCP client test uses a deterministic fake
transport; it does not establish that the deployed OCI MCP endpoint has the
trust store or is currently serving the new tool.

The current CACE verifier source blob is
`5cf3acde39ba1bfc072fb1c1d16731d592087948`; its regression test blob is
`67b89a6a122d6da57aec1ba203fd1e5b72c6eb03`. The workflow file explicitly
includes that test. Cace-app PR #93 remains open and targets the OCI inventory
qualification branch; it is not merged into the CACE default branch.

**Promotion boundary remains unchanged:** the Expert Robot pipeline can
validate an independently signed CACE attestation against its pinned key and
then require a separate signed `merlin-approver` receipt. However, no live
CACE-signed attestation or production verifier execution receipt for an actual
Expert Robot candidate has been received. The read-only OCI MCP surface still
does not expose the verifier or signing operation, and the CACE signing key
has not been provisioned to a production transport. Until that exists, no
candidate may be promoted. The successful CACE regression suite is not a
substitute for a live cross-repository evidence receipt.
