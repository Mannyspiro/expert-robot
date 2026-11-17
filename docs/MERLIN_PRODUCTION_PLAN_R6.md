# Merlin production engineering plan - revision 6

Plan ID: MERLIN-PRODUCTION-20261116. Parent: revision 5 in `docs/MERLIN_PRODUCTION_PLAN.md` at `53284060d0cc01e08c21b46d64eba6594d848c8c`. This companion revision preserves that entire prior plan. Date: 2026-11-17. Production readiness remains NOT ESTABLISHED.

## User direction and objective

Proactively fix observed defects within the approved engineering scope, prevent known recurrence through tested guards, and reframe/decompose when a method stagnates. This does not authorize unbounded retries, production self-modification, changed trust roots, paid runners, merge, deployment or promotion. Avrea remains held until 2026-12-01.

The parent checkpoint integrated the real scientific-recording worker and atomic success acknowledgement. Its 148-test evidence remains historical evidence for that scoped source; it is not inherited as a pass for this new change. Current container GitHub DNS and Python 3.11 remain unavailable. Private connector access works; no visibility or credential change was made.

## Observations, predictions and falsifiers

Exact-parent probes reproduced: (1) a 201-character task ID raises a second telemetry ValueError and leaves the task leased; (2) exception text reaches telemetry/last_error; (3) telemetry failure prevents durable failure handling; (4) repeated RuntimeError consumes four attempts without reframing; (5) NaN/infinite retry delays are accepted; (6) revocation during preexecution telemetry still allows the handler to run, even though its eventual success is rejected.

Required invariants: invalid task identity cannot break error reporting; secret-bearing exception prose is not rendered into automatic failure diagnostics; observation failure cannot mask a durable retry/rejection decision; repeated symptom groups stop within a declared budget; nonfinite timing configuration is rejected; and authority is rechecked immediately before execution.

Falsifiers: any corresponding regression reproduces the old result after the patch; a denied/cancelled task becomes successful; an unrelated/changed-input run is silently reused; a retry exceeds either declared budget; or source-patching/promotion authority is inferred from a diagnostic record.

## Implemented continuation

- `failure_prevention.py` creates typed, bounded operational failure decisions without creating another store. Fingerprints group event/phase/error-family symptoms, exclude exception prose, and explicitly do not establish root cause.
- The existing Hermes worker stores decisions in its existing outbox `last_error` before best-effort diagnostics. Restart retains the counter. Default second same-group failure stops/quarantines; invalid contracts and resource/capability blocks stop immediately. Existing total-attempt limits and revalidated approval/leases still apply.
- Every decision carries a heuristic reframe, preserved invariants, next investigative actions and the requirement to rerun original acceptance tests. `resolved=false` and `promotion_authority=false` remain explicit.
- Invalid task IDs use the canonical outbox identity for diagnostics; valid task IDs cannot exceed telemetry's 128-character limit. Failure and denial paths do not render exception strings. Lost acknowledgement replies retain exact-receipt recovery. Nonfinite retry delays are rejected. A fresh cancellation/authority check occurs after preexecution telemetry and before calling the handler.
- The existing known-failure catalog retains its eleven entries and adds seven linked defect families. The new catalog test checks that referenced methods are real discoverable unittest tests and that the new suite is selected by the existing exact-source gate. The legacy smoke guard admits the new guard file without removing any prior assertion.
- AGENTS.md records proactive repair, negative controls, adjacent-class checks, bounded Ideonomy/Lacuna exploration, explicit analogy limitations and evidence-based closure. It does not guarantee future chats will load those files automatically.

## Validation and evidence boundary

Fifty-one local tests pass on Python 3.13.5: forty-one new policy/worker/catalog cases and ten unchanged existing Hermes worker tests. Real pinned outbox, telemetry and ArtifactRef implementations were used, with explicitly test-only approval/lease callbacks. The log and exact blob/digest manifest are in `docs/evidence/failure-prevention-local-20261117.json` and `failure-prevention-tests.log`. Baseline probes are retained in `failure-prevention-baseline.json`.

The exact-source CI gate now requires fifteen suites. Only the two focused suites above were executed in this iteration; the prior 148-test collection, all fifteen production suites, full native/formal suites, full legacy known-failure smoke, deployed authorization services, full runtime/service/API/HUD composition, real MCFC isolation and independent CACE were NOT run. Python 3.11 AST parsing is only a static check. No hosted CI or external workload was dispatched.

The failure decision is the latest operational record in a mutable outbox field, not a new append-only scientific plan store or a complete incident archive. Diagnostic events remain best effort; durable retries/rejections still survive their absence. An unavailable outbox cannot truthfully claim persistence and is surfaced as an error. Raw forensic evidence retention in an approved protected store remains an integration task; no secret-bearing exception text is copied automatically.

## Ranked next steps

1. Obtain the approved complete authenticated checkout and execute all fifteen suites on the exact committed source under Python 3.11; reconcile the research branch history and examine every result. No green result from another commit substitutes.
2. Run the full runtime/service/API composition with independently supplied real authorization services. Exercise the existing scientific-recording path plus this failure policy together; audit other error-reporting and acknowledgement producers. Persist evidence-backed defect cases through canonical immutable ArtifactRefs before claiming complete incident-history coverage.
3. Qualify actual MCFC OS/container limits, process-tree cleanup, monotonic deadlines, secret/network/filesystem controls and lease fencing before external worker execution. Cooperative checks do not forcibly stop a hostile or stuck handler.
4. Exercise independently authenticated CACE exact-source/artifact/signer verification and audit promotion routes. A local regression guard or fingerprint is not independent verification.
5. Qualify the complete research-to-artifact/HUD path, installation, migration, backup/recovery, observability and rollback; require explicit release/promotion approval.

## Bounded idea-space review and skeptical controls

Manual alternatives were: repeat unchanged work until the old limit (rejected by measurement); suppress every exception (rejected because evidence and errors would disappear); add a new incident database/orchestrator (rejected as duplicate architecture); or use bounded existing-outbox decisions plus tested class-specific repairs (selected). This is manual enumeration, not a trained Ideonomy/Lacuna run. Proposed reframes preserve task identity, authority, resource bounds and original acceptance tests; they are not asserted exact analogies or universal n-ality resolutions.

Symptom families can combine different root causes. Retry success does not prove the fault was transient; a passing repair test does not prove global recurrence impossibility. Correlated-author test bias remains; exact-source CI, broader negative tests and independent review remain mandatory. No test threshold was relaxed after a failure.

Rollback: revert only this feature-branch increment; retain prior plans and evidence. Source context is the available project handoffs plus task-relevant live/pinned source and source hashes, not every historical chat or all repository files.
