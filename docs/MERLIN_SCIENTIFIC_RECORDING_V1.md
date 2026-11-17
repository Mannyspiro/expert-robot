# Canonical scientific recording v1

Status: source-authored and locally tested on Python 3.13.5. This is a recording and transition-validation adapter, not an experiment executor or an independently verified production episode coordinator.

## Existing components, not a second registry

`python/merlin/scientific_recording.py` uses the existing `MerlinRegistry`, immutable `ArtifactRef`, `HermesStageJournal`, `Observation`, `Prediction`, `compare_observation` and `update_plan_from_observations` implementations. No additional database or schema migration is introduced. Records use the existing registry's append-only artifact versions. Checkpoints and stable semantic-identity reservations use the existing `hermes-stage-journal.sqlite3` file.

The runtime supplies project, hypothesis, episode, source repository and exact source commit. Each canonical record binds those identities, the command data, all exact input ArtifactRefs, and its deterministically derived payload. The content-addressed logical path is `scientific-loop/records/<sha256>.json`, pinned to artifact version 1. Historical source revisions remain readable; replaying a task under changed source configuration is rejected rather than silently reusing its old result.

Every output remains `verification_status=unverified`, `qualification=false`, `promotion_authority=false`. Registry digest verification means byte integrity, not scientific truth. The handler returns `evidence_refs=[]` and does not mutate the hypothesis ledger or fabricate a CACE receipt.

## Operations and predecessor requirements

| Operation | Exact input references | Data and gate |
|---|---|---|
| `observation` | One or more raw artifacts | Existing Observation fields; units and uncertainty for every measurement, aware timestamp, conditions and matching source digests. |
| `plan` | One or more observation records | Plan ID, objective, assumptions, at least two alternatives, acceptance criteria, falsifiers and next actions. Creates version 1 only. |
| `prediction_set` | Exactly one plan or plan-revision record | Experiment ID, typed predictions and one falsifier per predicted metric. Validation occurs even when a metric has not yet been measured. |
| `outcome` | Prediction set, zero to eight observation records, then at least one raw execution log | Run ID, status, reason and observation count. Completed/inconclusive results need measurements. Failed/not-run results are retained; not-run cannot claim measurements. |
| `plan_revision` | Exact parent plan, followed by one or more outcomes | Changes and next actions. Every outcome must belong to the exact parent. At least one measured observation is required. Parent acceptance criteria/falsifiers are retained. |

Observation IDs, root plan IDs, experiment IDs and run IDs are reserved against their exact content in the existing journal. Changing content under a new task ID cannot overwrite those identities. A new experiment needs a new ID. A prediction recorded in Merlin precedes its referenced outcome in this storage protocol; this is not an independent timestamp or proof that data were previously unseen.

Plan revisions are append-only proposals. Two distinct proposals may share the same parent and revision number, but have distinct full ArtifactRefs. There is no implicit latest-plan pointer or automatic selection/promotion. A later orchestrator must explicitly select an approved proposal. This avoids silently discarding alternative branches while preserving the parent obligation.

## Opt-in Hermes integration

`build_scientific_recording_handler` returns the `(task, context)` callable accepted by the existing HermesWorker handler map. Register it under `scientific_recording` in a separately qualified runtime composition. It is not automatically exposed by the current default handler factory or public API.

The runtime must provide an `admission_validator(task, context)` that independently checks policy, approval, lease and hypothesis existence; only literal `True` admits a task. A test callback is not production admission. Existing HermesWorker approval, lease and ArtifactRef validation remain mandatory. Task/context task ID, hypothesis ID, approval, lease, input refs and budgets must match. The command is under `experiment_spec`, with exactly `episode_id`, `operation` and `data`.

The handler snapshots input data, revalidates canonical lineage, binds the complete task and prepared record into the stage journal, checkpoints before persistence, and compares immutable output on replay. Completion is recorded only after canonical persistence. Failed persistence or checkpoint completion can be retried without regenerating provider outputs; this stage invokes no provider. Cancellation is checked before admission work, before persistence and before completion. A cancellation after persistence may leave a valid unacknowledged record for recovery. This is not distributed exactly-once execution.

## Bounds and trust limitations

Commands/records are capped at 256 KiB (the task envelope at 512 KiB); raw source artifacts are capped at 1 MiB each, with at most 16 direct input refs. Lineage traversal admits at most 128 distinct artifacts and 48 recursive levels, with an aggregate read ceiling no greater than 16 MiB and reduced by the task's memory admission estimate. Exceeding a bound blocks the operation; it never silently discards ancestry. Longer histories require a separately designed verified checkpoint strategy.

Reads re-hash exact source versions and re-derive payloads, including during completed replay. Missing provenance, cross-project/episode/hypothesis references, changed bytes, invalid numeric intervals, unsupported operations and authority claims fail closed. These are integrity/structure gates, not authenticity proofs. A coherently forged set of raw measurements remains unverified reported data.

These bounds are not OS-enforced CPU/memory/network/filesystem limits. The existing registry's filesystem concurrency behavior, worker lease fencing, cancellation races and secret isolation still need the MCFC supervisor and full-worker tests. The source-only handler must not be used to justify executing untrusted model, solver or media work.

## Regression evidence and remaining integration

The local final focused run executed 84 tests: 42 recording tests, 14 existing/extended scientific-loop tests, and 28 test-runner regression tests. Real registry and journal implementations were restored from verified Git blob identities, not substituted with in-memory mocks. Admission/lease labels in tests are fixtures. Full HermesWorker/outbox integration, the remaining research-stack suites, target Python 3.11 execution, independent CACE verification and production qualification were not run.

The exact-source CI gate now selects both scientific recording and scientific-loop tests in addition to its previous eight suites (ten total). No workflow was dispatched during this change.

Next integration: wire an actual policy-backed handler into the runtime composition; exercise task dispatch, lease loss, output acknowledgement and restart with the real HermesWorker; re-run all ten research suites under Python 3.11 on the exact committed checkout. Then qualify the MCFC supervisor and real CACE transport before a production end-to-end claim.
