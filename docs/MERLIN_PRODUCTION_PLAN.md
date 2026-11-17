# Merlin production engineering plan

Plan: MERLIN-PRODUCTION-20261116, revision 1 (pre-implementation).
Status: active engineering; production readiness NOT ESTABLISHED.
Scope: continue the exact source-bound Ideonomy/Hermes/Logos branch, preserving CACE independence and existing registry/outbox architecture.

## Ranked execution order

1. Finish the interrupted scientific operating workflow in the existing PromptCompiler. First reproduce any metadata-binding defects; preserve versioned plans, observation/induction/deduction, bounded Ideonomy/Lacuna exploration, exact-vs-heuristic analogy, skeptical review, and scoped n-ality hypotheses. Verify deterministic prompt identity, bounded envelopes, tamper rejection, durable outbox/replay, unchanged approval boundaries, and no implied scientific qualification.
2. Reconcile the stacked Ideonomy provenance/Hermes/Logos dependency chain. Test exact source and quotation binding, full immutable generator provenance, replay after failure, and idempotency changes. Do not infer that success on a descendant independently qualifies each branch.
3. Implement and independently test the MCFC OS/container supervisor before real external-provider/media dispatch: CPU/memory/PID limits, deadlines, process-tree kill, lease fencing, environment allowlist, workspace/network/secret isolation, streaming caps, and race/cleanup tests.
4. Connect an authenticated, independently operated CACE transport to exact source/artifact identities. Test unavailable transport, wrong signer, wrong artifact, stale source, partial verification, and receipt persistence. Unit-test keys are never production trust roots.
5. Demonstrate one source -> extraction -> Ideonomy -> Logos -> bounded experiment -> independent verification -> canonical artifact/HUD loop, then perform package/install/security/backup/rollback and acceptance checks. Merge/deploy/promote only with explicit approval.
6. Expand math/equation-atlas/CAD/media and held-out self-improvement after the trustworthy path works. Keep research hypotheses, simulations, formal proofs and production capabilities separate.

## Current baseline and constraints

- Working branch: feat/merlin-scientific-operating-workflow-20261116.
- Parent research snapshot: 8b83b4dfd639d0abdd3e9b0a7eb695b193d2c7b3 (PR 176).
- Interrupted workflow module commit: f7cb6f6436e195e10805abe91ecbb37e18119a3b.
- Original prompt_contract.py blob: d1a0a8d7520e163a65fb51fbd69cb29711cd36b9.
- Original event_outbox.py blob: 14cd094db04d1a31d050129eb31b5cbd793d5457.
- Both original local source copies match the Git blob hashes; these are not independent correctness evidence.
- No paid compute, speculative CI, production worker launch, merge, deployment, signing/trust-root mutation or capability promotion in this iteration. Avrea unavailable until 2026-12-01 per saved project constraint.
- Drive reads are available in this session; the earlier handoff's claim that Drive is disabled is stale. No write/backup success is inferred from read availability.
- Accessible handoffs are context summaries, not every prior chat transcript. Record coverage, omissions and stale/missing evidence explicitly.

## Hypotheses and falsifiers for step 1

H1: central compiler injection gives every newly compiled task the same versioned scientific-workflow instructions. Falsifier: any compiler recipient omits the block, changes it silently, or returns an invalid/oversized prompt.
H2: compiled authoritative metadata is bound to the prompt envelope. Falsifier: modifying recipient, task identity, source, authority or approval metadata can pass validation while text still describes another envelope.
H3: adding instructions does not grant authority. Falsifier: a draft task gains tools or a bounded task can publish without independently validated approval.
H4: the existing outbox retains replay/tamper/lease behavior. Falsifier: changed payload is silently replayed, mismatched result accepted, or invalid worker lease acknowledged.

Acceptance: focused deterministic unit/integration tests on actual prompt/outbox modules pass; negative controls reproduce before fixes and reject after; Python syntax compiles; exact source and test hashes and command output retained. Full native/Lean/provider/runtime/production qualification remains not run.
Rollback: revert only this feature branch's changes; preserve immutable historical prompts and queued work. Do not rewrite historical prompt hashes.

## Context sources and evidence hierarchy

Live GitHub source and exact-run evidence outrank historical status text. User intent and specifications guide acceptance; they do not establish correctness. Source pinning -> executed local tests -> exact-head CI -> independent CACE verification -> explicit qualification/promotion are separate levels.

Sources read in this conversation: expert-robot README; PRs 170-177 and exact-run metadata; docs/MERLIN_MASTER_CONTEXT.md and docs/MERLIN_STATUS_AND_ROADMAP.md at 28d13720819651aac565122da953e29d8a4e87ba; Cace-app README, AGENTS.md and CROSS_CHAT_HANDOFF.md; Drive MERLIN_Inductive_Requirements_and_Specifications.md, Full Chats Master Handoff 2026 11 05 (partial retrieved text), and merlin_v27_newest_skill_output_raw.md (partial retrieved text). No claim of an exhaustive repository, archive, or chat review.

## Revision 2 - current continuation checkpoint

Reason for revision: the baseline probe reproduced four accepted metadata/text mismatches, and live source inspection found an existing canonical typed scientific-loop contract. The immediate work was narrowed to compiler admission hardening; no second scientific state machine, registry or evidence store was introduced.

### Implemented and measured

- Source commit 4a78e892bca3f470b08079e18227f381cb1434f6 integrates the pre-existing workflow text module into PromptCompiler and validates the complete runtime-owned preamble before publication.
- Test commit 5b1d2d0226fc9a6abc3d83974ff12cf889330499 adds 27 focused tests. All 27 passed locally on Python 3.13.5 against the actual prompt/outbox modules restored to verified Git blob identities. This is a focused source subset, not a full checkout or full application qualification.
- Task ID, recipient, task digest, authority, approval reference and source metadata must match the rendered preamble. Control-character injection in task/approval headers is rejected. Removing, moving or changing the workflow block is rejected even after recomputing the text hash. Oversized compiled prompts are rejected before publication.
- Real SQLite outbox tests cover persistence/reopen, replay, result mismatch quarantine and worker-lease/independent-approval checks. No real model, cloud worker or CACE verifier was invoked.
- An additional probe using the exact old compiler confirmed acceptance of a historical queued result without rewriting historical prompt bytes. Old compiled envelopes must be recompiled for new publication through the stricter publisher.
- Details: docs/evidence/merlin-scientific-workflow-local-20261116.json. Reproduce with: PYTHONPATH=python python -m unittest discover -s tests -p 'test_merlin_scientific_workflow.py' -v.

### Revised ranking after the observations

| Rank | Work | Acceptance gate |
|---|---|---|
| P0a - implemented locally | Finish scientific prompt integration and fix observed metadata-binding defect | 27 focused local tests pass; remote source/test blobs match tested bytes; no authority expansion |
| P0b - next | Wire the new suite into existing focused CI, test the existing prompt contract on the exact branch and target Python version, reconcile #175 -> #172 -> #176 without merging or triggering unapproved compute | Canonical source-provenance/quotation/replay tests pass on the exact reconciled head; failed, skipped and absent runs remain explicit |
| P0c | Persist the EXISTING scientific_loop.py typed records through the canonical registry/ArtifactRefs; add Hermes episode gates and idempotent append-only plan revisions | Missing observations/predictions/falsifiers/parent plan/evidence references block advancement; failed/null results remain queryable; original task acceptance is rerun after analogical decomposition |
| P1 | Enforce MCFC OS/container isolation before real external worker dispatch | CPU/memory/PID/deadline/process-tree/secret/network/filesystem/output bounds and lease-expiry/cancellation race tests pass |
| P2 | Exercise authenticated independent CACE verification without fabricating credentials or trust roots | Exact source/artifact/signer bindings and fail-closed wrong-key, missing-credential, stale-commit and partial-verification cases pass |
| P3 | Qualify one complete research-to-artifact/HUD path and package/recovery lifecycle | Install, restart, backup/restore, migration, observability, rollback and acceptance evidence; separate explicit promotion approval |
| P4 | Expand math/CAD/media/learning and measured self-improvement | Held-out benefit and capability-specific safety/verification, not feature-count claims |

The canonical scientific method and P1-P7 integration sequence remain in docs/MERLIN_SCIENTIFIC_OPERATING_LOOP_V1.md. This engineering checkpoint supplements that contract; it does not replace it. The existing AGENTS.md and runner/bridge operations documents were inspected and their authority boundaries retained.

### Manual constrained idea-space review

This was a manual alternative review, not a claimed automated Ideonomy or trained Lacuna run. Alternatives were: (A) persona/prompt-only advice, rejected as insufficient runtime enforcement; (B) canonical compiler validation plus deterministic local regressions, selected for the reproduced defect; (C) canonical typed-record persistence plus Hermes coordination, ranked next; (D) a parallel scientific registry/orchestrator, rejected as architectural duplication; and (E) immediate external provider/media execution, blocked by missing isolation/qualification evidence. No numerical claim of exhaustive idea-space coverage is made.

For future Lacuna-inspired candidate search, track coherence, corpus-relative availability and empirical support separately. The historical Drive 6D "alienness" demonstration is not a validated integration of the original Alien Science method. Public method references: https://ideonomy.mit.edu/intro.html and https://github.com/alejandrohdez00/alien-space-of-science . A corpus gap is not global novelty, and model plausibility is not truth. Treat n-ality as a defined, testable representational candidate; require semantics-preserving mappings and a checked resolution for each paradox, not a universal-resolution assertion.

### Live-state corrections and remaining limits

- PR #175 head b934d8344532b27dd69e58a9154c77bc0c24633a has successful CI run 44011084281. Its PR body still says pending; the live run supersedes that text. Success is scoped to that workflow, not CACE or production qualification.
- PR #176 head 8b83b4dfd639d0abdd3e9b0a7eb695b193d2c7b3 has successful runs 44010725986 and 44010726036 in the queried record. It remains draft/unmerged; no production inference follows.
- PR #172 head b3d78ff8ada12947cb53dcdfd13b627e52aee343 remains draft and was returned as non-mergeable; no exact-head PR workflow was returned in the earlier query. Reconcile deliberately; do not force-update another branch or inherit success by assumption.
- The new focused test file has not been wired into an explicit CI step. No CI pass is claimed for this feature branch. Commits use [skip ci]; no manual workflow, merge, deployment, signing, secret mutation or promotion was performed.
- The prompt block requests a scientific_workflow report, but the generic result receiver does not yet validate that report's scientific contents. Typed Hermes gates, independent evidence and held-out behavior evaluations remain necessary.
- Inclusion is proven only for newly compiled PromptCompiler tasks. Other Merlin chat/model paths and future ChatGPT sessions are not automatically covered; map entrypoints and retrieve the durable instructions explicitly.
- Source hashes establish identity, not origin authentication or semantic correctness. Full native/Python suites, package installation, Lean, live providers, CACE and production tests were not run here.

### Defect-class record

Trigger: change valid metadata while retaining another task's text/hash. Root cause: validation checked field shape and selected substring bindings but did not compare the complete control preamble. Preventive control: one canonical preamble renderer shared by compilation and admission, exact prefix equality, single-line controls and compiled-envelope validation. Detection: metadata perturbation, context-planted header, altered/relocated workflow, oversized envelope and publication-negative tests. Adjacent boundary review still needed: direct outbox producers, result admission, other model entrypoints, approval provenance and authenticated transport. This patch does not claim to authenticate a coherently forged whole envelope.


## Revision 3 - private checkout and exact-source CI gate (2026-11-17)

Parent plan: revision 2 at source 5a5cb0b3f1ff614666455b7bc9b212eb81693112. Prior plan text is preserved byte-for-byte. Production readiness remains NOT ESTABLISHED.

### Observations and decision

Authenticated connector reads succeeded for both private repositories. Container Git probes for both repositories failed to resolve github.com; the container also has no GitHub token, SSH agent or configured Git credential helper. A complete Git checkout was NOT obtained. Neither repository was made public, and no credentials or trust roots were created, read out or changed. The safe partial resolution is an exact-source private checkout path in existing CI, not a claim that connector access supplies shell authentication.

The current production feature branch diverges from PR #175 (59 commits ahead, 5 behind in the queried comparison). Content inspection found the complete six-field generator provenance already preserved in candidate envelopes and persistence validation. The newer interface additionally requires runtime-owned provenance before invocation and rejects provider-supplied provenance. Preserve that stronger interface; copying the older #175 provider-response interface would regress the trust boundary. No branch-history merge/rebase or full integration-test success is claimed.

### Implemented change and bounded validation

- Existing CI checks out the exact PR head or push commit with full history and persist-credentials=false, retains read-only workflow permissions and existing test steps, and records event identity separately from actual tested source.
- scripts/merlin_research_stack_gate.py requires Python 3.11 and verifies actual tracked source bytes against the exact Git commit before/between/after the eight fixed suites. It rejects hidden skip-worktree changes, untracked importable source, missing files, unsupported symlinks/submodules and source drift. Each suite has a deadline, bounded streaming log and explicit missing/failed/incomplete/not_run status. A stale previous result cannot be reused as a pass. These are test-runner controls, NOT an adversarial MCFC sandbox.
- The previously omitted scientific-workflow suite is now selected alongside prompt, extraction, knowledge-compression, Ideonomy, Hermes and Logos tests in an explicit existing-CI step. Prior standalone suites remain intact.
- .github/actions/checkout-cace-source/action.yml defines a dormant exact-commit private CACE checkout using an existing caller-supplied protected transport key. It does not provision a key or authenticate a CACE verifier. Use only in an independently approved protected job, never one executing untrusted PR code; do not forward its credential to tests. It has not been invoked.
- The NEW gate's 28 regression tests passed locally on Python 3.13.5 using disposable real Git fixture repositories. This is not execution of the actual Merlin research suites. YAML parsing and 37 shell-block syntax checks passed; Python 3.11 AST parsing passed but is not interpreter execution.
- An actual attempt to invoke the production gate in this container returned blocked because Python 3.11 is unavailable. All eight required suites were recorded as not_run. No CI workflow was dispatched. Evidence: docs/evidence/merlin-source-gate-local-20261117.json, research-stack-gate-local.log, and target-runtime-blocked/research-stack-result.json.

### Updated ranking and acceptance

P0b remains PARTIAL: checkout configuration and the test gate are source-authored/locally tested within the scope above. NEXT: execute the gate on the exact updated branch with Python 3.11 in an approved network-enabled authenticated runner and inspect every suite result; then resolve the remaining branch history deliberately. No other branch's green run substitutes for this evidence. A cross-repository source checkout requires its own authorized transport; the current repository's workflow token is not assumed to grant CACE access.

P0c remains NEXT IMPLEMENTATION: persist the existing scientific_loop.py observation/prediction/plan records in the canonical registry with immutable ArtifactRefs and Hermes episode gates. Require parent-plan and evidence references, preserve failed/null outcomes, and test restart/replay and changed-input rejection. Do not create a second registry.

P1 remains BLOCKED FOR REAL DISPATCH: implement and test actual MCFC OS/container enforcement, including CPU/memory/PID/filesystem/network/secret limits, process-tree cleanup and lease fencing. The focused test runner is not a substitute.

P2 remains UNEXERCISED: independent CACE verifier transport, signer and exact artifact/source acceptance. Existing transport access and local test keys cannot establish independent verification.

P3 remains UNQUALIFIED: one complete research-to-artifact/HUD path, followed by installation, backup/restore, restart, migration, observability and rollback. No production claim until all dependent gates and explicit promotion approval pass.

Rollback: revert only this feature-branch checkpoint; retain prior plans and evidence. No paid/speculative CI, Avrea use before the recorded 2026-12-01 hold, merge, deployment, signing, secret mutation or capability promotion occurred. Context coverage remains the available handoffs/specifications plus task-relevant live source, not every prior chat or repository file. Re-query live state before the next execution.

## Revision 4 - canonical scientific recording and measured regression fixes (2026-11-17)

Parent: revision 3 at `b0cfc03e693d565f4f71b923ad237d496b054b6c`. Earlier revisions are preserved. Production readiness remains NOT ESTABLISHED.

### Observation, decision and implementation

The production feature branch still pointed to the parent commit and no workflow run was returned for that exact head. Local GitHub name resolution remained unavailable and the runtime remained Python 3.13.5, not 3.11. Repeating checkout configuration would not resolve those constraints. The next safe implementation increment was the existing plan's P0c: canonical record persistence and handler-level gates, without external execution.

Implemented `python/merlin/scientific_recording.py` over the existing registry, ArtifactRefs, Hermes stage journal and scientific-loop primitives. It records observations, initial plans, prediction/falsifier sets, completed/failed/inconclusive/not-run outcomes, and immutable parent-linked plan-revision proposals. Semantic identities are journal-bound across task IDs. Exact raw versions, source commit, episode and hypothesis scope are retained. All outputs remain unverified, unqualified and non-promoting. No new database, hypothesis promotion, provider invocation or external tool execution is introduced.

The opt-in `scientific_recording` Hermes handler requires an independent admission callback and matching task/context identities, approvals, leases, refs and budgets. The complete task is bound into durable checkpoints. Replay rechecks sources and output; changed inputs, provenance, checkpoints or results are rejected. This is handler-level integration, NOT automatic default-factory/API activation or a fully qualified HermesWorker/outbox path.

### Measured iteration and regression prevention

The first 37 recording tests passed. Review found that new task IDs could reuse a plan/experiment identity with changed content. Stable identity reservations in the existing journal were added for observations, root plans, experiments and runs; five additional tests cover substitution and missing completed checkpoints. Recording tests now total 42.

Inspection of the existing scientific-loop suite found two negative-test functions below the `__main__` block rather than inside the test class. The unmodified exact source discovered only six tests. Actual baseline probes also accepted NaN predictions when the metric was unobserved or the unit mismatched, and produced a plan-update record with null parent identity/version from an unrelated nonempty mapping.

Corrected test placement; added shared `Prediction.validate()` before all comparison branches; rejected interval overflow, missing/invalid parent plan identity/version, and coerced non-string next actions. The recording adapter reuses the shared validator rather than maintaining competing numeric semantics. The scientific-loop suite now discovers and passes 14 tests. These are narrowly scoped contract fixes, not a claim that all scientific primitives have been qualified.

The final focused run on Python 3.13.5 passed 84 tests (42 recording + 14 scientific-loop + 28 source-gate fixture regressions), with zero failures/errors/skips. The exact registry, ArtifactRef and journal dependencies matched fetched Git blob identities. Python 3.11 AST checks and bytecode compilation passed; Python 3.11 interpreter execution did NOT occur. The CI gate now includes both recording and primitive suites, retaining the prior eight, for ten required suites.

Evidence: `docs/evidence/scientific-persistence-local-20261117.json`, `scientific-persistence-final-tests.log`, and `baseline-probes.json`. Reproduce the focused recording/primitive tests with `PYTHONPATH=python python -m unittest discover -s tests -p 'test_scientific*.py' -v`; run the exact-source research gate only on a complete pinned checkout under Python 3.11.

### Ranking and unresolved obligations

1. P0b remains blocked for target-runtime qualification: obtain the approved authenticated complete checkout, execute all ten research-stack suites on the exact new commit under Python 3.11, and reconcile branch history deliberately. No other branch's success is inherited.
2. P0c is PARTIALLY IMPLEMENTED/LOCALLY TESTED: canonical records and opt-in handler gates exist. Next integrate the real admission policy and HermesWorker/outbox lifecycle, including acknowledgement, lease loss and cancellation/restart races; exercise the actual default runtime composition. Plan revisions are proposals and may branch; no implicit latest plan or approval selection exists.
3. P1 remains required before real worker dispatch: actual MCFC OS/container isolation and resource/secret/network/filesystem enforcement. Recording/input caps and test-runner process cleanup are not a sandbox.
4. P2 remains unexercised: independently authenticated CACE exact-source/artifact/signer verification. Neither registry hashes nor local test fixtures establish this.
5. P3 remains unqualified: the complete research-to-artifact/HUD path plus install, recovery, migration, observability, rollback and explicit promotion approval.

Additional limitations: prerecording an experiment in Merlin does not prove outcomes were unseen; artifact hashes do not authenticate observation truth; lineage inspection is bounded and blocks at its ceiling; canonical registry concurrent file-write behavior still needs supervisor/integration qualification. No claim of universal n-ality paradox resolution or exhaustive idea-space coverage is made.

### Alternative review and skeptical controls

Manual, bounded alternatives were (A) add another store, rejected as duplicate architecture; (B) mutate current plans, rejected because history would be lost; (C) use canonical immutable artifacts plus the existing journal, selected; (D) dispatch real experiments immediately, rejected pending isolation/verifier gates. This was not a claimed trained Lacuna run. The event-log/content-addressing analogy guides the implementation but is not scientific evidence. Correlated-author test bias remains; independent review and the full pre-existing suites are still required.

Rollback: revert only this feature-branch increment and retain prior evidence/artifacts. No workflow dispatch, paid compute, Avrea use before the recorded 2026-12-01 hold, merge, deployment, credential/trust-root mutation or capability promotion occurred. Context coverage is the available handoffs/specifications and relevant live source, not a literal read of every historical chat.


## Revision 5 - real recording-worker lifecycle and atomic completion (2026-11-17)

Parent: revision 4 at `1754d4819d5b6bc0ec2dcc09bf6c2e0a98549011`. Earlier plan text is preserved. Production readiness remains NOT ESTABLISHED.

### Live context and bounded objective

The feature branch still pointed to the parent and its exact-head workflow query returned no runs. The container still could not resolve github.com and had no Python 3.11 interpreter. These observations do not justify making repositories public, inventing credentials or repeatedly dispatching unapproved CI. The selected increment was the existing P0c next step: execute the recording path with the REAL HermesWorker/outbox, test interruption boundaries, and add an explicit opt-in hook to the existing runtime composition.

Context used: the preserved project decisions and available cross-chat specifications, current branch/CI query, exact worker/outbox/registry/journal/telemetry/ledger/runtime source, and the prior scientific-recording patch with Git blob identity checks. This is task-relevant coverage, not a claim to have reread every historical chat or source file. Avrea remains held until 2026-12-01.

### Observation -> deduction -> change -> test

Baseline probes reproduced three defects: acknowledgement failure left a pending task with a completion announcement; approval revoked during a handler still permitted success; and a nonempty string denial was accepted as approval. The required invariant is that a committed completion announcement references an acknowledged exact receipt, while denied/expired authority cannot authorize success.

Implemented atomic receipt plus completion-event insertion in the EXISTING outbox transaction. Worker completion uses that method, binds announcements to the receipt digest, normalizes JSON before lost-reply comparison, and checks literal True for admission and artifact validation. Cooperative checks now include lease expiry and current approval/MCFC policy; retry error paths retain lease-loss outcomes instead of throwing a second lease error. Mutated handler input cannot replace the admitted task's receipt.

The existing runtime now has explicit `include_scientific_recording=False` and calls the tested registration helper only through that flag. The helper uses canonical stores and the same runtime-supplied policies, requires an existing hypothesis/project scope, and never grants approval. The recording handler revalidates at write boundaries. No second registry, scheduler or authority mechanism was added.

Repeated admission exposed unclosed HypothesisLedger connections. A baseline probe retained three connections from three get calls and found all still usable. Canonical ledger methods now explicitly close their connections; a regression checks both successful and missing-hypothesis paths. The unchanged eight-test ledger suite still passes.

### Actual validation and boundary

Final validation: 148 distinct local tests passed on Python 3.13.5, with zero failures/errors/skips. Counts: 35 integration/atomicity, 42 recording, 14 scientific-loop, 10 existing worker, 11 existing outbox, 8 existing ledger, 28 source-gate fixture regressions. The first combined invocation exceeded the tool's 60-second execution limit; five smaller batches completed the unchanged test set. No timed-out invocation is reported as a completed pass.

Integration exercised the real stores, stage journal, worker, delivery leases and receipt path, including an actual local child process exiting after persistence/before ACK; reopening and lease recovery; cancellation after persistence; revocation; expired/reclaimed leases; changed-input and corrupted-source rejection; lost ACK replies; and a concurrent cancellation/commit test showing no half-committed completion visibility.

Full runtime composition is SOURCE-AUTHORED/STATIC-CHECKED ONLY: the opt-in call and default-off flag were AST checked, but its complete import graph, deployed policy services, API, HUD and service start were not executed. Tests use explicit fixture approval/lease policies, not a real operator/MCFC authorization service. The local work remains a focused source subset, not a full repository checkout. Python 3.11 syntax parsing passed but target-interpreter execution did not occur.

Evidence: `docs/evidence/scientific-worker-local-20261117.json`, `scientific-worker-final-tests.log`, and `MERLIN_SCIENTIFIC_WORKER_INTEGRATION_V1.md`. The exact-source gate now requires fourteen suites, retaining all earlier suites. No CI run, CACE verification, OS sandbox or production qualification is claimed.

### Revised ranked queue

1. P0b remains the next QUALIFICATION gate: complete authenticated checkout, run all fourteen suites under Python 3.11 on the exact new commit, reconcile the branch stack, and inspect each result. Do not inherit another branch's pass.
2. P0c is WORKER-INTEGRATED/LOCALLY TESTED within the scope above. Next execute the complete runtime/service/API composition with real independently supplied policies; review adjacent completion producers and legacy acknowledgement callers. Recording completion is not experiment success or scientific verification.
3. P1 remains blocking for real external execution: OS/container CPU/memory/PID/network/filesystem/secret limits, monotonic deadlines, process-tree cleanup and lease fencing. Cooperative policy checks and a local SQLite transaction do not provide this isolation.
4. P2 remains unexercised: real CACE transport and signer/exact source/artifact tests. Audit end-to-end promotion paths; low-level ledger status APIs are not themselves a verifier gate.
5. P3 remains unqualified: complete research-to-artifact/HUD, installation, migration, restart, backup/restore, observability, rollback and explicit promotion approval.

Registry persistence/journal completion and outbox acknowledgement are not one distributed transaction. Cancellation or lease loss can leave immutable records for reconciliation, and a check cannot forcibly stop an uncooperative process. Final external approval can change after a cooperative check; independent service fencing remains an obligation. No automatic deletion or history rewriting was introduced.

### Manual constrained alternatives and skeptical controls

This iteration used a manual idea-space enumeration, not a claimed trained Ideonomy/Lacuna model run: (A) completion before ACK, rejected by the reproduced false-success event; (B) completion after ACK in a separate write, rejected because a crash can lose the announcement; (C) receipt plus announcement in the existing local transaction, selected; (D) another registry/message subsystem, rejected as duplication. The selected mapping is scoped to one SQLite outbox; it is not an analogy claiming distributed exactly-once execution. Correlated-author/test bias remains, so existing regressions, negative controls and eventual independent review remain mandatory. No exhaustive novelty or universal n-ality paradox-resolution claim is made.

Rollback: revert this feature-branch increment while retaining historical records/evidence. No workflow dispatch, paid compute, Avrea use, merge, deployment, signing, secret/trust-root mutation or promotion occurred. Re-query the live head and evidence before the next execution.
