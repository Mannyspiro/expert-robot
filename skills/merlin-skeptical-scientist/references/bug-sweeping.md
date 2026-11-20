# Just-in-time repair and defect-family architecture

Design for localization:
- Give boundaries typed contracts, explicit ownership/invariants and structured failures.
- Separate pure domain/policy logic from IO, providers, runtime and approval adapters.
- Bind source/schema/config/data/environment identities; invalidate dependent evidence when assumptions change.
- Expose bounded diagnostics with stable task/run/artifact IDs; exclude secrets/raw private context.
- Keep contract/negative tests, replayable fixtures and targeted fault injection near boundaries.

For each defect preserve:
1. Trigger, smallest reproducer, expected and observed behavior.
2. Violated invariant, defect family, root cause or unknown.
3. Authorized repair scope, changed nodes and affected dependency closure.
4. Search rule and sibling locations checked, including counterexamples to overbroad rules.
5. Smallest root-cause change, rollback and evidence-preservation path.
6. Regression, relevant independent checks and preventive guard that fails on the original defect.
7. Actual results, exact source/environment, residual risk and follow-up.

Observed Merlin examples:
- A token lacked Actions read for the validation lookup: retain the gate and add only the required read.
- Restrictive umask could hide release/config directories: explicitly set modes and test restrictive umask.
- A working directory could shadow imports: bind verified source/import paths and test hostile working directories.

Re-read current code/evidence before applying a historical repair. Similar appearance alone does not establish the same defect. Keep proactive actions within actual authorization, evidence and rollback feasibility.
