# Failure observations for RSI induction

## Event contract

Research failures are appended to the existing per-episode hash-chained
`ResearchEpisodeLedger` using event type `failure_observation.v1`.

The payload contains:

- `source_agent`: producer identity, such as the local research engine or Hermes
- `source_task_id`: stable task/run identifier
- `stage`: direct proof, parent retry, or an external stage
- `failure_class`: normalized failure category
- `target_sha256`: digest of the exact target statement
- `diagnostic_sha256`: digest of deterministic attempt metadata and diagnostics
- `attempt_count`: number of proof attempts observed

The local research engine now emits records for failed direct proof searches
and failed parent retries. Tactic and diagnostic text are hashed rather than
copied into the observation envelope.

## Hermes integration seam

An external Hermes adapter can use
`ResearchEpisodeLedger::append_failure_observation` to add its task failures
to the same event chain. It must preserve the source task ID and identify its
own source agent. The event is then ordered with the rest of the episode and
covered by the ledger's payload and event hashes.

This is an ingestion contract, not a completed cross-repository Hermes
connection. The external Hermes endpoint/transport and authenticated receipt
verification still need to be connected.

## Immutability and verification

SQLite triggers reject UPDATE and DELETE on episode events. The event hash
chain independently detects payload tampering if a database administrator
removes the trigger and edits a row. This is tamper-evident local persistence,
not a claim of protection against replacement of the entire database file.

## OCI safety

No OCI runner dispatch, filesystem operation, installation, cache mutation,
or deployment is required for this repository change.
