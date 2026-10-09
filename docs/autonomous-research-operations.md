# Autonomous Research Operations — bounded pilot

## Objective

Operate a small, reproducible research cycle without manual prompts: select one
registered toy question, run its exact or differential experiment, screen its
counterexamples, retain source/module/experiment/policy hashes, and suggest the
next question. This is an **observation pilot**, not an independently qualified
autonomous scientific researcher or a self-modifying agent.

The route is source commit + UTC date + trusted policy, followed by fixed
task selection, local experiment, independent assertions, SHA256 evidence
receipt, and next task recommendation.

The four initial routes are exact reaction conservation, CRNT deficiency and
weak reversibility, enzyme steady-state counterexamples, and an offline toy
parser differential test. Only fixed entrypoints execute. Papers, webpages,
LLM suggestions and incoming records cannot select code or grant permission.

## Local reproduction

Run tests/autonomous_research_operations_smoke.py with Python, then execute
scripts/run_autonomous_research_cycle.py with --source-commit equal to a full
Git SHA and -o pointing to a fresh artifact path.

An optional --previous JSON receipt can suggest the next registered route
only if its repository, policy, SHA, date and status match. The prior receipt
is low-trust planning input, NOT a cryptographic independent attestation.
Without it, deterministic UTC-day rotation covers all four routes.

## Scheduling and access

The proposed GitHub workflow starts one five-minute-budget GitHub-hosted job
daily at 09:23 Phoenix time. IMPORTANT: GitHub schedules only execute after
the workflow is reviewed and merged into the repository **default branch**.
PR events can smoke-test it if a runner is available. The pilot uses contents:
read permissions, checkout without persisted credentials, no repository writes,
no code mutation, no external network from its experiment, no subprocess
execution, no credential fetching, no Avrea allocation and no promotion.

GitHub Actions on PR #63 has also shown jobs failing before steps begin.
Do not claim scheduled autonomous operation until at least two independent
exact-head episodes have completed with retained artifacts.

## Evidence and next stages

One passed toy experiment is not a Lean theorem, a validated biological
model, a CACE residual certificate, a measured optimization or permission for
RSI promotion. Each still requires independent qualification and the unchanged
collar, rollback, scope, compute and human-authorization checks.

Ranked next work:
1. Restore CI runners and verify two scheduled observations with exact SHAs.
2. Authenticate and ingest prior-run artifacts as read-only, bounded memory;
   de-duplicate copied lineage and retain failed experiments.
3. Add licensed, SHA-pinned public research data without letting it control tools.
4. Feed interesting failures to the existing math-mining and Lean proof pipeline.
5. Match CACE source and solver residuals to formal assumptions, then benchmark
   sealed baseline/candidate holdouts before any RSI recommendation.

The project completion estimate remains 22/100 and autonomous operations
remains 0/5 *verified* points until scheduled execution is observed.
