# Titan ↔ CACE Attestation Integration Gap

**Status:** interface analysis; no CACE code changed and no receipt issued.
**Reviewed CACE repository:** `morganaspim/Cace-app`, branch `main`.
**Relevant existing files:** `schema/signed-attestation-v1.schema.json`, `cace_studio/core/attestation.py`, `docs/ATTESTATIONS.md`, `docs/PROVENANCE_ATTESTATION.md`.

## Existing CACE capability

CACE already defines a signed-attestation envelope:
- Ed25519 signature;
- canonical JSON statement with a domain separator;
- verifier identity and verifier key ID;
- claim ID and evidence-bundle SHA-256;
- timestamp, purpose and an extensible `bindings` object;
- `proof_effect: "none"`, explicitly separating provenance from mathematical proof.

The existing profile is useful for authenticated provenance, but Ed25519 is not a post-quantum signature. It must not be described as a PQC receipt or as a quantum-resistant long-term signature.

## Titan receipt binding profile

A Titan-to-CACE adapter should submit a canonical evidence bundle and populate CACE's statement bindings with exact identifiers, not caller assertions:

- `source_repository`
- `source_commit_sha`
- `workflow_run_id`
- `workflow_run_attempt`
- `runner_identity`
- `runner_image_or_environment_digest`
- `workflow_file_path`
- `workflow_file_commit_sha`
- `toolchain_manifest_sha256`
- `command_manifest_sha256`
- `input_manifest_sha256`
- `output_manifest_sha256`
- `artifact_sha256`
- `verifier_repository`
- `verifier_commit_sha`
- `verifier_toolchain_sha256`
- `verification_result`
- `verification_scope`
- `nonclaims`

The adapter must verify GitHub run metadata against the repository API, download and hash the exact artifact, verify the checked-out commit and workflow identity, and have CACE independently re-run or validate the artifact according to its verifier class. A caller-supplied SHA is never sufficient.

## Signature profile and migration

The current CACE schema fixes `signature_algorithm: ed25519`. For a future PQC profile:
1. preserve the current v1 envelope unchanged for compatibility;
2. define a separately versioned v2 envelope with explicit algorithm identifiers and canonical signing bytes;
3. use a vetted, independently reviewed ML-DSA implementation conforming to FIPS 204;
4. include key ID, public-key encoding, parameter set, canonicalization profile, domain separator and signature bytes;
5. support key rotation, revocation and verifier trust policy;
6. test with official FIPS 204 known-answer vectors and cross-implementation verification;
7. require independent review before any production use.

Do not implement custom signature code or silently reinterpret an Ed25519 signature as post-quantum.

## Current Titan evidence state

The Avrea contract smoke run and provider-inventory run are successful workflow executions. The provider inventory found `liboqs-python` and `pqcrypto` absent on the worker; `cryptography 41.0.7` was present but was not treated as a PQC provider. No known-answer tests or cryptographic operations ran. CACE verification has not run. The recorded evidence remains unsigned.

## Promotion gate

The adapter is not production-eligible until:
- CACE independently verifies exact source/run/artifact/tool bindings;
- a separately authorized signer signs the canonical statement;
- signature verification and key identity are independently checked;
- any PQC profile passes official test vectors and cross-implementation tests;
- CACE's existing mathematical proof/qualification gates pass independently;
- the authority-nonexpansion and rollback gates pass.

A valid signature authenticates the statement; it does not prove that the cryptographic construction is secure or that a research result is mathematically correct.


## Implementation progress (2026-11-05)

CACE implementation is isolated on `morganaspim/Cace-app`, branch
`feat/titan-mldsa-attestation-v2-20261105`:

- `schema/signed-attestation-v2-mldsa.schema.json`: additive ML-DSA-65 v2 envelope.
- `cace_studio/core/pqc_attestation.py`: canonical, domain-separated ML-DSA signing and verification; exact provenance binding checks; key-ID binding; key-pair consistency check.
- `cace_studio/attest_cli.py`: `pqc-keygen`, `pqc-sign`, and `pqc-verify` commands. Signing requires an artifact root and verifies the actual artifact bytes before signing.
- `scripts/verify_titan_bundle.py`: independent CACE bundle and artifact-byte verifier.
- Tests cover signature roundtrip, tampering, malformed public-key input, mismatched keypairs, CLI roundtrip, bundle integrity, and actual Avrea artifact reproduction.

The pinned Python binding is liboqs-python 0.16.0.2 at commit
`64c76ad0a80d6c69f2003219eb27b253782a3d68`. This patch release is selected
because upstream documents fixes for malformed short-key handling affecting
ML-DSA verification and ML-KEM decapsulation. Its commit is GitHub-verified;
the tag itself is lightweight, not signed.

The Avrea ACVP workflow passed the selected FIPS 203/204/205 parameter-set
tests. CACE's separate OCI runner `cace-oci-a1` passed independent verification
of the latest Avrea artifact archive (run `42090360334`) and its extracted log,
JUnit report, provider provenance, and evidence manifest. The CACE verification run is
`42090006059`; its verification artifact is retained for 30 days.

The ML-DSA v2 receipt implementation is present. The CACE OCI provider installation succeeded in run `42092942992` and the CLI signer/verifier emitted a valid result, but the test harness initially failed to parse stdout because liboqs-python prints an informational startup line. The code now redirects that line to stderr. Subsequent retries hit `No space left on device` on `cace-oci-a1` before a clean rerun; the final ML-DSA receipt test is therefore not yet green. Until that workflow
passes and an authorized production key is provisioned, the profile remains
implemented-but-unqualified and no production signed receipt is claimed.
