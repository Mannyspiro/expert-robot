# Merlin Held-Out Benchmark v1

Status: specification; task corpus and execution adapters are not yet implemented.
Branch: `feat/merlin-heldout-benchmark-v1`

## Purpose

Provide one reproducible, leakage-resistant evaluation protocol for Merlin across mathematics, Lean/formal verification, research synthesis, software engineering, and practical engineering. The benchmark measures end-to-end task success and evidence quality rather than model preference, verbosity, or self-reported confidence.

This is an evaluation contract, not a claim that Merlin currently passes it. A benchmark result is valid only when the task-set version, evaluator version, toolchain versions, execution environment, resource limits, and artifact digests are recorded.

## Design principles

1. **Fixed holdout:** task IDs, prompts, hidden tests, rubrics, and expected evidence are frozen before candidate evaluation. Candidate agents cannot read hidden material.
2. **No self-certification:** a model's assertion that work is correct is not a pass. Use independent tests, compilers, source checks, and CACE verification where applicable.
3. **Paired comparison:** compare candidate and baseline on identical tasks, budgets, tools, and environment snapshots. Randomize run order where stochasticity matters.
4. **Reproducibility:** persist task-set digest, candidate/model revision, prompt/config digest, tool versions, seed, resource limits, stdout/stderr digests, outputs, and evaluator receipts.
5. **Fail closed:** missing evidence, evaluator error, timeout, malformed output, or unverifiable provenance is not a pass. Report it separately from a substantive task failure.
6. **No contamination:** training, prompt tuning, GEPA, Inspect, and agent adaptation may use train/validation only. The holdout is never fed back into optimization.
7. **Cost-aware:** report quality alongside latency, tokens where available, CPU/RAM, tool calls, and estimated or measured execution cost.
8. **Human-auditable:** retain concise task-level explanations and links/digests for every score.

## Benchmark composition

Version 1 contains 100 scored tasks, 20 per domain. Each domain has 12 development/train tasks, 4 validation tasks, and 4 fixed holdout tasks. The task split is stratified by difficulty and task family. Holdout tasks are not exposed in development fixtures.

| Domain | Task families | Independent evaluator |
|---|---|---|
| Mathematics | symbolic derivation; numerical reasoning; counterexample search; proof planning; typed/N-ary operations | exact answer checks, property tests, independent numerical oracle, or proof checker |
| Lean/formal verification | compile supplied proof; complete bounded proof obligations; diagnose compiler errors; prove invariants; reject invalid claims | pinned Lean toolchain and mathlib revision; compiler exit code plus artifact digest |
| Research | literature retrieval; claim/evidence mapping; synthesis with disagreement; citation accuracy; explicit uncertainty | source identity/metadata checks, DOI/arXiv resolution, quote/claim entailment rubric, human adjudication for ambiguous cases |
| Coding | implement a specified change; repair regression; API compatibility; tests and edge cases; constrained refactor | isolated test suite, static checks, API contract tests, patch review rubric |
| Engineering | unit/dimensional analysis; circuit/netlist reasoning; CAD/geometry constraints; thermal/safety calculations; manufacturability trade-offs | dimensional/property checks, ngspice or CAD adapter when available, independent calculations, explicit assumption review |

The initial 100-task corpus is a target, not a statement that tasks already exist. Every task must have a stable ID, domain, family, difficulty, split, prompt digest, allowed tools, resource budget, evaluator contract, expected artifact type, and provenance.

## Task record contract

Each task record must include:

- `task_id`, `benchmark_version`, `domain`, `family`, `difficulty`, `split`
- `prompt_sha256` and a reference to the prompt artifact
- `allowed_capabilities`, `forbidden_capabilities`, and `resource_budget`
- `expected_outputs` and `evaluator_id` with evaluator version/digest
- `scoring_rubric`, `critical_failure_conditions`, and `provenance`
- optional `seed`, pinned toolchain, reference sources, and adjudication notes

Do not store hidden holdout prompts or expected answers in agent-readable training repositories. Keep them in a separately permissioned evaluation store; publish only aggregate results and non-sensitive task metadata.

## Scoring

For each task, record a vector rather than only a single scalar:

- correctness: 0–1
- evidence/provenance quality: 0–1
- completeness: 0–1
- constraint compliance: 0–1
- reproducibility: 0–1
- resource use: measured values, not a subjective score
- evaluator status: pass, fail, invalid, timeout, or not-run

A task's quality score is the weighted mean of correctness (0.45), evidence (0.25), completeness (0.15), and constraint compliance (0.15), but a critical failure caps the score at 0. A missing required provenance receipt makes evidence score 0 and prevents a verified-pass classification. Reproducibility and resource use remain separately reported so they cannot conceal incorrect work.

Report per-domain scores, macro-average across domains, verified-pass rate, critical-failure rate, invalid/timeout rate, median and p95 latency, and resource consumption. Include bootstrap confidence intervals for paired candidate-minus-baseline differences. Do not rank candidates on a single aggregate if any domain regresses beyond the pre-registered tolerance.

## Evaluation protocol

1. Freeze and hash the task manifest, evaluator code, hidden tests, toolchain images, and baseline configuration.
2. Run evaluator self-tests and known-positive/known-negative fixtures.
3. Execute baseline and candidate with identical task-level limits; record run order and random seeds.
4. Store raw outputs and evidence receipts before scoring.
5. Verify artifact digests and provenance independently. CACE receipts must bind exact source and output digests; a digest alone does not establish author identity.
6. Run deterministic evaluators first, then rubric-based adjudication only for cases marked ambiguous.
7. Compute paired metrics and confidence intervals; publish domain breakdowns and exclusions.
8. Promote only when the candidate improves the pre-registered primary metric without breaching domain, safety, or resource guardrails.
9. Preserve every run and decision in an append-only ledger. Never overwrite prior scores; corrections are new, linked records.

## RSI and optimizer isolation

GEPA, Inspect, prompt search, evolutionary selection, and other RSI methods are optional adapters. They may be evaluated only after the base harness is stable. Each optimizer run must record its parent candidate, search space, objective, budget, seed, mutations, selected candidate, and validation evidence. It may consume train/validation results, but must not inspect holdout prompts, labels, hidden tests, or task-level outcomes. Holdout execution is a one-way evaluation event; no automatic feedback path may carry hidden task content back to the optimizer.

## Promotion gates

A candidate is eligible for controlled promotion only if:

- all required task/evaluator receipts are present and valid;
- no critical failure occurs in the fixed holdout;
- the pre-registered primary metric improves over baseline with the agreed confidence threshold;
- no domain falls below its non-inferiority margin;
- resource use stays within declared limits;
- CACE independently verifies the exact candidate artifact and benchmark result bundle;
- Hermes records the evaluation and promotion decision with immutable lineage.

Promotion remains a separate, explicitly authorized action. Passing this benchmark does not grant new capabilities or authority.

## Initial non-inferiority and decision policy

Before the first candidate comparison, freeze a benchmark policy file specifying:
- primary metric and minimum meaningful improvement;
- per-domain non-inferiority margins;
- confidence interval method and resampling count;
- critical failure taxonomy;
- timeout and invalid-run treatment;
- maximum per-task and total resource budgets.

Do not choose these thresholds after seeing candidate results. The initial default policy should require a positive paired macro-average improvement, no domain regression greater than 5 percentage points, and zero critical failures. These defaults are provisional until signed off by the benchmark owner.

## Implementation sequence

1. Add versioned task/evaluation data contracts and JSON Schema.
2. Build deterministic evaluator runner with timeouts, resource limits, and append-only result records.
3. Add task families and train/validation fixtures; validate evaluator sensitivity using positive and negative controls.
4. Add pinned Lean and Python/C++ test adapters.
5. Add Crossref/arXiv source-resolution evaluator and research citation rubric.
6. Add engineering adapters incrementally; do not label a CAD/circuit task verified when its external tool is unavailable.
7. Add CACE receipt verification and Hermes event/lineage integration.
8. Create the sealed holdout corpus and freeze hashes only after the harness passes its own tests.
9. Run baseline, then candidate; publish the report and promotion recommendation.

## Current limitations

- This PR introduces the protocol only. It does not yet include the 100 task prompts, sealed holdout store, executable evaluator, CACE transport, or CI results.
- No benchmark pass rate should be reported until the corpus and evaluators are implemented and independently exercised.
- Engineering evaluation must distinguish analytic checks from real CAD/ngspice execution; do not substitute mocks for external tool receipts.
