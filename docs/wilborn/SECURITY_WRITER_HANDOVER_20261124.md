# Durable local writer handover and restart

Parent producer: `e619f14b0ac0b1439065bb99a7ea41ae52c95f7f`, draft PR #228.
Parent Studio: `315fccb5bd3103b1400c07715d489e239818a4b9`, draft PR #229.
This checkpoint advances the next implementation requirement from
`SECURITY_SEGMENT_REVIEW_20261123.md`. It remains synthetic development work.

## Initial frame and acceptance

The parent can stage and review a predecessor archive and successor genesis,
but it relies on the host to stop writers. An object opened before staging
can still invoke the signed event or operator-review APIs. A wrapper around
the new writer would leave these older paths usable.

The observable target is one eligible ledger and one current ownership epoch
after a separately reviewed transfer. Test each public mutation, rejected
signer invocation, concurrent ownership claims, process interruption, exact
history retention and successor continuation. The baseline has no durable
enrollment or ownership state. On failure, access must remain closed,
never reopening predecessor writes because a process exits or a timer expires.

Assumptions are a trusted host administrator, protected original files,
working SQLite locks and synchronization on a local filesystem, separately
configured fixture roles and current signed custody receipts. These are
assumptions of the software experiment, not measurements of an OCI or private
production host. The new ownership token does not authenticate a person.

## Implementation

`wilborn_ops.security_handover.WriterHandover` implements one bounded transition:

| Durable state | Permitted behavior |
| --- | --- |
| `preparing` | An immutable intent is retained before enrollment. The successor is frozen first and the predecessor second. A retry repeats only the same enrollment. A changed reviewed tip leaves the operation closed. |
| `ready` | Both enrolled ledgers are frozen. The exact archive, current anchors, staged rotation, untouched successor and proof-file identities have been verified. A separate handover signature is still required. |
| `active` | The signed handover grant permits local synthetic successor writes with the current epoch and owner token. The predecessor remains frozen. |

The enrollment record is encrypted/authenticated with the ledger's existing
Titan demo envelope and bound to the ledger identity, canonical file path,
coordinator identity/path, role and host configuration digest. A durable
SQLite metadata version prevents a missing enrollment row or table from
falling back to an ordinary unenrolled write. A copied enrolled database
cannot write at another path. Existing unbound ledgers retain their prior API
behavior until explicitly enrolled.

`observe_local`, `ingest` and `acknowledge` check enrollment on every mutation,
including objects created before enrollment and duplicate event retries.
An enrolled writer acquires the coordinator transaction before the ledger
transaction, rereads current ownership and holds the coordinator lock until
the ledger commit completes. A stale writer fails before its signing callback.
Read-only ledger views do not reacquire the coordinator and cannot invert the
lock order.

The coordinator uses a private SQLite rollback-journal database with
`BEGIN IMMEDIATE` and `synchronous=EXTRA`. Ledger commits also use `EXTRA`.
SQLite documents that `IMMEDIATE` starts the write transaction immediately
and that `EXTRA` adds directory synchronization to rollback-journal deletion.
The implementation depends on actual filesystem locking and sync behavior;
using those settings is not a measurement of physical power-loss durability.
Sources: [transaction semantics](https://www.sqlite.org/lang_transaction.html),
[synchronous settings](https://www.sqlite.org/pragma.html#pragma_synchronous),
and [atomic commit assumptions](https://www.sqlite.org/atomiccommit.html).

The existing rotation review still has `activation_authorized=false`. It
cannot substitute for the new claim
`wilborn:security:local-writer-handover:v1`. The separate fresh handover
signature binds the exact plan, host configuration, successor, first epoch
and initial owner. Its purpose is local synthetic writes; production,
external execution and deployment fields stay false. Fixture signer
separation does not establish independent administration.

## Restart and preservation

`claim_writer(expected_epoch=..., owner_id=...)` is an explicit trusted-host
recovery action. It verifies the retained signed grant, both exact enrollments,
current custody, the frozen predecessor, its reviewed archive, the unchanged
rotation proof files and the successor's complete chain back to the reviewed
genesis. A compare-and-swap epoch update gives one concurrent claimant the
next epoch and fences all older tokens. There is no expiry-based automatic
takeover. The host-only method must not become a public endpoint accepting
an owner UUID as authentication.

Replaying the same activation signature returns the original epoch-one
token. It never upgrades an earlier owner to a later owner's token. Restart
does not invoke the old genesis-only staging inspector after successor events
exist. It verifies retained proof identities and the active successor chain.

Incident data stays in the signed encrypted ledger. The coordinator stores
ownership state, not a separately updated per-event high-water mark; this
avoids a second data commit that could disagree after a process crash between
the ledger and coordinator transaction exits. An event committed before a
crash remains present; an uncommitted event rolls back.

Enrollment adds control metadata to the original ledger files, so those file
bytes change. The encrypted predecessor incident history and logical report
remain unchanged, the separately reviewed archive retains its exact bytes,
and unresolved predecessor alerts remain attached to the predecessor. No
implicit review, deletion or alert clearance occurs.

## Evidence and defect prevention

The core and adversarial tests use real signatures, encrypted SQLite files
and local process isolation with synthetic identities/events. They cover:

- Old and newly opened raw objects rejected on every mutation; a signer is
  never invoked on a fenced call.
- Partial enrollment retried after both injected exceptions and actual
  `os._exit` process termination at each durable freeze boundary.
- Two process restart claims yielding exactly one winner; a claim waiting for
  an in-flight event to commit before advancing the epoch.
- Process exit before ledger commit rolling back the event, and process exit
  after ledger commit preserving it through explicit takeover.
- Wrong, expired, substituted or differently bound handover grants; stale
  tokens, missing/corrupt control state and enrollment metadata; copied paths.
- Missing/changed rotation proof files and damaged predecessor archives
  blocking recovery. Exact proof restoration permits retry without advancing
  the epoch on rejected attempts.
- Expired custody blocking restart until both current signed receipts are
  explicitly renewed.

The full-capacity workload also transfers a predecessor with 1,023 events at
revision 1,024, writes two successor events across a reopened ownership claim,
and rejects three stale objects. Its existing 230-second internal and
240-second external workload budgets are retained. Timing is a measurement
of the executing host, not a production SLA. The separate process tests,
not this workload, supply abrupt-process-termination evidence.

Review found that an ownership-only restart initially did not reread the
retained staged proof files. The repair pins their exact canonical hashes in
the authenticated handover plan and rechecks them on activation, reopening,
restart and status. Sibling regressions alter and remove each proof file.
This closes a concrete evidence-preservation gap without weakening the
genesis or custody requirements.

`ReleaseEvidenceGate` now requires a distinct `durable_writer_handover`
statement. A regression first demonstrated that the previous 17 statements
could omit this requirement, then confirmed the new 18-gate set blocks that
bundle. A signed fixture receipt is structural test evidence only; complete
receipts still cannot authorize deployment.

## Remaining production requirements

This is **one reviewed local transfer**, not indefinite automatic rollover.
The successor cannot yet enroll in another coordinator for a third generation.
That attempt fails closed. A reviewed multi-generation protocol and tests are
required before sustained operation across successive capacity limits.

Ownership is refreshed on every write; an already-open writer retains the
custody receipt supplied when opened. Fresh custody is required on reopening,
restart and status. The host must prevent replacement/rollback of active files
and the ownership database. Coordinated rollback, an old pre-enrollment copy,
a malicious administrator with keys/raw SQL, broken filesystem locks,
distributed writers and physical power-loss behavior are outside these local
measurements. Operational rollback-resistant ownership custody remains open.

Actual independently administered Titan keys and signer/anchor custody,
the isolated OCI monitoring profile, private-host authentication and qualified
recovery remain required. The OCI profile proposal is in
`OCI_SECURITY_MONITORING_PROFILE_PROPOSAL_20261124.md`; it does not change the
gateway or dispatch a job. No production service or customer data is activated
by this checkpoint.

## Method

N-ality is applied to keep incident revision, ownership epoch, role, retained
evidence and production authority independent. The invariant is that changing
ownership does not change history or confer deployment authority. Simplex,
continuum and fuzzy lenses are not applicable to these discrete integrity and
authorization gates. Competing explanations for apparent recovery include
reuse of an old object, an uncommitted event and absent/corrupt proof; the
failure tests distinguish them. Passing fixtures or prior CI does not replace
exact-candidate CI or independently administered host qualification.
