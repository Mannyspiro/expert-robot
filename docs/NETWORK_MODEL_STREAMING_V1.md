# Merlin network inference and streamed intelligence v1

Date: 2026-11-02

## Decision

Merlin is a network-native orchestrator. Model weights remain on provider or worker infrastructure; Merlin streams request/response data and generated artifacts. It does not download model weights per request.

The first implementation is an OpenAI-compatible HTTPS gateway in \`POST /api/chat\`:
- Remote endpoint, API key, allowed hosts and qualification flag are supplied only through process environment.
- HTTPS is mandatory; the hostname must exactly match an explicit allowlist.
- The bearer key is never returned from capability/status APIs or written to event summaries.
- \`stream: true\` passes through upstream Server-Sent Events incrementally, flushing chunks without buffering the full answer.
- Non-streaming JSON remains supported.
- Local llama.cpp remains a separately gated option.
- The server continues to bind to loopback by default.

## Environment

\`\`\`bash
export MERLIN_REMOTE_MODEL_URL="https://YOUR-APPROVED-PROVIDER.example/v1/chat/completions"
export MERLIN_REMOTE_API_KEY="read-from-your-secret-manager"
export MERLIN_REMOTE_ALLOWED_HOSTS="YOUR-APPROVED-PROVIDER.example"
export MERLIN_REMOTE_MODEL_QUALIFIED="1"
\`\`\`

Do not commit actual keys, tokens, private endpoints, or customer prompts. Do not set the qualification flag until the selected provider/model has passed a small correctness and latency check. Provider access, terms, retention and data-use settings must be reviewed before sending confidential material.

## Example streaming request

\`\`\`json
{
  "model": "provider-model-id",
  "messages": [
    {"role": "user", "content": "Explain this design and identify assumptions."}
  ],
  "stream": true
}
\`\`\`

The response is upstream SSE. Clients should render text deltas as they arrive, parse the terminal usage event when available, support cancellation, and display a partial-answer state if the connection ends early.

## Performance strategy

1. Measure time-to-first-token (TTFT), tokens/second, end-to-end latency, error rate and cost per successful task.
2. Keep a persistent HTTPS connection pool in the production async gateway; this initial standard-library MVP uses urllib and should be replaced by a tested async HTTP client before high concurrency.
3. Route small/simple tasks to fast models; coding to a coding specialist; deep research to a reasoning model; image/video to modality-capable providers.
4. Run council seats concurrently only when they provide independent value; stream the lead answer first and attach dissent/review as later events.
5. Cache only deterministic, non-sensitive results with explicit TTL and content hashes. Never cache private prompts by default.
6. Keep local Avrea/OCI workers for private jobs, long-running tests, indexing, simulation, and fallback when explicitly authorized.
7. Avoid automatically sending private data to a different provider on fallback. Provider selection is an explicit trust-boundary decision.

## Next implementation gates

- Add an asynchronous gateway with connection pooling, cancellation, request deadlines, bounded concurrency and per-provider circuit breakers.
- Add a provider registry and task-role router with model IDs, capabilities, pricing metadata, context limits, streaming support and qualification receipts.
- Add provider health probes and latency/cost telemetry without recording prompt text or credentials.
- Add a client-side streaming parser, reconnect policy and partial-output handling.
- Add council fan-out/fan-in, Kokoro chunked speech, and audio playback queue.
- Benchmark at least three task classes using the same held-out prompts before changing defaults.
- Add explicit user consent and data-classification rules for external inference.

## Acceptance criteria

- A test provider emits at least three SSE chunks; Merlin forwards each chunk before upstream completion.
- Remote endpoint rejects HTTP, credentials embedded in URLs, unlisted hosts and missing secrets.
- Non-stream JSON proxy still passes.
- Tests prove API keys are absent from capability responses, event summaries and logs.
- Client cancellation closes upstream work.
- Measured TTFT and throughput are reported separately; no claim of "fastest" without comparative benchmark.
- Local model route remains gated by its own qualification flag.

## Limits

This gateway is not itself an AI model, does not guarantee provider uptime, and does not make an unqualified model safe or correct. The initial implementation is a low-concurrency MVP; use a production async gateway before scaling to many simultaneous sessions.
