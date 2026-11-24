# Read-only review of a staged security rotation

Parent source: `bba73dbede1dea3beb71a5fc0f78ade66f381b8c`, draft PR #228.
The parent full-capacity recovery and rotation results are recorded in
`SECURITY_RECOVERY_WORKLOAD_20261123.md`. This change builds on the reviewed
rotation; it does not advance a staged successor into an active writer.

## Observable target and acceptance

After a verified predecessor archive and successor genesis have been staged
and separately reviewed, an operator must be able to see the predecessor's
incident history and unresolved alerts beside the successor without copying
events into a new ledger or confusing their revision numbers. Previously the
portable Studio summary represented only one ledger.

`wilborn_ops.security_segments.inspect_staged_segments` verifies the existing
rotation before and after collecting complete verified snapshots. It binds
the source identities, predecessor checkpoint and untouched successor genesis
to the reviewed continuity record. It returns two ordered segment summaries
and at most 20 incident summaries in total. A shorter display window never
reduces verification of the complete retained history.

`wilborn_ops.security_dashboard.studio_segment_snapshot` calls that verifier
directly and exports `merlin-studio-security-summary/2`. It removes ledger
identities, checkpoint hashes, signatures, signer identities, keys, timestamps
and raw payloads. Each retained incident has a segment index and its original
segment-local revision. The v1 single-ledger export remains supported.

Acceptance includes exact predecessor counts and pending alerts, zero events
in the successor, original source/archive bytes preserved, rejection of
tampered archives and continuity records, expired anchors, changed source or
successor, mismatched roles and observed changes during inspection. Studio
must reject reordered or inconsistent summaries, unknown fields and categories,
invalid bounds and any promotion to real data or execution authority.

## Scope and remaining gates

This is a snapshot of **one staged transition**: predecessor archive plus an
untouched successor genesis. It is not an arbitrary active historical chain,
an automatic rollover, a writer lease or proof of independent operational
custody. The host must quiesce writers; before/after comparisons detect
observed changes but cannot establish an atomic cross-ledger lease.

Studio checks the imported summary's structure and displays the host's claims.
It does not verify the original signatures or independently authenticate the
snapshot's source. Pending predecessor alerts remain attached to their
segment. No alert is implicitly acknowledged by staging or viewing a rotation.
Activation, execution and production qualification remain false.

The next implementation gate is a single-writer transition with durable
ownership and restart/recovery evidence. Independently administered Titan
keys and current anchors, the isolated OCI monitoring profile, private-host
authentication and deployment qualification remain open.

## Method and interpretation

Measured evidence uses synthetic event fixtures and real local cryptographic
operations. Deterministic summaries and matching hashes establish the tested
contract, not real-world security effectiveness. Tests challenge missing and
altered evidence as well as the happy path to avoid treating a green prior CI
run as evidence for new source. N-ality keeps segment identity, revision,
pending state, historical evidence and writer authority separate. Simplex,
continuum and fuzzy logic are not applicable to these exact integrity and
authorization decisions.
