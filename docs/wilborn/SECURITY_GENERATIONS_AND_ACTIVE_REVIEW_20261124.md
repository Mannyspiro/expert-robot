# Repeated security handover, current custody and active review

This checkpoint extends producer `298f53862a9757147c8f9490c21688ff508e81fe`
(draft PR #228) and the compatible Studio work based on
`370726c22e35f12746225367bad23fae70304eab` (draft PR #229).
The implementation and workload use synthetic data, real cryptographic
operations and actual local SQLite/process execution. They do not qualify
production custody or authorize a deployment.

## Initial frame and acceptance

The preceding checkpoint enforced one local writer transfer. Its active
successor could not become a predecessor in another transfer, and an open
writer retained the anchor receipt supplied when it opened. Those limitations
prevent sustained operation across successive capacity limits and leave a
running object unaware of a subsequently retained rollback anchor.

The acceptance target is a bounded, fully inspectable lineage in which only
the latest reviewed successor can write. Earlier ownership grants, enrollment,
history, archives and unresolved alerts must remain intact. Every managed
mutation must read the current retained anchor before reaching its signer.
Recovery and review must verify all ancestors, including history outside the
portable display window. A rejected continuation must never retire the last
usable owner merely because it exceeds the declared bound.

Falsifiers include two accepted child branches, revival of a retired owner,
loss or alteration of predecessor incidents, a rollback accepted by an open
writer after a newer anchor was retained, incomplete ancestry accepted as a
complete review, or a coordinator write into retained evidence directories.

## Repeated transfer protocol

`WriterHandover(..., previous=previous_handover)` extends the exact preceding
successor. The host supplies the complete configured ancestry. The child
binds the preceding coordinator identity, path, configuration, signed plan,
epoch and owner. It also binds the exact predecessor/successor custody
directories and configurations. A new archive review, rotation review and
separate handover grant are required for every transfer.

The declared policy is **seven transfers and eight ledger segments**. All
ledger IDs, file paths, encryption key IDs and encryption key values must be
distinct across the complete lineage. Coordinator identities/paths must not
repeat; cycles, omitted ancestors and reordered ancestry fail closed. The
ninth segment is rejected before its coordinator is created or the current
owner is retired. This is a finite policy bound, not indefinite rollover.

| Phase | Meaning and permitted next step |
| --- | --- |
| `preparing` | The new successor is frozen. The exact previous owner and reviewed predecessor tip are checked under ancestor-to-descendant locks. |
| Parent `retired` | The previous coordinator durably records the exact next coordinator and plan, frozen successor tip and unresolved alerts. Its original enrollment and signed grant stay unchanged. |
| Child `ready` | A second transaction verifies the committed retirement and complete retained evidence. Both sides remain fenced while awaiting the separate fresh handover grant. |
| Child `active` | Only the child successor with the current ownership token can mutate its ledger. Explicit restart advances the epoch by compare-and-swap. |

Retirement is permanent in this protocol. A retired coordinator cannot be
prepared, reactivated, used to acquire a new epoch or opened as a writer.
It remains available for historical verification. A previous successor keeps
its original enrollment pointing to the original coordinator; retiring that
coordinator fences all its old objects without rewriting enrollment.

The two preparation transactions deliberately place a durable boundary
between parent retirement and child readiness. If a process exits at that
boundary, both writers remain closed. A retry of the exact child intent can
continue. Another child cannot replace the retained retirement destination.
All multi-coordinator operations acquire locks from oldest to newest. The
signed rotation statement still cannot substitute for the separate handover
grant, and no fixture grant authorizes production execution.

## Current retained anchor on every managed mutation

An opened writer carries a host-configured `AnchorCustody` provider in addition
to its ownership token. Its signed plan binds that provider's canonical
directory and configuration. Every event ingestion, local observation and
operator review then holds locks in this order:

1. Current coordinator: verify the active phase, owner and epoch.
2. Configured custody: reread and verify the current retained signed receipt.
3. Ledger: verify its chain against that receipt and commit the mutation.

The first two locks remain held through ledger commit. A stale or retired
token, missing provider, relocated custody copy, expired receipt or ledger
restored behind a newly retained anchor is rejected before the signing
callback. An already-open object observes an explicit custody renewal on its
next write. Concurrent receipt retention waits for the current write to finish.

This does not create an external anchor for every event. The current retained
anchor may lag an active ledger's tip; rollback detection covers the retained
anchor and its chain binding. Frozen historical segments require exact-tip
anchors. Independently administered retention and protection against restoring
the coordinator, custody and ledger together remain operational requirements.

### Earlier grants without custody-directory bindings

Earlier signed plans remain historically inspectable; the software does not
rewrite a signed plan to pretend it contained the new bindings. Opening or
using a live writer under an unbound grant fails closed. The tested migration
route creates a separately reviewed continuation into a fresh successor with
the required custody bindings. It preserves the original historical grant and
enrollment. Hosts must arrange this review before expecting an earlier grant
to resume writes under the new executable.

An earlier coordinator can still report its retained historical phase as
`active` while live writer opening is blocked by the missing binding. That
historical status does not bypass the new write boundary.

## Complete host review and minimized Studio export

`WriterHandover.lineage_snapshot()` accepts only the latest active coordinator
with its complete ancestry. Under the coordinator locks it verifies retained
grants, exact retirement destinations, enrollment, rotation-proof identities,
current custody, every frozen predecessor and archive, and every successor
chain back to its reviewed genesis. A retired prefix cannot stand in for the
latest complete lineage.

Recovery and active-lineage review require current, available custody for
the retained segments as well as the latest segment. Historical archive
inspection does not remove this dependency; expired or unavailable retained
custody must be restored or explicitly renewed before those operations resume.

`inspect_active_lineage()` additionally checks the full ordered history of
every segment: dense revisions, event sequences, review counts, category
totals and final state hashes. These checks run even when `history_limit=0`.
Only after verification does it select up to 20 recent display entries.
Acknowledging a new segment's alert does not clear an archived segment's alert.

`studio_lineage_snapshot()` emits `merlin-studio-security-summary/3`:

| Field group | Portable contract |
| --- | --- |
| Scope | `environment=demo`, `data_class=synthetic`, `review_scope=active_lineage`. |
| Authority | `activation_authorized`, `execution_authorized` and `production_qualified` are false. `writer_handover_verified=true` is the exporting host's assertion. |
| Ownership | Positive bounded `ownership_epoch`; `active_segment_index` equals the final index. No owner or coordinator identity. |
| Segments | Two through eight densely ordered segments; earlier roles are `archived_predecessor`, and only the last is `active_successor`. |
| Counts | Aggregate counts, event/review totals and pending alerts exactly equal the segment totals. |
| Anchors | Every historical anchor equals its segment tip. The active retained anchor may lag the live tip. |
| Recent history | Exact suffix of up to 20 entries with segment-local revisions and bounded event categories. |
| Exclusions | No keys, signatures, private IDs, paths, raw payloads, state hashes or timestamps. |

Studio preserves v1 and staged-v2 support and strictly validates v3 before
display. It describes the file as an imported synthetic snapshot and its
verification as host-reported. It independently validates the portable shape
and consistency; it does not independently authenticate the ledger, signature,
custody or current writer from the JSON. No mutation controls are added.

## Evidence and a reproduced defect

Final local producer validation: **186 Wilborn tests passed in 21.785 seconds**,
plus **8 canonical CACE verifier tests in 0.005 seconds**. Syntax and whitespace
checks passed. The 186 include six generation tests, 13 new adversarial tests
and ten active-lineage tests; targeted runs are not added again to the total.
The new adversarial tests execute seven actual child processes in addition to
the preceding handover suite's process tests.

The discriminating cases include competing child branches; parent restart
racing child preparation; actual process exit after durable retirement;
stale tokens through event and review paths; an already-open object facing a
new rollback anchor; explicit receipt renewal; receipt-retention lock ordering;
copied or absent custody providers; nonadjacent ledger/key reuse; missing or
reordered ancestry; earliest proof corruption; and all-history verification
behind a truncated display. A usable eighth segment and its actual v3 export
are tested before the ninth-segment attempt is rejected.

A failing reproduction found that a child coordinator could use an ancestor
archive's directory: the earlier check covered only the immediate pair. That
created a control database inside sealed evidence. The repair checks every
configured coordinator against the complete lineage's archive, stage, source
and custody directories before creating its database. The regression and
sibling cases for the ancestor ledger and custody directories now reject the
operation without changing their bytes. The original failure is retained in
the parent-linked plan record.

The local full-capacity workload produced schema v3 with **three segments,
1,023 / 2 / 2 events, 1,027 total, active index two and final epoch two**.
It preserved the oldest complete history/archive and pending alerts, rejected
the retired middle writer and returned 20 recent incidents only after complete
verification. Measured first handover/reopen was 5.054304 seconds; second
transfer/reopen/export was 5.720841 seconds on Linux x86_64, Python 3.12.14,
SQLite 3.53.1 and cryptography 50.0.0. These are one-host measurements, not
latency promises. Only the first segment was filled to capacity; later fixture
rotation thresholds were deliberately smaller.

That workload completed before the final directory-collision guard was added.
The final full unit suite covers that repair. Exact published-candidate CI must
run the full workload again before its result is attributed to the publication.
The 210-second ingestion, 230-second overall internal and 240-second external
limits remain unchanged. The workload itself does not terminate processes;
abrupt-process evidence comes from the separate tests.

One local verification invocation used the broader `test_cace*.py` pattern and
also selected the unrelated adapter test without its `merlin` import path.
That command reported an import error. The workflow's actual canonical
`test_cace_attestation.py` invocation then ran all eight required tests and
passed; no source or dependency was changed to suppress the discovery error.

## Actual OCI availability and remaining acceptance

The existing fixed read-only inventory operation completed successfully in
[run 45392435551](https://github.com/morganaspim/Cace-app/actions/runs/45392435551).
The matching job establishes assignment and execution at that time. The
original receipt and inventory artifact were checked and retained separately
from the public source; detailed operational payloads are not included here.

The receipt explicitly reports `qualification=false`. This observation does
not establish continuous availability, effective workload isolation, exact
runtime compatibility or Wilborn monitoring qualification. No gateway profile
was added and no monitoring job was dispatched. Revised acceptance targets
are recorded in `OCI_SECURITY_MONITORING_PROFILE_PROPOSAL_20261124.md`.

The remaining operational gates are:

- A reviewed, fixed, isolated OCI monitoring wrapper, immutable source/package
  and runtime identities, installation authority and an actual acceptance run.
- Independently administered Titan keys, signer/operator roles and current
  anchor custody, with a rollback-resistant ownership recovery policy.
- Authenticated private-host operation and measured restore/interruption
  behavior under the deployed filesystem, process ownership and backup policy.
- The complete source/artifact-bound independent release statements and the
  separately authorized release decision.

The existing 18-statement release gate remains unchanged. Repeated handover
strengthens the evidence required for `durable_writer_handover`; it does not
invent another gate or promote synthetic receipts into operational proof.
Whole-control rollback, compromised administrators/raw SQL, pre-enrollment
copies or obsolete executables, distributed writers and physical power loss
remain outside this experiment's evidence.

## Method and continuity

Canonical traceability remains master plan v6
`MERLIN-PRODUCTION-MASTER-20261117`, tasks `P00-3`, `P00-4`, `P02-3`,
`P04-3` and `P04-4`. The new plan update is a child of the preceding handover
checkpoint; no historical measurement or failed attempt is replaced.

N-ality separates segment identity, incident revision, ownership epoch,
evidence/custody and production authority. A new owner or segment must not
rewrite history or confer deployment authority. Simplex, continuum and fuzzy
lenses are not applicable to these discrete integrity and authorization gates.
The adversarial cases distinguish real durable continuation from replayed
objects, incomplete ancestry, stale anchors and a surviving alternate branch.
Local tests, the OCI inventory and eventual exact-candidate CI each retain
their own scope; none substitutes for independent operational qualification.
