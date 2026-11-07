# Merlin authenticated outbox worker API

**Status:** implemented and hosted-tested; no production worker credentials or continuously running Hermes service are configured.

## Purpose

This API exposes Merlin's durable SQLite outbox to separately operated workers. It provides authenticated claim, heartbeat, acknowledgement, retry and status operations. Delivery is at-least-once; handlers must be idempotent. The API does not execute shell commands, create arbitrary tool permissions, or expand worker authority.

## Worker credentials

Set `MERLIN_WORKER_TOKENS` in the trusted server environment to a JSON object mapping stable worker IDs to independent high-entropy tokens. Example shape (replace both placeholders with randomly generated values):

```json
{
  "hermes": "<at-least-48-character-random-ASCII-token>",
  "mcfc": "<different-at-least-48-character-random-ASCII-token>"
}
```

Generate tokens with a cryptographically secure generator such as `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Never commit real tokens, include them in a browser bundle, or place them in task payloads. Rotate by updating the server environment and restarting the service. A missing, malformed or empty map denies all worker requests. Set a separate `MERLIN_OUTBOX_ADMIN_TOKEN` to an independent high-entropy ASCII token (at least 32 characters) for administrative cancellation; do not reuse a worker token.

Every request supplies both:

- `X-Merlin-Worker-ID: hermes`
- `Authorization: Bearer <worker-specific-token>`

The worker ID is bound to the token by a constant-time comparison. A token for one worker cannot claim or acknowledge a lease under another worker's identity.

## Endpoints

All writes are JSON POST requests. The service is loopback-bound by default. A production network deployment must terminate authenticated HTTPS at a trusted gateway and must not expose the loopback process directly.

| Method and path | Purpose |
|---|---|
| `GET /api/internal/outbox/status` | Authenticated worker identity and state counts only |
| `POST /api/internal/outbox/claim` | Claim one available event; optional `topics` list and `lease_seconds` |
| `POST /api/internal/outbox/heartbeat` | Extend the active lease |
| `POST /api/internal/outbox/acknowledge` | Acknowledge with an optional JSON result |
| `POST /api/internal/outbox/retry` | Release the lease and retry or quarantine after the attempt limit |
| `POST /api/internal/outbox/cancel` | Administrative cancellation using the separate admin bearer token |

Administrative cancellation is authenticated only by `MERLIN_OUTBOX_ADMIN_TOKEN` and records the actor as `merlin-admin`; worker credentials cannot cancel tasks. Claim response includes the lease token only for the authenticated worker. Heartbeat, acknowledgement and retry require the exact event ID, worker-bound lease and active lease token. Stale, expired or cross-worker leases return HTTP 409. Missing worker credentials return 401. A missing outbox returns 503.

## Operational semantics

- Queue delivery is at-least-once, not exactly-once. A worker must make external side effects idempotent using the event ID/idempotency key.
- A worker should heartbeat before its lease expires while work is active.
- If a worker crashes, an expired lease can be recovered and the event redelivered.
- Failed attempts return to pending or move to quarantine after the configured maximum.
- The API persists state in the configured SQLite outbox. SQLite is suitable for the current single-host MVP; multi-host workers require a shared, production-grade database and coordinated lease semantics.
- Lifecycle events are recorded in the local metadata event ledger. Bearer tokens and lease tokens are not written to that ledger.
- The existing cooperative cancellation state invalidates a lease. An external process must poll/check its lease and terminate itself; this API does not forcibly kill a remote process. An authenticated administrative cancellation endpoint is not yet implemented.

## Hosted evidence

- The first worker API run, [42268148088](https://github.com/Mannyspiro/expert-robot/actions/runs/42268148088), compiled but failed 6 worker API tests while 88 existing tests passed. The root cause was duplicate Python module identity: `hermes_outbox.py` imported `merlin.event_outbox` absolutely while the application loaded `python.merlin.event_outbox`. Python therefore saw two distinct class objects.
- Corrected to a package-relative import and added the new module to the unified workflow.
- Exact passing head `89b19250ef99b2277694eb1dc0d48070a790aae8`: [run 42268417875](https://github.com/Mannyspiro/expert-robot/actions/runs/42268417875) compiled and passed **94 tests in 8.30 seconds**.
- Evidence artifact [13528675991](https://github.com/Mannyspiro/expert-robot/actions/runs/42268417875/artifacts/13528675991), SHA-256 `a57d74ec67e89135fede3196e4ed98ff0e2e789abf3b1febc8548654d8560858`.
- Tests use temporary local SQLite databases and generated test credentials; they do not establish a production deployment, multi-host durability, or live worker identity infrastructure.

## Still required for production

1. Configure per-worker secrets through a managed secret store.
2. Deploy behind authenticated HTTPS with network policy, rate limits and audit export.
3. Move to a shared database if workers run across multiple hosts.
4. Implement and operate a long-running Hermes worker supervisor with bounded concurrency, resource budgets, deadline handling, graceful shutdown and process cancellation.
5. Connect Avrea and OCI as independently qualified execution adapters; require exact source/artifact/toolchain/environment binding in returned results.
6. Verify worker outputs independently through a real CACE verifier service before any proof or capability qualification.
7. Run fault-injection tests for process crashes, database restarts, lease expiry during execution, duplicate delivery, provider timeouts and partial results.
