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

## Default research discipline and master plan

Read skills/merlin-skeptical-scientist/SKILL.md for consequential Merlin research, engineering, coding and self-improvement. Use config/merlin/production-master-plan.json and docs/MERLIN_PRODUCTION_MASTER_PLAN.md as the consolidated navigation and ranked dependency plan; retain the existing canonical catalogs and prior versions.

- Frame explicit premises, observations, unknowns and falsifiers before ingesting persuasive new claims, then update from reliable evidence. Record concise checkable rationale, not a private reasoning transcript.
- Assess simplex, n-ality, continuum and fuzzy-logic lenses in every substantive research plan. Apply, defer or reject applicability with a reason and invariant/translation-back test. Do not force an irrelevant representation. Membership scores never replace probability calibration or Boolean permission/evidence gates.
- Use typed research plans/reviews and canonical merlin.scientific_loop primitives. The private fixed circuit episode requires a valid frame before execution and retains a review afterward; provider-wide Hermes integration remains separately tracked.
- Proactively fix routine reversible defects within existing user authorization. Isolate a minimal reproducer, root cause or unknown, dependency impact, sibling mechanism sweep, regression, preventive guard and rollback. Recompute only invalidated dependents. Never bypass a denied action or weaken an evidence gate.
- Treat Ideonomy/lacuna/alien-science combinations as bounded, source-linked hypotheses with explicit search coverage and falsifiers. A ledger gap is not global novelty; a toy model is not physical qualification.
