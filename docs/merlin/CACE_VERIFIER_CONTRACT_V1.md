# Merlin ↔ CACE signed-verification contract v1

Status: **client-side validation and composition implemented; live CACE HTTP verifier not yet available or qualified**.

## Trust model

Merlin does not trust a `verifier_id` string, a receipt hash, or an embedded public key by itself. A verification receipt is accepted only when:

1. the receipt binds the exact repository, commit, artifact digest, theorem/artifact type and tool identity;
2. the nested CACE `cace-signed-attestation-v1` uses Ed25519 and `proof_effect: "none"`;
3. the statement digest and Ed25519 signature validate under the CACE v1 domain separator;
4. the embedded public key matches a pinned Merlin trust-store key ID;
5. the pinned key record also pins the expected `verifier_id`;
6. the attestation claim ID, bundle digest and required bindings exactly match the submitted request;
7. the receipt's canonical SHA-256 digest validates; and
8. the CACE-specific verification fields independently pass (source commit, artifact digest, kernel check, axiom audit, exact target declaration, or artifact schema/content checks).

A signed attestation is provenance metadata, not mathematical proof. It never grants promotion authority.

## Proof-verification request

Merlin sends `merlin-cace-verification-request/1` with:

- `repository`, `commit_sha`, `artifact_sha256`, `theorem`;
- `tool_version` (for example, the exact Lean toolchain);
- `requester_id`;
- the registry-rehashed artifact bytes as base64.

CACE returns `cace-independent-verification/1`, with matching subject fields, `verifier_id`, verification result and checks, `axiom_dependencies`, a nested `signed_attestation`, and `receipt_sha256`.

The signed statement must use:
- `claim_id = theorem`;
- `bundle_sha256 = artifact_sha256`;
- `purpose = independent-reproduction`;
- bindings for `repository`, `commit_sha`, `theorem`, and `tool_version`.

## Non-theorem artifact-verification request

Merlin sends `merlin-cace-artifact-verification-request/1` with the exact repository/commit/artifact digest, artifact kind/schema/path, requester, tool identity, and registry-rehashed bytes.

CACE returns `cace-artifact-verification/1`. The signed statement must use:
- `claim_id = "artifact:" + artifact_kind`;
- `bundle_sha256 = artifact_sha256`;
- `purpose = artifact-integrity`;
- bindings for repository, commit, artifact kind/schema/path and exact tool identity.

## Receipt hashing

The outer `receipt_sha256` is SHA-256 over canonical UTF-8 JSON of the entire receipt excluding only `receipt_sha256` itself. Canonical serialization is sorted keys, compact separators, UTF-8, and non-finite numbers rejected. The nested CACE signature uses the existing CACE profile:

- domain separator: `CACE:SIGNED-ATTESTATION:v1\0`;
- statement schema: `cace-attestation-statement-v1`;
- envelope schema: `cace-signed-attestation-v1`;
- Ed25519, with key ID `ed25519:<sha256(raw public key)>`.

## Merlin environment configuration

- `CACE_VERIFY_URL`: HTTPS endpoint for the external CACE verifier.
- `CACE_VERIFY_TOKEN`: high-entropy bearer credential; store in a secret manager.
- `CACE_VERIFY_TRUSTED_KEYS_JSON`: JSON object mapping key IDs to `{"verifier_id":"…","public_key_pem":"…"}` records.
- `CACE_VERIFY_TIMEOUT_SECONDS`: bounded request timeout.
- `CACE_VERIFY_MAX_REQUEST_BYTES`: default 36,000,000 bytes, compatible with the 25 MiB artifact limit after base64 encoding.
- `CACE_VERIFY_MAX_RESPONSE_BYTES`: bounded receipt response size.

The public trust keys are configuration, not secrets. CACE private signing keys remain exclusively on the CACE side and must not be copied into Merlin or committed to either repository.

If endpoint/token configuration is partial, or trusted signer configuration is absent/malformed, runtime composition fails closed. If all CACE configuration is absent, the adapter remains unavailable and artifacts may be recorded without claiming independent verification.

## Outstanding CACE-side work

The CACE repository contains the Ed25519 signed-attestation implementation and a pinned Lean qualification workflow. The currently inspected CACE FastAPI surface exposes graph execution and claim browsing, but does **not** expose the external Merlin verification endpoint described here. The OCI/Lean qualification workflow also has no successful run evidence on the inspected source commit. Therefore Merlin's signed-receipt client is tested against contract fixtures, not a live CACE service.

Production acceptance still requires:
1. a CACE-side HTTPS endpoint that executes the exact source/artifact checks on a qualified runner;
2. the endpoint to return receipts signed by the pinned CACE key, with exact commit/artifact/tool bindings;
3. a real round-trip from Hermes through CACE and back to Merlin;
4. CACE's own independent receipt verification and artifact retention; and
5. a successful, reproducible Lean/OCI execution with durable logs and artifacts.

No local test fixture or signature-only validation may be represented as independent proof verification.
