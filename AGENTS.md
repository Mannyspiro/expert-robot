# Repository agent instructions

Before working on Merlin, Hermes, Avrea or CACE, read [docs/AI_RUNNER_AND_BRIDGE_OPERATIONS.md](docs/AI_RUNNER_AND_BRIDGE_OPERATIONS.md), then [docs/MERLIN_AVREA_HERMES_ROUTING.md](docs/MERLIN_AVREA_HERMES_ROUTING.md) and [docs/cace-bidirectional-bridge.md](docs/cace-bidirectional-bridge.md). Fetch live workflows and exact-run evidence; do not rely on historical chat context.

- Capability grows; authority never expands.
- Do not claim runner dispatch, Lean compilation, tests or CACE verification without evidence.
- Never commit credentials, private keys or certificates.
- The CACE-app SSH key is repository transport access, not verifier authentication.
- Keep Lean compilation separate from CACE proof verification.
- Keep training and held-out corpora disjoint and versioned.
- Do not merge or deploy without explicit approval.

- If independent CACE credentials are unavailable, keep research and artifact capture running with `artifact_verifier=None`; surface `blocked_missing_credentials` and never claim verification or promotion.
- Never create placeholder secrets to satisfy GitHub's non-empty secret form.


## Mandatory scientific operating loop

Before any research, engineering, or self-improvement episode, read `docs/MERLIN_SCIENTIFIC_OPERATING_LOOP_V1.md`. Merlin must use the evidence-first cycle: frame → observe with provenance/uncertainty → preserve competing hypotheses → generate falsifiable predictions → run bounded experiments → skeptical/independent review → append a plan update → convert failures into regression and prevention rules.

- Use induction for measured generalization, deduction for explicit consequences, abduction for competing explanations, and analogy only with explicit invariant mappings.
- Trigger Ideonomy enumeration only for a concrete blockage, unexplained observation, design trade-off or search gap. Enumerate only compatible, useful, budget-feasible combinations; do not use unconstrained Cartesian products.
- When blocked, first isolate the failing operation and invariants, then solve smaller analogous subproblems, translate back and rerun original acceptance tests.
- Treat model output as hypothesis, not evidence. Preserve null/negative results, uncertainty, dissent and rejected hypotheses.
- Append plan versions linked to exact observations, artifacts and source commits. Never silently rewrite plan history.
- Every bug class must yield a minimal reproducer, root cause, regression test, detection rule and preventive control; verify the control catches the class.
- Runtime integration must enforce this contract through typed records and Hermes stage gates; documentation or prompts alone are insufficient.
- These practices never authorize merge, deployment, signing, promotion or expanded capability. Existing approval and CACE trust boundaries remain in force.

## Production continuation and prompt admission

Read the latest appended revision in [docs/MERLIN_PRODUCTION_PLAN.md](docs/MERLIN_PRODUCTION_PLAN.md) and its scoped evidence record before continuing this branch. Re-query live heads and workflow evidence; a planning snapshot is not qualification. Preserve the canonical scientific-loop contract above rather than creating a parallel registry or orchestrator.

New `PromptCompiler` tasks include `python/merlin/scientific_workflow.py` and bind the runtime-owned preamble, source, task identity, recipient, authority and approval reference. The focused regression command is:

```sh
PYTHONPATH=python python -m unittest discover -s tests -p 'test_merlin_scientific_workflow.py' -v
```

This proves instruction inclusion and envelope consistency only. It does not prove model compliance, scientific correctness, independent verification or coverage of other chat/model entrypoints. Wire the suite into approved focused CI and integrate existing typed scientific-loop records into canonical registry/Hermes gates before claiming broader enforcement. Preserve historical prompt bytes and results; recompile old envelopes for new publication through the stricter compiler.

For each substantive session, record task-relevant context coverage with exact source/revision and read, partial, stale or missing status. Do not claim every prior chat or repository file was read. Carry decisions, evidence, open obligations and the next ranked step in durable artifacts rather than relying on conversational memory.

Keep Lacuna-inspired coherence, corpus-relative availability and empirical support distinct. Label exact analogy only with a checked structure/solution-transfer mapping; otherwise name the unmatched assumptions and transfer tests. Treat n-ality as a defined, testable method, not an asserted universal paradox solver. Check concrete bias/fallacy risks and counterexamples without claiming an exhaustive or bias-free review.

No paid compute or speculative CI. Preserve the recorded Avrea hold until 2026-12-01 unless the user explicitly changes it. No new merge, deployment, signing, credential/trust-root mutation or capability promotion is authorized by this continuation.
