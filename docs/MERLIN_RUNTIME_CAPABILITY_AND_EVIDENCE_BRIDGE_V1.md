# Merlin runtime capability and evidence bridge v1

Status: implementation proposal on an isolated draft branch. No provider is qualified by configuration alone. No code path in this package grants execution, promotion, deployment, or CACE proof authority.

## Contracts

- `RuntimeCapabilityRegistry` distinguishes `unavailable`, `configured`, `unqualified`, and `qualified`.
- Qualification binds a receipt to the exact provider, model, revision, artifact digest, held-out task/seed identifiers, evaluator revision, and privacy-policy digest.
- `AsyncStreamingGateway` applies one wall-clock deadline including semaphore wait and stream reads; enforces concurrency, chunk, and total-response limits; propagates task cancellation and closes the upstream iterator.
- Streaming timing is emitted to the optional callback as chunks are delivered. The caller owns durable telemetry storage.
- `paired_heldout_comparison` runs candidates on identical held-out seeds in randomized order and reports paired metric deltas. It does not claim statistical significance or authorize promotion.
- `select_measured_route` is a deterministic advisory selector; it only selects a candidate with positive paired quality delta and non-worse latency.
- `make_cace_evidence_envelope` binds evidence to repository/revision/path/digest and hashes canonical evidence. The `verified` field is a statement from the named verifier, not a cryptographic proof of that verifier's identity.

## Required integration before production

1. Wire the registry to the real environment/config loader; absent endpoints become unavailable, configured endpoints remain unqualified.
2. Replace the synchronous `urllib` chat relay with an async server/transport adapter. Do not run this async generator directly from the current synchronous `BaseHTTPRequestHandler` without a bounded event-loop bridge.
3. Add authentication, request quotas, disconnect propagation, content-type validation, SSE framing validation, retry policy, and per-provider circuit breaking at the HTTP adapter boundary.
4. Persist only metadata: provider/model/revision, byte counts, chunk timing, status, and evidence digests. Never persist prompts, completions, API keys, or raw audio by default.
5. Populate receipts only from an independently executed held-out harness. Record exact task/seed manifests and immutable evaluator revision. Privacy approval must be a real reviewed artifact.
6. Use CACE's own verifier and typed API to validate incoming envelopes. A digest proves integrity relative to supplied bytes, not truth, provenance, or reviewer identity.
7. Add property-based tests, stress tests, real disconnect tests, event-loop starvation checks, and integration tests on the supported runtime before promotion.

## Known limitations

The initial gateway returns chunks to its async consumer; it does not itself send HTTP headers or write to sockets. It does not implement authentication or provider URL policy. The initial qualification thresholds are caller-supplied. The paired evaluator assumes deterministic seed control and matching metric sets. The selector is a simple dominance filter, not a learned policy or confidence-bound optimizer. No independent CACE verification has occurred.

## Invariants

- Capability grows; authority never expands.
- Unavailable is not configured; configured is not qualified.
- Qualification is revision-specific and expires when the model, artifact, evaluator, privacy policy, or relevant runtime changes.
- Held-out evidence must not be reused for candidate tuning.
- Simulation and self-reported model claims are not qualification evidence.
- All outputs are advisory; `promotion_authorized=false`.
