# Merlin production plan — verification and continuation checkpoint (2026-11-21)

Parent: existing production plan and PR #195; this is an append-only checkpoint, not a replacement for prior plans.
Repository: Mannyspiro/expert-robot
Branch: merlin/release-gate-evidence-20261121
Last inspected source commit: 9723256e304807cfe1feb3454329eb558e0acfc9
Decision: release gate CLOSED; no merge, deployment, or promotion authorized.

## Constraints
- No Avrea runner before 2026-12-01. Thereafter use only with explicit, bounded limits.
- No intentionally billable GitHub Actions runs without prior approval. GitHub-hosted ubuntu-latest is not automatically free for private repositories.
- Do not dispatch CI until repository visibility, account billing entitlement, remaining included minutes, and runner availability are verified.
- Keep sensitive keys and private user context out of CI artifacts and repository commits.
- No autonomous authority escalation, unbounded retry, or unreviewed release.

## Observations and competing explanations
- PR-associated workflow runs at source 9723256 were reported failed: CI 44971929789; release reporting 44971929787; portable staging 44971929924; runner diagnostic 44971929904; self-healing 44971929785.
- Main CI job 137053392296 and runner diagnostic 137053392407 returned null steps/logs through connector. This is insufficient to attribute root cause to source code, runner provisioning, or billing.
- Main .github/workflows/ci.yml currently uses ubuntu-latest but has automatic PR and main push triggers.
- python/merlin_loop_persistence.py reconstructs hierarchy before applying restored state; tests include independent-process restart. Exact updated revision has not been independently executed in a full checkout.
- Existing scripts/run_merlin_offline_ci.sh requires clean complete checkout and emits logs/hashes; no complete-checkout execution evidence currently available.

## Ranked continuation loop
1. **Cost and CI safety gate** — read repository visibility and GitHub Actions billing/usage settings using authorized account tools; inventory all workflow triggers/runner labels. Acceptance: written $0 eligibility or no dispatch. No speculative paid execution.
2. **Exact-revision Python verification** — obtain complete Git checkout at a recorded SHA, execute `python3 -m unittest discover -s tests -p 'test_merlin_loop_*.py' -v` locally without GitHub Actions; preserve stdout, stderr, exit status, Python version and source SHA. Acceptance: all tests pass; failures are investigated and regression added.
3. **Independent restart challenge** — launch fresh Python interpreter, restore parent/child interruption, test corrupted and inconsistent checkpoints. Acceptance: interrupted work blocked, tampering rejected, no silent resume.
4. **CI provisioning isolation** — inspect job diagnostic, runner configuration, permissions and billing independently of code. Acceptance: evidence distinguishes pre-step provisioning failure from executed test failure; no paid rerun.
5. **Offline Studio vertical slice** — exact source startup at 127.0.0.1:8771/studio, local model route, persistent session, restart and offline interaction. Acceptance: independent HTTP/UI and restart evidence, no mock substituted for production runtime.
6. **Portable ZIP** — build from clean SHA, extract into fresh directory, start without network, verify manifests/hashes, security boundaries and data restoration. Acceptance: documented clean-machine execution and reproducible package.
7. **Release gate** — reconcile PR chain, review code/security and all test evidence, then request approval before merge/deploy. Acceptance: explicit authorization and recorded verified artifacts.

## Scientific protocol
Question: can Merlin run a bounded plan/research/subloop lifecycle across restart without fabricating success or charging CI?
Prediction: an interrupted running loop restores blocked; a passed parent cannot contain incomplete children; tampered ledger fails verification.
Falsifiers: any silently resumed interrupted work, accepted inconsistent checkpoint, unverifiable source identity, or a paid/unapproved CI dispatch.
Method: smallest local tests first; independently compare state/evidence and record negative cases. Preserve failures.
Stopping rule: stop on unknown cost eligibility, missing checkout, missing evidence, or violated authorization boundary.

## Lens and bias review
- Simplex: not applicable to Boolean authorization; no relaxation.
- N-ality: apply independent axes of cost, execution, integrity, functionality, and authority; do not collapse to one readiness score.
- Continuum: deferred; resource usage can be measured once billing data is accessible, not assumed.
- Fuzzy: not applicable to binary release or permission gates.
- Bias risk: repeated CI failures could anchor on code failure despite null job steps; distinguish provisioning and execution with direct evidence.
- Idea-space: bounded alternatives [local complete-checkout tests, free-eligible GitHub-hosted CI, authorized self-hosted runner]; no exhaustive search claimed. Choose local tests first because cost and authorization are explicit constraints.

## Next checkpoint
Read remaining workflows and repository settings; execute exact-revision tests locally when complete source is available. Append actual run IDs, exit codes, environment and hashes. Do not claim passing CI or release readiness from code inspection alone.
