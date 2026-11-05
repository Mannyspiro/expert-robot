# Merlin durable event outbox v0.1

This SQLite outbox is the durable boundary for Hermes consumers and a later Avrea adapter.
It guarantees at-least-once delivery, not exactly-once execution; consumers must deduplicate
using the stable event ID and make side effects idempotent.

States are pending, leased, acknowledged and quarantined. Claims have an owner, opaque
lease token and expiry. A crash makes the event eligible for redelivery after expiry.
Failures may be retried with a delay; exhausting the retry limit quarantines the event.
Acknowledgement is explicit and terminal. Conflicting reuse of an idempotency key is rejected.

The outbox is intentionally separate from the Proof Observatory and Knowledge Graph
SQLite databases. It does not claim cross-database atomicity. A bridge should validate
source evidence, enqueue a deterministic operation, apply idempotent target mutations,
verify the resulting target state, then acknowledge. Restart recovery resumes from outbox
state. Avrea dispatch must additionally require operator approval and an MCFC LeaseBook
resource grant; this module does not start workers or expand authority.
