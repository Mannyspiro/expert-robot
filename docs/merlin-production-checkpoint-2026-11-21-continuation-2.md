# Merlin production engineering checkpoint — 2026-11-21, continuation 2

Parent plan: docs/merlin-production-checkpoint-2026-11-21.md. This is an additive checkpoint, not a claim of release readiness.

## Observed implementation delta
- 58306700de53e7bd23c61cc047206ecb000ff16a: parent cannot finish while child remains running; block reason must be a nonempty string.
- 4a9cdf0b46fc8a757261b19feda229cce7791407: two regression tests for these cases.
- b5ac455a0820275e045d642b52b24b491ab80bc5: bounded deterministic dependency-ordering graph tool, no execution authority.
- 6826823964acb361ecf9e64009f5739569e77d99: dependency-order regression tests.
- Local, isolated graph module fixture: four unittest methods passed in Python 3. This verifies the local fixture only; exact committed repository integration remains unverified.
- Existing /mnt/data/merlin_persistence_check fixture: five old persistence unittest methods passed, but this fixture is stale and cannot establish latest-revision correctness.
- Git clone failed in the local container because github.com DNS resolution was unavailable. GitHub connector file operations still worked.

## Scientific reframe
Original problem: ensure nested plans respect prerequisites and cannot claim completion while work remains active.
Analogue: finite directed graph with edges prerequisite -> dependent and a state-transition automaton.
Preserved invariants: each prerequisite precedes dependent; cycles/missing nodes rejected; active children prevent terminal parent completion.
Transfer scope: exact for finite declared graph and implemented coordinator transitions; does not prove agent/runtime execution or distributed scheduling.
Falsifier: a cyclic graph accepted, a prerequisite ordered after dependent, or a parent completed with a running child.
Controls: empty graph, independent nodes, known acyclic graph, malformed types.
Bias check: passing isolated fixtures is not evidence of passing the entire application; retain distinction.

## Ranked next tasks and acceptance
1. Obtain exact branch revision in a complete checkout using approved route; run all Merlin loop, graph and tool-reframing tests and save SHA-bound logs. No CI dispatch without verified $0 eligibility.
2. Integrate graph validation into coordinator only after compatibility tests for existing dependencies and parent ordering; test no false-positive cycle detection.
3. Add transaction-level persistence guards and fault injection (partial write, interrupted process, duplicate checkpoint) against canonical evidence ledger.
4. Audit all workflows and runner labels, not just main CI; prevent Avrea use until December 1 and any billable Actions execution without approval.
5. Verify offline Studio model/UI interaction, restart and persistent session against real local runtime.
6. Build and independently extract/test portable ZIP, then review PR chain and release gate.

Math lens review: simplex not applicable to discrete scheduling; n-ality applied to distinct dependency, containment, temporal and authorization axes; continuum deferred because no continuous model is needed; fuzzy not applicable to Boolean integrity gates.
Decision: continue small reversible changes with negative tests. Release gate CLOSED; no merge or deployment.
