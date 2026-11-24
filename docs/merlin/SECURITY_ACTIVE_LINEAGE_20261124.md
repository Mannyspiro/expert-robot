# Studio review of active synthetic security history

Studio parent: `370726c22e35f12746225367bad23fae70304eab`, draft PR #229.
Producer parent: `298f53862a9757147c8f9490c21688ff508e81fe`, draft PR #228.
Published producer candidate: `33303d5947024d10155a66a6dc6d46221088276a`.
Complete producer tree: `d76d66364e2f77b8ff1a043d4edf4c58ff64a65a`.

This continues `20261124-security-writer-handover-producer-pin.json` without
rewriting its evidence. The previous Studio contract described either one
ledger or a staged predecessor/successor pair. It could not represent the
active successor after another reviewed generation transfer.

## Contract and display

The new `merlin-studio-security-summary/3` import represents two through eight
ordered segments. Earlier segments are `archived_predecessor`; only the final
segment is `active_successor`. Every revision remains local to its segment.
The top-level `active_segment_index` identifies that final segment, while
`ownership_epoch` is its reported current ownership epoch. Neither number is
an authentication credential or a global incident revision.

V3 retains the exact v2 fields and adds only those two ownership fields. Its
scope is `active_lineage`. `writer_handover_verified=true` is explicitly a
host report. Activation, execution and production-qualification fields remain
false. The existing v1 and staged-v2 contracts retain their behavior; in
particular, v2 still requires an untouched successor and unverified handover.

The import checks dense segment order, one active final role, bounded counts,
the revision/event/review relationship, exact aggregate categories and totals,
and the final chronological suffix of up to 20 incidents. Archived segments
require their exact reported tip anchors. The active segment requires a
reported signed anchor between genesis and its current tip; its anchor may
lag recent accepted events. The producer performs the actual history and
custody verification before export. Studio checks the minimized structure and
does not independently verify the source signatures or current writer.

Ledger identities, owner identities, handover identities, keys, signatures,
checkpoint hashes, timestamps and raw payloads are excluded. Extra fields,
unknown categories, reordered roles, history gaps, inconsistent totals and
authority promotion fail validation. The existing 32 KiB regular-file bound,
duplicate-JSON-key rejection and no-follow file handling are retained.

The page displays each segment's counts and pending alerts, aggregate totals,
the reported active segment and ownership epoch, and the bounded incident
timeline. Clearing pending alerts on the active segment cannot remove the
separate archived pending counts from this view. The page remains a read-only
startup snapshot with loopback/origin protections and no activation, transfer
or acknowledgement controls.

## Local verification

All 55 Studio tests passed in 28.386 seconds, including 19 security-review
tests. The seven additional tests cover three-segment rendering, preserved
archived alerts after an active-segment review, exact-field and authority
rejection, order/role/anchor validation, category totals, a truncated suffix
spanning three segments, eight full segments, and the actual read-only HTTP
route. Existing v1/v2 tests remain in the same successful run.

The rebuilt source-only package contains 30 payload files and one manifest,
and passed exact inventory and shipped-byte verification. Its SHA-256 is
`e6954bcc495e32f137061b55ede260cca2d6878fcb2dc12b1bb7ae78214e141e`
and size is 100,495 bytes. It contains no model weights, Python runtime,
inference engine or user state. Package integrity is not source authenticity
or production qualification.

The v3 development component check used actual encrypted ledgers, signed
archives, reviewed rotations and writer transfers, then passed its export to
the extracted package's actual HTTP server in another process. Its fixed
scenario contains three segments, five events, no operator reviews and two
unresolved archived integrity alerts. The final segment has one event at
revision two with its retained genesis anchor, active index two and ownership
epoch one. Two retired writer objects were rejected before their signers.
Reading the view preserved source, archive and coordinator bytes. The page,
cross-origin rejection and fixed startup snapshot passed, and the complete
export matched the independent literal scenario in the handoff script.

That development check did not exercise the published-source pin gate. The
full acceptance entry point, `portable/tests/security_handoff_smoke.py`, keeps
its exact producer SHA and clean-worktree checks before and after execution.
It now runs v1 encrypted recovery, v2 staged rotation and v3 active lineage,
each through the extracted package. The combined receipt schema is
`merlin-security-handoff-evidence/2`. The accompanying plan update records
whether the exact published-source run has completed and embeds its receipt;
development observations cannot substitute for that gate or remote CI.

## Published-source acceptance

The complete three-scenario handoff subsequently passed against a clean
checkout of published producer `33303d5947024d10155a66a6dc6d46221088276a`.
The workflow checkout and handoff constant both pin that exact revision, and
the producer's tracked and nonignored untracked state was checked before and
after the run. The unchanged `e6954b...` package above reached its actual HTTP
page in a separate consumer process for each producer export:

| Scenario | Observed result |
| --- | --- |
| V1 encrypted recovery | Five events, one operator review and signed anchor revision seven. |
| V2 staged rotation | Two predecessor events, one unresolved alert and an untouched inactive successor; handover remains unverified in this view. |
| V3 active lineage | Three segments, five events, two retained archived alerts, active segment two and ownership epoch one; two retired objects rejected. |

All three route, cross-origin and fixed startup-snapshot checks passed. The
combined receipt SHA-256 is
`e37e8efd6cae145d6865ea6f1f150289fb623754c577c84709b325742331f9bc`.
The parent-linked Studio plan embeds the complete receipt and its exact
serialization rule. The producer's
[generation contract](https://github.com/Mannyspiro/expert-robot/blob/33303d5947024d10155a66a6dc6d46221088276a/docs/wilborn/SECURITY_GENERATIONS_AND_ACTIVE_REVIEW_20261124.md)
and [plan update](https://github.com/Mannyspiro/expert-robot/blob/33303d5947024d10155a66a6dc6d46221088276a/config/merlin/plan-updates/20261124-security-generations-active-review.json)
retain its separate implementation and verification evidence. These local
acceptance results do not substitute for CI on the published Studio candidate.

## Scope and remaining requirements

The active-lineage label reports a local synthetic producer state. The page
does not independently authenticate it, grant a writer lease or establish a
running production monitoring service. The producer's bounded generation
protocol, custody assumptions and source-specific tests remain controlling.
Actual independently administered Titan keys and signer/current-anchor
custody, an approved isolated monitoring profile and authenticated private-host
qualification remain open. Existing model, provider and browser work is not
requalified by this display change.

The principal test invariant keeps incident revision, generation position,
ownership epoch, pending alerts and production authority independent. N-ality
is applied to those separate axes. Simplex, continuum and fuzzy models are not
applicable to the exact schema, integrity and authorization gates. The tests
challenge plausible alternative explanations such as a staged summary being
relabeled active, a missing older incident or an aggregate that silently drops
archived alerts.
