# Adaptive research policy: implementation plan

## Goal

Improve verified research progress per unit compute by learning which bounded
search action to try next. This is an evaluation-first change: the adaptive
policy must beat fixed and uniform-random baselines on paired held-out tasks
before it can influence production search.

## Existing foundations discovered

The repository already contains much of the required substrate:

- `ResearchEpisodeLedger`: append-only SQLite events with a SHA-256 chain.
- `MathEvalLedger` and `compare_variants`: per-case telemetry and baseline
  ablation comparisons.
- `ProofRoutePlanner`, `ResearchStrategyPlanner`, and route outcome memory:
  bounded route scoring with empirical experience adjustments.
- `MathResearchEngineConfig::learning_writes`: disables persistent learning
  writes during evaluation.
- Separate verifier, Lean acceptance boundary, and explicit qualification /
  promotion gates.

Do not create a parallel ledger or a second source of truth. The first
implementation should extend these components or provide a thin adapter.

## Iteration 1 — Establish the experiment contract

The machine-readable contract is `config/adaptive_search_policy.json`.
It is deliberately marked `experimental_not_wired`; its presence does not
change runtime behavior or grant promotion authority.

Compare three arms on identical cases and budgets:

1. `fixed_baseline`: current production route/strategy ordering.
2. `uniform_random`: randomly select only from the same validated,
   bounded candidate set, using a recorded seed.
3. `contextual_bandit`: rank candidates using domain/context features and
   only outcomes that were independently verified.

The first trial must be small, deterministic where possible, and network-free.
Use existing benchmark cases and record the commit, seed, configuration hash,
case ID, candidate set, selected action, estimated cost, actual cost, result,
and verifier evidence.

## Reward and anti-gaming rules

- A target-level Lean-verified success is positive reward.
- A useful negative result may receive a small information reward only when
  the tested hypothesis and observation are recorded and independently
  reproducible.
- A verified helper lemma alone is not target success.
- Unverified model claims receive no positive reward.
- A verifier bypass or authority change is a hard rejection, not a trade-off
  that can be offset by a high score.
- Evaluation must not mutate production learning stores.

## Metrics

Report, per arm and per domain:

- target-level verified success rate;
- compute/resource cost per verified success;
- wall time, model calls, proof attempts;
- duplicate-candidate rate and failure-class counts;
- confidence intervals and paired case-level deltas.

Do not tune on the holdout. Require at least the configured minimum number of
cases, but treat that minimum as a floor rather than proof of statistical power.

## Promotion criteria

The contextual bandit remains advisory until it beats the fixed baseline on
held-out paired cases, does not regress verified success beyond the declared
tolerance, improves cost efficiency or justifies its added cost, and passes
failure review, lineage verification, rollback readiness, and authority checks.
Human approval remains required.

## Iteration sequence

- [x] Identify and reuse the existing episode/evaluation ledgers and bounded
      route/strategy planners.
- [x] Add an explicit, disabled-by-default evaluation contract.
- [ ] Add a deterministic paired benchmark harness using the existing math
      evaluation API.
- [ ] Implement a minimal contextual-bandit selector behind a feature flag.
- [ ] Add unit/property tests for invalid inputs, tie-breaking, determinism,
      cost handling, and no authority expansion.
- [ ] Run the baseline arms; do not claim gains until real results exist.
- [ ] Only then consider online learning or RL fine-tuning.

## Safety invariant

Capability may improve, but authority does not automatically expand. The
selector may rank only actions already admitted by the C++ validators,
capability policy, budget, and sandbox. It cannot modify verifiers, policy
files, credentials, permissions, or promotion gates.
