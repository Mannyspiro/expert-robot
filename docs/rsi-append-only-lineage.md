# RSI append-only lineage

SQLite triggers reject UPDATE and DELETE for generations, evaluations, and promotion decisions. New rows represent new events. This increment does not provide a per-evaluation hash chain or authenticated CACE signatures. Repository-only; no OCI runner activity.


## Promotion readiness semantics

Promotion readiness uses the latest immutable evaluation record as one unit:
its keep recommendation, verification, efficiency, and diversity gates must
all pass together. Partial passes from separate evaluators are never combined
into a synthetic pass.

The latest explicit promotion decision also governs readiness. A later
rejection supersedes an earlier approval while preserving both records in the
append-only history.
