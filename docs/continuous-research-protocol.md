# Continuous research protocol

This document operationalizes `MERLIN-RESEARCH-001`. The machine-readable contract is
`config/research/reasoning_protocol_v1.json`; the reasoning-error reference is
`config/research/reasoning_checks_v1.json`.

## Activation

Invoke the protocol automatically when relevant to research, engineering, design,
debugging, planning, scientific claims, model selection, cross-domain reasoning,
or self-improvement. Do not force the full pipeline onto simple lookups or
format-only tasks.

## Runtime adapter

The Python entry point `python/orchestrator.py` calls
`python/research_protocol.py` before forwarding a task to the existing C++
runtime. Activation modes are:

- `auto`: activate for research/engineering/design/debugging/planning and
  related triggers;
- `always`: force the protocol context;
- `off`: do not attach it.

The adapter validates the protocol identity, ordered nine-stage pipeline, and
authority invariant. It binds the protocol and mathematical method registry
SHA-256 digests into the context and emits an activation event to stderr
without logging the task text.

This is a runtime prompt/context adapter, not yet a full C++ state-machine
implementation of every protocol stage. It does not import conversation
archives, invoke new mathematical solvers, verify claims, or produce CACE
receipts. Those are separate implementation gates.

## Mathematical capability registry

`config/research/math_method_registry_v1.json` distinguishes:
- existing executable and verified boundaries (Lean formalization, theorem
  graph, hash-chained episode ledger);
- qualified prompt procedures (analogy, geometry/algebra/duality/spectral/
  topology, skeptic/counterfactual, and lacuna);
- partial evaluation infrastructure (strategy ranking and benchmark metrics);
- methods that remain research-only or not implemented as runtime solvers
  (general Bayesian inference, information theory, control/dynamical/
  numerical solvers).

A registry entry is not a qualification. The runtime must not claim an
unimplemented method was executed. Promotion requires implementation,
assumption checks, independent tests, and measured results.

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

### Operator-learning and transformation tests

For problems involving learned procedures or transferable reasoning, represent
a solution as a typed sequence of operations rather than only a final answer.
Use procedural task generation, symbol/label renaming, coordinate transforms,
irrelevant perturbations, inverse tasks, and load-bearing counterfactual pairs.
A valid method should preserve outputs under transformations that preserve the
problem and change outputs under interventions that change a load-bearing
condition. Hold out entire operation compositions to test generalization.

Candidate objectives include equivariance, invariant agreement, contrastive
structural consistency, executable program validity, counterfactual consistency,
and simplicity of valid operation sequences. These are evaluation signals,
not proof of general intelligence.

Geometric algebra, symmetry groups, typed graphs, spectral structure,
multiscale coordinates, and topological summaries are candidate representations
when they preserve the task's semantics and can be benchmarked against simpler
baselines. A cellular-automaton-inspired heartbeat may help scheduling or
visualization, but it remains orchestration metadata and cannot certify
scientific truth.

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
