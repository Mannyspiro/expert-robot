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


## Independent offline receipt audit

A separate verifier at `scripts/verify_autonomous_research_receipt.py` reads
the policy, one saved receipt, an **independently supplied full source commit**,
and the experiment module bytes from an exact checkout:

```bash
python3 scripts/verify_autonomous_research_receipt.py \
  --root . \
  --receipt autonomous-research-artifacts/research-episode.json \
  --source-commit <independently-verified-git-commit-sha>
python3 -m unittest discover -v -s tests -p 'test_receipt_verifier.py'
```

The verifier is no-execution/no-network. It checks exact schema and policy,
source commit identity, experiment module SHA-256, next-route consistency,
episode identity, bounded size, falsified authority flags, and fixed evidence
summary shapes. The Python unittest suite provides six offline regression
groups including altered source bytes, hashes, proof flags and symlink input
rejection. The verifier is also a separate step in the proposed
`autonomous-research-operations.yml` workflow. The tests ran locally against
byte-identical committed sources; **GitHub-hosted CI remains unverified** because
recent PR jobs failed before reporting execution steps.

**What passing does *not* prove:** A SHA-256 digest without a trusted external
attestor does not establish that the experiment ran. The verifier has no
original producer output to independently recompute `result_sha256`, cannot
prove the science, cannot perform a Lean kernel check or CACE certification, and
cannot authorize RSI promotion. Treat a structurally consistent receipt as
a well-formed *claim*, not trusted or independently measured scientific evidence.


## Exact-Git-checkout source binding (2026-10-10)

The offline verifier now checks local Git HEAD against the independently
supplied 40-character source commit and verifies the policy file, producer
module, and verifier file byte-for-byte against the committed Git tree. It
uses local git rev-parse and git show operations, without network or writes.
Edited source, incorrect HEAD, or a missing Git worktree fails closed.

Eight standalone local regression tests passed, including mismatched HEAD,
modified module or policy, and missing Git worktree. This only strengthens
provenance consistency. It does not certify an experiment, a Lean theorem,
a CACE numerical result, or autonomous RSI promotion.

GitHub-hosted Actions failures currently occur before a runner is assigned:
run 38030654840, job 114150708727, has an empty runner_name and steps list.
This does NOT show an application test failure. Possible causes include the
private-repository Actions quota, spending restrictions, Actions permission
configuration, or a GitHub provisioning incident; none are verified yet.
Review GitHub account billing/Actions usage and repository Actions settings
without purchasing minutes or increasing any spending limit. Do not blindly
rerun the blocked jobs until the provision issue is understood.

The exact-tree check additionally includes the research-cycle driver script,
so a modified orchestrator cannot be hidden behind an otherwise unchanged
producer-module and policy hash. A mutated-driver negative control passes
in the standalone offline test suite.
