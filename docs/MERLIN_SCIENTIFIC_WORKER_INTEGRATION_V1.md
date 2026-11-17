# Scientific recording through the existing Hermes worker

Status: source-authored and locally tested on a focused Python 3.13.5 source subset. Not independently verified, production-qualified, deployed, or enabled by default.

## Composition and authority

The existing `build_merlin_hermes_runtime` accepts `include_scientific_recording=False`. Explicit boolean opt-in calls `register_scientific_recording` before constructing the existing HermesWorker. The helper uses the same MerlinRegistry, HypothesisLedger, approval validator and MCFC lease validator as that runtime. It refuses to replace an existing recording handler or use noncanonical stores. No new registry, database, scheduler, executor or approval service is introduced.

The helper and real worker path were executed locally. The complete runtime composition module was syntax/AST checked only: its full import graph, service start, API and default application wiring were NOT exercised in this focused checkout. The feature remains disabled by default; a source hook is not a deployment activation.

Deployment-owned approval must authorize the complete task, including episode, operation, hypothesis, exact inputs and budget. Policy callbacks in the integration tests are explicitly TEST fixtures, not a real operator approval or MCFC service. All approval, lease and artifact-validation callbacks must return literal True; a nonempty string or object is not approval.

Scientific admission rechecks the hypothesis's existence, project scope and independently supplied policies at recording boundaries. Refuted hypotheses may still receive negative records; recording never changes hypothesis status or appends hypothesis evidence. Worker task and artifact arguments are copied so accidental mutations cannot change the admitted receipt; mutated handler tasks are rejected.

## Receipt and completion-event atomicity

`MerlinEventOutbox.acknowledge_with_events` uses the existing SQLite database and `enqueue_in_transaction`. It requires a current unexpired worker lease, stores the exact result receipt and inserts completion announcements in one transaction. Failure rolls back both the receipt transition and announcements. The worker no longer announces completion before acknowledging the task.

Replaying an acknowledged batch requires the exact stored receipt and matching existing events. A replay cannot add new completion events or replace a receipt. The older `acknowledge` method retains its historical compatibility behavior for other callers; do not claim all callers acquired the stronger contract.

Worker completion events reference the parent outbox event and canonical receipt digest. A lost response after COMMIT is reconciled against the stored receipt rather than rerunning work. Handler results are normalized to their JSON representation first, so tuple/list serialization differences do not produce false loss reports.

A completed scientific-recording task means the record was persisted and its task receipt acknowledged. It does NOT mean a physical experiment ran successfully, a measurement is true, or a claim was independently verified. Failed, inconclusive and not-run experiment outcomes can be correctly recorded by completed recording tasks.

## Recovery and cancellation

The local integration exercised the sequence:

raw artifacts -> observation -> initial plan -> prediction/falsifier set -> outcome -> immutable parent-linked plan revision -> outbox receipt and completion announcements.

It also exercised an actual local child interpreter terminating with `os._exit(23)` after record persistence and before acknowledgement. After lease recovery and reconstruction of the existing stores/worker, the original task completed without adding another artifact version. This is bounded crash recovery evidence, not distributed exactly-once execution.

Cancellation after persistence leaves a valid immutable record but no successful task acknowledgement or completion announcement. Revoked approval/MCFC lease, expired delivery lease and lease replacement likewise block success. Missing hypotheses, wrong project/episode scope, invalid predecessor records, missing falsifiers, changed delivery inputs and tampered source bytes fail closed.

The receipt and telemetry share one outbox transaction; registry blobs and stage checkpoints do NOT share that transaction. Unacknowledged immutable records can remain after cancellation or interruption. They must be reconciled, not silently deleted or treated as successful task results. There is no claim that stale workers cannot write any artifact before noticing lease loss.

## Concrete regression observations

At parent source `1754d4819d5b6bc0ec2dcc09bf6c2e0a98549011`:

- injected acknowledgement failure left a task pending but one task.completed announcement;
- revoking approval inside a handler still resulted in a completed acknowledgement;
- a nonempty string `denied` from the approval callback was treated as approval;
- holding references to three ledger connections after three get calls showed all remained usable, because the connection context committed/rolled back but did not explicitly close.

The new probes report zero completion announcements for failed acknowledgement, revocation and nonboolean approval. HypothesisLedger methods now explicitly close their connections with contextlib.closing; its prior public behavior and existing tests are preserved.

## Executed evidence

The final local validation ran 148 distinct tests in five bounded batches, with zero failures, errors or skips:

- 35 scientific-worker/atomic-completion integration tests;
- 42 scientific-recording tests;
- 14 scientific-loop tests;
- 10 unchanged existing HermesWorker tests;
- 11 unchanged existing outbox tests;
- 8 unchanged existing hypothesis-ledger tests;
- 28 research-stack gate fixture tests.

The initial combined command hit the 60-second tool execution limit before finishing; it is not counted as a completed pass. Batching retained the same tests and acceptance assertions. All final test IDs were deduplicated. Evidence is in `docs/evidence/scientific-worker-local-20261117.json` and `scientific-worker-final-tests.log`.

The exact-source CI gate now selects fourteen required suites, including the integration, worker, outbox and ledger suites. No hosted CI job was dispatched. Python 3.11 AST parsing is not Python 3.11 execution.

## Remaining gates and limits

1. Complete authenticated checkout and all fourteen suites on the exact new commit under Python 3.11; reconcile branch history and inspect exact-run evidence.
2. Execute the actual full runtime/service/API composition and deployment-owned authorization integration. Audit other acknowledgement/telemetry producers for the same defect class.
3. Qualify MCFC OS/container enforcement, monotonic deadlines, process-tree termination, secret/network/filesystem limits and fencing before any external worker dispatch. These cooperative checks are not a sandbox.
4. Exercise independently authenticated CACE verification with exact source/artifact/signer bindings. Registry hashes and local fixture callbacks provide no verifier identity.
5. Qualify the full research-to-artifact/HUD path plus installation, migration, backup/restore, observability, rollback and explicit promotion approval.

The final policy check is not transactionally fenced with an external authorization service. A noncooperating handler cannot be forcibly terminated by these checks. The canonical registry's concurrent blob-write behavior remains a separate obligation. Existing low-level hypothesis status APIs are not themselves a complete CACE/approval boundary; recording avoids them, and end-to-end promotion routes still require audit.
