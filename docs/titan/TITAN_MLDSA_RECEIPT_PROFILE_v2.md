# Titan ML-DSA Receipt Profile v2

**Status:** protocol specification; implementation and conformance pending.

## Purpose

Define a post-quantum signature profile for CACE provenance statements without silently changing the existing CACE v1 Ed25519 format.

## Profile

- Envelope schema: `cace-signed-attestation-v2`
- Statement schema: `cace-attestation-statement-v2`
- Signature algorithm: `ML-DSA-65` (FIPS 204)
- Standard: NIST FIPS 204, subject to current errata
- Canonical encoding: UTF-8 canonical JSON with an explicit versioned canonicalization identifier
- Domain separator: `CACE:TITAN:SIGNED-ATTESTATION:v2\0`
- Key ID: `ml-dsa-65:` plus SHA-256 of the exact canonical public-key byte string
- Proof effect: `none`

## Signed statement bindings

The signed bytes bind the complete canonical statement, including:
- verifier identity and key ID;
- claim ID and evidence bundle SHA-256;
- exact source repository and commit;
- workflow run ID and attempt;
- workflow file path and commit;
- runner identity and environment digest;
- provider repository, release and exact commit;
- official ACVP vector repository, tag, commit and test suite digest;
- exact toolchain and command manifest digests;
- CACE verifier repository, commit, toolchain and verification result;
- scope, limitations, timestamp and explicit nonclaims.

## Verification

The verifier must:
1. validate the v2 schema with unknown fields rejected;
2. recompute the canonical statement bytes and bundle digest;
3. verify the public-key-derived key ID;
4. verify the ML-DSA-65 signature using a vetted FIPS 204 implementation;
5. verify the exact evidence and source bindings independently;
6. record key trust, revocation and verifier identity decisions separately from signature validity.

## Key custody

Private signing keys must not be stored in GitHub source, workflow artifacts, logs, or the evidence bundle. Signing must occur in an explicitly authorized key-custody boundary. A valid signature proves possession of the signing key for the exact statement; it does not prove cryptographic security, FIPS 140 validation, mathematical correctness, or reviewer independence.

## Migration

CACE v1 remains Ed25519 and remains verifiable. V2 is additive and must not reinterpret v1 envelopes. During migration, a record may carry both signatures, but each signature must cover the same canonical claim and bundle identity under its own versioned domain separator.
