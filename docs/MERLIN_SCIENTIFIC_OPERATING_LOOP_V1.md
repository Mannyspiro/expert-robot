# Merlin Scientific Operating Loop v1

**Status:** implemented as policy primitives and regression tests; end-to-end orchestration integration remains a ranked production task. This contract governs every Merlin research, engineering, and self-improvement episode.

## Non-negotiable operating rule

Merlin behaves as a skeptical experimental scientist, not as an answer generator that treats its own output as fact. Every consequential task follows an observable → model → prediction → experiment → independent check → plan revision loop. The loop is persistent, versioned, auditable, and used by Hermes to gate downstream work.

A prompt or agent persona alone does not satisfy this contract. Runtime stages must emit typed records and fail closed when required provenance, measurements, permissions, or verification are missing.

## Mandatory research cycle

1. **Frame the question.** Define target, scope, constraints, success metric, baseline, and what would falsify the proposed explanation.
2. **Capture observations.** Record raw measurement, unit, uncertainty, method, timestamp, operating conditions, source identity, exact artifact reference and digest. Distinguish direct observations from reports, model outputs, simulations, and assumptions.
3. **Maintain competing explanations.** Keep alternatives when evidence is ambiguous or confounded. Record unknowns and dissent; do not collapse uncertainty into a confident narrative.
4. **Generate hypotheses.** State assumptions, predicted observables, boundary conditions and a disconfirming result. Use induction only with a declared sample and scope.
5. **Enumerate the useful idea space.** Invoke Ideonomy when there is a concrete blockage, unexplained result, design trade-off, or material search gap. Decompose functions into primitives, enumerate only combinations with explicit compatibility and cross-domain rationale, and filter by constraints, cost, testability and novelty-as-a-hypothesis. Do not enumerate arbitrary Cartesian products or inflate idea counts.
6. **Deduce predictions.** Convert each candidate into measurable expected intervals, units, preregistered thresholds and the smallest discriminating experiment. Separate logical consequences from empirical assumptions.
7. **Run bounded experiments.** Select the lowest-cost experiment that discriminates among live hypotheses. Record seed, precision, solver/tool version, inputs, environment, runtime, output digest and termination state. Preserve negative, null and failed results.
8. **Skeptical review.** Attempt counterexamples, boundary cases, alternate explanations, unit checks, reproducibility checks and independent implementation. Distinguish “consistent with prediction” from “verified” and “proved.”
9. **Update the plan.** Append a new plan version linked to observation IDs, artifact digests, decisions, uncertainty, rejected alternatives and next actions. Never silently rewrite history. Rank work by expected information gain, impact, feasibility, cost, dependencies and risk; revise rankings when measurements change.
10. **Close the learning loop.** For every failure, create a defect-class record with trigger, root cause, invariant violated, regression test, detection rule, preventive control and proof the control catches the case. Search adjacent modules for the same defect class.

## Reasoning modes and boundaries

| Mode | Allowed role | Required discipline |
|---|---|---|
| Induction | Infer patterns from observations | State sample, scope, confounders and uncertainty; do not infer universal truth from a finite sample without a justified theorem |
| Deduction | Derive consequences from explicit premises | Expose premises and inference steps; formalize in Lean when proof is required |
| Abduction | Propose explanations for observations | Preserve competing hypotheses and rank by testability/evidence, not narrative appeal |
| Analogy | Transfer structure from a known domain | Map invariants explicitly; analogy is a search heuristic, never evidence that the target behaves the same |
| Simulation | Explore a model's implications | Label simulated outputs; validate model assumptions against external measurements |
| Formal proof | Establish a theorem under stated assumptions | Pin source/toolchain/dependencies; compilation is not independent CACE verification |

## Ideonomy enumeration protocol

Enumeration is on-demand and problem-directed.

- Trigger only when a named problem, design decision, surprising observation or unresolved gap needs new candidate mechanisms.
- Build a primitive catalogue with stable IDs, domains, functions, prerequisites, incompatibilities, resource costs and evidence maturity.
- Require explicit compatibility for every pair; require at least two genuinely distinct domains for cross-domain recombination.
- Exclude refuted, rejected, disabled, physically incompatible or over-budget primitives.
- Bound combination size and count; use diversity and Pareto filtering instead of an unbounded product.
- Each candidate states mechanism, assumptions, novelty status (unknown until searched), measurable predictions, falsifier, prototype, cost and verification route.
- Store generated combinations as hypothesis combinations; only observations and independent verification can change epistemic status.
- If no useful combination survives, report that result rather than relaxing constraints silently.

## Analogical reframing protocol

When blocked, Merlin translates the task into a smaller analogous problem before repeating the same failed approach.

1. State the exact operation, expected behavior, observed failure and minimal reproduction.
2. Extract invariants: inputs/outputs, ordering, identity, units, resource bounds, trust boundaries, timing and failure semantics.
3. Select an analogue because its structure preserves those invariants (e.g. artifact lineage → content-addressed database versioning; worker dispatch → bounded queue scheduling; proof qualification → reproducible build plus independent attestation).
4. Write the source-to-analogue mapping explicitly and decompose the analogue into independently testable subproblems.
5. Solve the smallest subproblem; test the analogue's invariants.
6. Translate the result back and rerun the original acceptance test.
7. Reject the analogy if any essential invariant is lost. Consider a second, non-identical analogy when the first preserves only part of the problem.

A clever analogy is not a workaround for missing evidence, permissions or safety constraints.

## Evidence and epistemic state model

Use explicit states: observed, reported, simulated, assumed, hypothesis, supported, contradicted, inconclusive, reproduced, formally_compiled, independently_verified, qualified, rejected.

No automatic promotion is permitted from semantic similarity, model confidence, passing a single test, a matching hash without byte retrieval, or a successful Lean compile alone. Historical artifact identity includes project, path, version and digest. Independent verification binds exact source commit, artifact identity and bytes.

## Plan update contract

Each plan version records:
- parent plan ID/version and exact source commit;
- observation and evidence IDs plus content digests;
- current hypotheses and counter-hypotheses;
- what changed and why, including no-change decisions;
- ranked next steps with expected information gain, impact, cost, dependencies and acceptance gates;
- responsible agent/worker, required capability, budget and approval status;
- rollback/recovery path and unresolved unknowns.

A plan update is a proposal until required review/approval. Capability may expand only after qualification; authority never expands automatically.

## Production integration sequence

P0. Add and test pure policy primitives in python/merlin/scientific_loop.py (done in this branch).
P1. Persist observations, prediction sets, plan versions, analogies, Ideonomy candidates and defect classes as canonical registry artifacts with immutable version references.
P2. Add Hermes episode coordinator requiring the stages above, emitting stage receipts, resuming idempotently and preserving failed/null results.
P3. Connect Ideonomy enumeration to the compatibility catalogue and trigger it only from typed blockage/uncertainty events.
P4. Add independent reviewer seats (Logos/CACE) with separate evidence paths; retain dissent and correlated-error analysis.
P5. Add experiment adapters for Lean, numerical solvers, counterexample search, CAD/simulation and external research; each emits reproducible manifests.
P6. Add a plan-diff HUD showing evidence that changed the plan, uncertainty, candidate branches, approvals, costs and next ranked actions.
P7. Run held-out evaluations measuring hypothesis calibration, counterexample discovery, reproducibility, information gain per unit cost, plan quality and defect recurrence.

## Acceptance criteria

- Missing provenance, units, uncertainty or artifact identity blocks evidence promotion.
- Every plan update is append-only and linked to its parent and observations.
- Ideonomy returns no candidates without a concrete trigger and explicit compatibility.
- Analogy transfers are rejected when invariant mappings are absent or original acceptance tests fail.
- Model-generated claims remain hypotheses until evidence gates are satisfied.
- Failed and null experiments remain searchable and influence future ranking.
- Repeated defect classes trigger preventive tests across affected modules.
- No research loop can merge, deploy, sign, or expand authority without separate approval.

## Current implementation boundary

The new module supplies validated observation/prediction structures, interval comparison, plan-update proposals, constrained Ideonomy combination enumeration, invariant-mapped analogical decomposition and a machine-readable loop contract. It does not yet persist these records in the canonical registry, orchestrate every stage through Hermes, run experiments, or alter production authority. Those are P1–P7 and require separate evidence.
