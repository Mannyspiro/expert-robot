# Merlin Hermes Durable Delivery Foundation

Date: 2026-11-06

## Scope

This change adds a SQLite-backed task outbox and result inbox to the existing
Merlin runtime registry. It is a single-node persistence foundation, not a
distributed broker or a production worker deployment.

## Delivery contract

- `publish_task` commits the `tool.requested` run event and outbox row in the
  same SQLite transaction.
- A stable idempotency key returns the original task on an exact replay and
  rejects reuse with a different payload or run.
- `claim` atomically leases ready work and returns a random fencing token.
  Expired leases can be reclaimed; stale workers cannot acknowledge a task.
- `acknowledge` commits the inbox receipt, outbox acknowledgement, and
  `tool.completed` event in one transaction.
- Replayed result messages with the same key and digest return duplicate;
  conflicting content under the same key is rejected.
- `retry` uses a caller-supplied delay and dead-letters at the configured
  attempt limit. `cancel` clears lease ownership and prevents future claims.

## Trust boundaries

A transport acknowledgement only says that Merlin durably received a worker
message. It does not prove that an artifact is correct, that a Lean proof
compiled, that a numerical result is reproducible, or that CACE independently
verified evidence. It also does not authorize external side effects. Those
remain separate CACE verification and exact-action human approval gates.

## Remaining production work

1. Add lease renewal and explicit operator requeue/dead-letter inspection.
2. Add deterministic retry policy with capped exponential backoff and jitter.
3. Add concurrency and crash/restart integration tests against a real worker.
4. Move from single-process SQLite claims to a server database with fencing
   semantics before running multiple independent schedulers.
5. Define authenticated Avrea and OCI worker adapters, signed result envelopes,
   artifact storage references, and CACE verification receipts.
6. Add metrics for queue depth, oldest pending age, lease expiry, retry rate,
   dead letters, acknowledgement latency, and result verification lag.

## CI evidence

The Hermes lifecycle tests are imported by the existing
`test_sqlite_registry.py` test entrypoint so the current CI job executes them
without silently skipping a newly added suite. Per-suite logs and result JSON
continue to be retained by the existing artifact upload step.
