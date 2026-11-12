# Merlin artifact registry and local runtime contract

## Purpose

The artifact registry is the first canonical provenance layer shared by the Expert Robot research engine and the Merlin agent runtime. It gives every output a stable identifier and binds its metadata to a SHA-256 content digest.

The registry stores metadata and verification receipts. It does not store artifact bytes or fetch the locator.

## Persistent model

### Artifacts

Each artifact record contains:
- Stable artifact_id.
- Typed artifact_type and media_type.
- Lowercase SHA-256 content_sha256 and size_bytes.
- Storage locator.
- Optional source repository and commit, supplied together.
- Producer identity and version.
- Provenance JSON and creation timestamp.

Artifact records are insert-only. SQLite triggers reject update and delete operations.

### Verification receipts

A receipt binds the receipt ID and artifact ID, verifier identity and version, verified/rejected verdict, exact artifact SHA-256, evidence JSON, global sequence, previous receipt hash and receipt hash.

The receipt chain is append-only. verify_chain recomputes each receipt hash, checks contiguous sequence numbers, verifies previous-hash links and checks that each receipt digest still matches its artifact record.

## Local NDJSON operations

The runtime accepts one JSON request per line. payload is itself a JSON string, so clients must JSON-escape the payload when constructing the outer request.

Operations use role = artifact:

| task | Purpose |
|---|---|
| register | Register immutable artifact metadata |
| get | Retrieve one artifact and its latest receipt |
| list | List artifacts with bounded limit and offset |
| record_receipt | Append a previously verified receipt |
| receipts | Retrieve the receipt history for one artifact |
| verify_chain | Verify the global receipt hash chain |

Example request shape:

```json
{
  "id": "artifact-001",
  "role": "artifact",
  "task": "get",
  "payload": "{\"artifact_id\":\"artifact-0001\"}"
}
```

The response envelope contains id, ok, result and error. result is a JSON-encoded string; clients should parse the outer envelope and then parse result when it contains a structured value.

The runtime is a local stdin/stdout process. It is not a public HTTP endpoint. MERLIN_ARTIFACT_DB selects the SQLite path; otherwise the default is state/merlin/artifacts.sqlite3.

## Trust boundary

The registry does not read artifact bytes from locator, independently compute the digest of referenced content, authenticate the caller, or authenticate the verifier. A caller-supplied verifier_id is attribution, not proof of independent verification.

A production CACE adapter must retrieve or receive the exact artifact bytes, independently recompute the digest, authenticate the CACE result/receipt and only then call record_receipt. The receipt chain protects the stored sequence from undetected in-database alteration; it does not replace CACE authentication or an external trust anchor.

## Merlin integration

1. Hermes: attach artifact IDs and digest references to job envelopes and outbox acknowledgements.
2. CACE: independently verify artifact bytes and authenticate the returned receipt before recording it.
3. Knowledge graph: link claims, theorems, experiments and agent decisions to artifact IDs.
4. MCFC: workers return bounded result locators, digests and execution metadata; the registry indexes them without copying large files into SQLite.
5. HUD: query artifacts and receipts through an authenticated gateway; never expose the SQLite file directly to a browser.

## Next implementation priorities

1. Add authenticated CACE transport and receipt verification.
2. Persist the capability registry and expose capability health/qualification state.
3. Link knowledge-graph nodes and Hermes outbox events to artifact IDs.
4. Add idempotency keys, worker leases and resource-budget receipts.
5. Build the authenticated Merlin API gateway and research HUD on top of these contracts.
