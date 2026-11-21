# Merlin production completion — 21 November 2026

## Current position

Merlin has a tested engineering foundation and a limited running private read/demo service. The latest native-accepted candidate is an integration candidate for a first private research release. It is not a completed release of the whole platform.

This assessment concerns delivered functionality and release milestones. It reconciles canonical master plan version 6 with later source-specific checkpoints; it does not replace the plan or mark entire tracks complete.

The plan enumerates 45 tasks across 10 tracks. Those tasks differ in size, contain partial results and depend on externally configured services. Neither their count nor the software test count supplies a defensible completion percentage or calendar estimate.

## Exact accepted baseline

- Repository: `Mannyspiro/expert-robot`.
- PR188 remains an open draft, unmerged.
- Tested source: `45e927b7918edb7fffc3e0731c09a1df3d858866`.
- Observed documentation head: `634d9a88f5d0b4e13264a3ea360febeb83252856`.
- Selected source: 126 files, map SHA-256 `fddded3d28afeb9494831c301b8d6254328e424d3976bffae744e1d4e865e55f`.
- Local and native acceptance: the same 569 software tests.
- Native run: [44906658290, attempt 1](https://github.com/morganaspim/Cace-app/actions/runs/44906658290), additionally recording 8 kernel and 6 context cases.
- The native run observed the existing private service active, running and enabled with the same recorded PID before and after. It did not deploy PR188.

The complete scope and limitations are in the [native result checkpoint](../../config/merlin/plan-updates/20261121-resource-solver-native-result.json) and [efficiency record](RESOURCE_AND_SOLVER_EFFICIENCY.md). Source-file identity, component acceptance and a running older demo service are separate observations.

## Functional completion by area

| Area | Evidence-backed status | Remaining product milestone |
| --- | --- | --- |
| Private read/demo service | A real private service and isolated restoration of its two-record synthetic registry have recorded operational evidence. | Put the chosen release configuration through startup, resume, restore and telemetry acceptance. |
| Canonical context and artifact history | Versioned artifacts, exact references, provenance and source-scoped retrieval are implemented and tested. | Demonstrate representative private research retrieval with independently chosen original-source cases on its intended host. |
| Research and coding workflow | Durable workflow, model-binding interfaces, result records and restart/replay machinery have selected-source test coverage. | Connect actual model/coder/evaluator providers and complete one real original task. |
| Worker execution | Fixed bounded native worker and process recovery paths have actual execution evidence. | Demonstrate their composition in the chosen live research workflow. |
| Mathematics and resource efficiency | PR188 implements bounded-memory hashing and a faster exact rational solver in the studied local workloads. | Measure the chosen real workload; retain tiny-input regressions and architecture limits. |
| Host and direct user access | Host injection, model transport and private status interfaces have controlled implementation tests. | Provision actual host/provider inputs and demonstrate the intended user route. Direct ChatGPT web access is not established by a local Unix-socket route. |
| CAD, voice and institutional workflows | There are scoped implementations, fixtures and prior component results. | Complete the actual native tools, application flows and relevant pilots for any release that includes them. |
| Self-improving models and advanced simulations | Typed research machinery and bounded experiments exist; research has produced concrete ordinary-code improvements. | Establish actual editable-model experiments, independent original-task evaluation and measured benefit before claiming model improvement. |

Sources: [master plan](../MERLIN_PRODUCTION_MASTER_PLAN.md), [canonical task records](../../config/merlin/production-master-plan.json), [model transport and private status](MODEL_TRANSPORT_AND_BOUND_STATUS.md), [applied learning decision](APPLIED_LEARNING_RESEARCH_DECISION.md), and [PR188 efficiency record](RESOURCE_AND_SOLVER_EFFICIENCY.md).

The older plan's queued worker and optimization labels must be read alongside the newer bounded native and efficiency results. Conversely, the new results do not complete the plan's real model/provider integration or the full CAD, voice or institutional tracks.

## First useful private research release

The current user priority is applied research that improves Merlin, with direct practical use. The shortest useful release slice can therefore retain broader platform domains as deferred work while completing these milestones:

1. **Bind the real deployment and providers.** Supply the intended canonical registry/context, host configuration, authorized model/coder/evaluator adapters and operating budget through the existing entrypoints.
2. **Demonstrate one complete research task.** Retrieve its sources, run the original task, assess the result with an independent task oracle, retain exact evidence, report status and resume after restart without losing the result.
3. **Complete operational acceptance for that configuration.** Exercise application/service startup, the relevant state restore, telemetry and intended user access on the chosen target.
4. **Release the reviewed source.** Reconcile the draft source stack, run the required release checks, and merge/deploy through the existing release process.

These are milestones, not equal-sized units or an ETA. Actual provider/host inputs and a representative end-to-end run are the next decisive evidence.

An editable checkpoint is an additional requirement for weight-editing experiments; it is not inherently required for an API-backed research assistant. Consciousness-inspired task selection, non-reward learning and custom-physics ideas remain research directions and do not enlarge the first release's completion claim.

## This continuation

A bounded read-only storage inventory has been implemented through the existing registry and query facade. Its purpose is to distinguish current logical references, deduplicated known artifact storage and retained history, with explicit incomplete observations. It is useful resource accounting; retained history is not declared reclaimable.

The new 127-file candidate passed 581 selected software tests locally in 52.581 seconds, including 12 new accounting tests. Six separately prepared functional controls also passed across 10 actual inventory calls, preserving every before/after database and file snapshot. Published source is `bb2e3f31d631ac587a43322b42566f7808cf7005`. The [parent-linked storage checkpoint](../../config/merlin/plan-updates/20261121-storage-completion-local-result.json) records exact identities, measurements, scope and retained evidence. Prior native acceptance remains attached to PR188's exact source. New source does not inherit that native result.

## Evidence and open-input discipline

This reconciliation used the current plan, relevant governing documents and the exact narrow checkpoints. It is not a semantic review of all 191 captured document records or all private conversation history. The absence of a demonstrated live model run is an evidence limit, not a claim that no provider exists elsewhere.

The canonical plan remains version 6. This dated note and its plan-update checkpoint preserve the newer observations without rewriting previous results.
