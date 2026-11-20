# Cross-agent improvement review

Merlin and dot can use `dot_ai_os.cross_agent_review.CrossAgentReviewer` to evaluate a change to any registered agent. The default roster covers Merlin, dot, coder A, coder B, the evaluator and the reviewer. A host may configure additional roles and bind them to its actual provider identities. Supply an evaluator independently of both coders and the target, including for changes to the reviewer itself. The comparison checks declared identities. Authenticating them and enforcing provider isolation remain host responsibilities.

## Host integration

Use an existing project in `MerlinRegistry`. Register the baseline and supporting context as exact artifact versions. The first context item is always the baseline. The host supplies a source commit, fixed train and held-out case labels, and the three provider manifests documented by `DualCoderWorkflow`. A manifest binds the provider ID and revision plus the prompt, configuration and adapter hashes. Persist the returned protocol reference. A different set of labels, revisions or sources starts a separate trial.

```python
from dot_ai_os.cross_agent_review import CrossAgentReviewer

reviewer = CrossAgentReviewer(registry, roster=host_agent_identities)
protocol = reviewer.prepare(
    target="merlin", baseline_ref=baseline_ref, context_refs=supporting_refs,
    objective="Improve routing on the frozen cases", source_commit=source_commit,
    providers=provider_manifests, train_labels=train_answers,
    holdout_labels=heldout_answers,
)
review = reviewer.run(protocol, coder_a=author, coder_b=challenger, observe=observer)
```

The two coders retain dot’s existing callback contract. Each returns a candidate and rationale. The observer receives the baseline reference, candidate texts and references, pinned inputs and case IDs. It returns one mapping per arm (`baseline`, `coder_a`, `coder_b`) from every frozen case ID to its observed text label. Coder requests omit held-out IDs and keys. Expected labels stay in the host. Registry access needs separate host enforcement, and distinct case IDs do not establish semantic independence. Use versioned, genuinely withheld cases and record how the observer obtained its outputs.

Each comparison keeps the exact outputs and the list of baseline matches lost by each candidate. Reviewers re-score the stored outputs on resume. A research recommendation requires an additional held-out match and zero lost matches across both splits. Training-only gains, unchanged scores and regressions remain visible. The returned reference identifies the existing dot workflow report and a separate content-addressed per-case observation in the same registry.

After a restart, `reviewer.status(protocol)` returns the next stage or the completed comparison. `reviewer.coverage()` lists every target with its frozen protocols, including empty roles. A fresh host can call `run` again with the same reference. Completed callbacks replay from the journal. A callback with a recorded intent but no valid output remains in `reconciliation_required`. Providing no adapters is sufficient to initialize and inspect a pending trial.

## Regression experiment

The four-case control compares an observer that reports aggregate counts with the reviewer that retains per-case predictions. One training case stays correct. On the three held-out cases the baseline passes one, candidate A passes two but loses the baseline’s previous match, and candidate B leaves all baseline outcomes unchanged. The aggregate control selects A when its observer reports zero regressions. The per-case reviewer identifies the exact lost case and retains the parent. A separate positive control gains both missing matches without losing the old one and recommends independent evaluation of that candidate.

Run `PYTHONPATH=python python -m unittest discover -s tests -p 'test_cross_agent_review.py' -v` from the repository root. These deterministic fixtures test the review decision. Measuring an actual agent change requires observations from the configured host adapters on fresh cases. A stored recommendation carries no authority to install a change, merge, dispatch, sign, qualify or deploy.

## Reproduce a dot product measurement

Run this from the repository root using a local registry directory.

```sh
PYTHONPATH=python python scripts/measure_dot_review.py --registry /tmp/dot-review-v1
```

This exercises the actual `DotContextBridge.search` implementation on three hash-checked repository documents. A host-scoped question supplies one permitted document. A query must return its first matching locator or `no_hit`. Fixed software adapters compare unrestricted retrieval (baseline), namespace selection (A) and exact record/source pins supplied by the host (B). Run it again on the same directory to replay the journal. The benchmark prints the raw observed locators, exact source hashes and durable report reference. The included evidence is at `docs/evidence/dot-cross-agent-retrieval-review.json`.

The baseline returned the expected locator or miss on 2 of 5 held-out questions, namespace filtering on 3 of 5 and exact pins on 5 of 5. Both candidates retained the baseline's correct answers, and both passed both training questions. A same-namespace sibling document contained matching words for two questions. Only exact pins excluded that sibling before retrieval. This supports choosing the existing pinned search option for this host-scoped task. These deliberately constructed scope probes do not measure generally better search, production traffic, access enforcement or independently authored model output.
