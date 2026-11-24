# Expert Robot / CACE checkpoint — 2026-09-26

## Resume here

This change starts from `main` at `6f747f90b6229adfe319d498e31d248ce084704f`.
Existing draft PRs #2–#16 are separate work and must not be edited as a side effect.
Save each useful, locally verified increment in this draft PR before expanding scope.
Open another PR for a distinct deliverable. Do not wait for an entire research phase.

## Current implementation

- `python/cace_bridge.py`: asynchronous dispatch and one-shot collection using the existing CACE deploy key inside Actions. No waiting/polling loop.
- Each request has a new branch, a full Expert Robot source commit, a full CACE base commit, and a receipt saved before the push.
- A fresh CACE dispatch tree contains only the request and the capability workflow; it does not inherit unrelated CACE workflows.
- The self-hosted CACE lane observes tool availability, installed Lean versions, cache presence and free disk. It does not execute candidate code or download tools.
- Hosted dispatch/publish are disabled by default. Account-specific, fresh allowance evidence and platform zero-overage enforcement are required before live use.
- Capability observations never confer theorem verification or promotion authority.

## Verification and unresolved work

`python3 tests/cace_bridge_test.py` passed 17 local tests on 2026-09-26, using disposable Git repositories: round trip, retries, exact request binding, preservation of main, malformed/tampered evidence, transport failure, and quota refusal.

This is a draft checkpoint. Live dispatch, CACE execution, publication, return-key access and hosted CI have not been qualified by this change. Checkpoint commits use `[skip ci]` to avoid spending unknown GitHub allowances. Local tests are not reported as hosted CI success. Review workflow syntax and wire these tests into the existing CI before making the PR ready.

## Resource constraints and new feedback

- User reports **1,000 Avrea credit minutes remaining for September 2026**. This is an observation, not a fresh provider balance or authorization to spend all of it.
- Preserve Avrea for targeted qualification where local/CACE checks cannot supply evidence. Confirm the credit multiplier and reserve the worst-case charge before a run; use a short timeout and one job. No five-variant reruns of an already saturated benchmark.
- User reports 14% remaining in the current ChatGPT window. Prefer bounded tasks, concise output, batched independent reads, small logs and this checkpoint over repeatedly retrieving the entire project history. Do not promise a specific credit saving or unattended continuation after the window ends.
- Railway access is authorized within free resources. Its connector lists a workspace but does not establish remaining allowance. No Railway deployment is justified by this transport task.
- User reports a deploy-key secret in Cace-app for the return route to Expert Robot. Its name and scope are unverified. Use it only inside its intended trusted workflow; never print or export private key material. The current collector uses the existing outbound read path, so this key is not needed for the first probe.
- Base44 and Vercel remain available options; allocate no service without a concrete role and verified free limits.

## Newer work in the other project chat

Live GitHub inspection found PRs #17, #18, #19, #21, #22 and #23 merged into `feat/reuse-refactored-fishstick`, not `main`. PR #20 was closed and superseded by #22. Do not confuse the small mainline baseline with this integration branch.

That branch includes a bounded CACE tool broker, non-promoting generation evidence, deterministic routing, required verification gates and a hardened local headless reasoner. PR #23 prevents CACE-native workflow passes from qualifying Expert Robot source. Its executable cross-repository capability uses the pinned source-bundle bridge. Broker run 36293212076 and headless contract run 36292814281 both passed at their exact PR heads.

This asynchronous capability-only prototype is a separate draft checkpoint, not a replacement for that broker or proof bridge. Reconcile it before adoption. A capability observation is not candidate qualification. The other chat reports removed benchmark leakage and subsequently indistinguishable variants on five holdout cases; no repeated measured RSI gain was established.

## Ranked next increments

1. Preserve this prototype and reconcile it with PR #23's source-bundle contract. Prefer the existing integration path over a second architecture.
2. Demonstrate one complete bounded candidate cycle: proposal, exact source verification, generation evidence, required-gate handling, fresh hidden evaluation and external promotion decision. Verify live inference separately from contract mocks.
3. Replace the saturated five-case evaluation with a fresh sealed set and deterministic baselines. Record success, proof attempts, model calls, runtime and charged credits.
4. Replay the accepted generation and use it to attempt another improvement under the same authority and budget. Distinguish changes proposed by the system from changes supplied by the outside coding assistant.
5. Qualify the exact CGA identity from PR #16 through pinned Lean and axiom audit, then expand reusable theorem/skill memory for measured gains. Broader AGI and sustained RSI remain unverified.

The useful notebook material is the CGA distance/null identities plus falsifiable regression witnesses. PGA embeddings, quadric projections and collision claims remain quarantined until independently specified and checked.
