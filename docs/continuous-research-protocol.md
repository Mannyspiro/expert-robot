# Continuous research protocol

This document operationalizes `MERLIN-RESEARCH-001`. The machine-readable contract is
`config/research/reasoning_protocol_v1.json`; the reasoning-error reference is
`config/research/reasoning_checks_v1.json`.

## Activation

Invoke the protocol automatically when relevant to research, engineering, design,
debugging, planning, scientific claims, model selection, cross-domain reasoning,
or self-improvement. Do not force the full pipeline onto simple lookups or
format-only tasks.

## Ideonomy and useful lacuna exploration

Enumerate a bounded idea space. Search for missing links, unexplained observations,
unmodeled mechanisms, and useful combinations across disciplines. "Lacuna alien
science" is a deliberate prompt to look beyond familiar disciplinary boundaries;
it is not a license to invent evidence or assert unsupported physics.

Retain a combination only when it has a coherent mechanism, respects known
constraints, has a plausible use, and admits a test. Record rejected combinations
and why they failed. Keep novelty, utility, explanatory power, feasibility,
risk, and testability as separate dimensions.

## Induction and deduction

Induction starts from observations and measurements, identifies patterns, and
forms hypotheses with alternatives and uncertainty. Deduction starts from
explicit premises, derives consequences, and turns them into predictions and
acceptance tests. Reconcile disagreements between the two; neither direction
silently overrides the other.

## Analogy and decomposition

Translate a blocker into a representation that exposes its structure. Map
relationships rather than superficial vocabulary. Explicitly state what the
analogy preserves and what it does not. If no faithful analogy exists, isolate
the failure, produce a minimal reproducible case, split the problem into
independent subproblems, solve and verify them, then recompose and test the
original problem.

An analogy is a search heuristic, not proof.

## Skeptical review

Use the fallacy/bias taxonomy as an active checklist. Do not mechanically label
arguments; cite the exact reasoning step and explain the mismatch. Seek
disconfirming evidence, competing hypotheses, falsifiable predictions,
counterexamples, uncertainty, and independent reproduction. Lack of
counterevidence is not confirmation. Consensus, confidence, model fluency, and
novelty are not proof.

## Mathematical method selection

Select mathematical tools only after checking the problem's assumptions and
domain. Candidate families include formal logic and type theory, linear algebra,
graph theory, optimization, Bayesian inference, statistics, information theory,
control theory, dynamical systems, numerical analysis, dimensional analysis,
topology, geometry, game theory, category theory, and formal methods.

For each selected method, record why it applies, assumptions, expected benefit,
cost, error bounds, and a baseline comparison when measurable. Avoid adding
mathematics that does not improve the result.

## Engineering loop

For each meaningful project change, preserve:
- requirement and source reference;
- observation or measurement that motivated the change;
- hypothesis and derived design decision;
- exact artifact revision;
- implementation and test commands;
- complete logs and results, including failures;
- verifier identity and evidence;
- remaining uncertainty and next ranked step.

Update the plan from measured outcomes. A failed test changes the plan; it does
not disappear from the record. A queued workflow is not an executed test.

## Trust and authority

Models propose. Agents investigate and implement within explicit leases.
Independent verifiers assess artifacts. Trusted-state promotion and authority
changes remain behind explicit policy gates. Generated claims, ideas, code,
and summaries are untrusted until checked by the appropriate independent
mechanism. Learning must never expand authority implicitly.
