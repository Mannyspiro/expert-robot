# Merlin Studio continuation — 21 November 2026

**Status: locally implemented and tested; GitHub publication blocked by automatic approval review.** No new source commit, merge or deployment was accepted. The production host was not changed and Avrea was not used.

This is an append-only checkpoint under the existing [master plan v6](https://github.com/Mannyspiro/expert-robot/blob/6d4b5a4a3a5b81210d192554774316c04d2d88ff/config/merlin/production-master-plan.json), plan `MERLIN-PRODUCTION-MASTER-20261117`. It does not replace that plan or complete its 45 tasks. The machine-readable companion is `config/merlin/plan-updates/20261121-studio-runtime-browser-continuation.json`.

## Source coverage and direction

The continuation reconstructed the 404-file source inventory for PR #194 at `5b1624e062a7687fe9f84eb97bfa75a5f621c6a6`; preserved originals and Git blob identities distinguish the baseline from subsequent local edits. Current main was observed at `4c8491d23410c956779c76c6d733501df66e7f95`. Browser work remains a separate successor to PR #193 at `d4903129f2eba847658bfd4d6c0b68424d013723`. The prior `Merlin_Studio_Portable_Alpha.zip` was recovered and inspected as the starting interface artifact.

The retained direction is Experimental autonomy, a portable Merlin chat interface, useful offline operation, optional internet research and computer tools, a zero-dollar external model budget, and exclusion of ChatGPT account/site access. Context recovery covered the accessible handoff, source, plans and evidence; it does not establish access to every raw conversation or complete semantic review of the historical document catalog. Private conversation bodies are not copied into this update.

## Implemented and measured

**Studio.** The local server now provides persistent conversations, saved settings, a workspace editor, Activity records and an agent/tool loop. Offline commands support help, file listing, reading, writing and explicitly approved Python execution. Conversation and action evidence use the existing Merlin registry and immutable ArtifactRefs. Large UTF-8 results retain full canonical bytes while the Activity view uses a bounded preview. Restart preserves history and marks unfinished actions interrupted without replay.

Script approval binds exact source bytes and is consumed once. Changing a script, cancelling its request or disabling Python while approval waits prevents execution. Scripts execute from the approved snapshot with bounded runtime/output and filtered inherited environment variables. Workspace paths, symlinks and nonregular files receive explicit checks. The server checks local Host/Origin, session tokens, JSON framing and body sizes. These controls do not create an OS sandbox.

**Runtime recovery.** Recovery transactions retain unresolved markers across restarts, use per-subsystem cooperating-process leases and cannot accept stale completion IDs. A failed evidence write cannot prevent the rollback attempt. The JSONL process connection bounds requests, responses and shutdown. A separate recovery adapter demonstrated restart after killing the actual C++ protocol worker and rejected a replacement that failed its reference check. The C++ result covers the health protocol, not inference or the full research engine. Studio does not automatically attest that its host is sandboxed.

**Research transport.** Public HTTPS retrieval pins a validated numeric address while verifying TLS for the URL host, applies cumulative body and total-time budgets, validates redirects and retains raw source receipts. It is HTTP retrieval without JavaScript rendering. Local-model transport excludes environment proxies and redirects, bounds framing and total duration, and validates chat/tool responses. Actual public DNS access was blocked in this environment; no successful new public-source retrieval is claimed.

**Separate native-browser repair.** The producer now accounts for resource bytes before reentrant callbacks and emits resource records in request order. A distinct derivative of the saved arXiv capture passed the strict importer in a temporary local registry and fresh-process readback. The 42 original files remain unchanged. Reconstructed accounting is labeled as derived metadata; it is not a new browser observation or host acceptance.

## Evidence and limits

| Scoped suite | Passed | What it establishes |
| --- | ---: | --- |
| Runtime/recovery | 43 | Fault, concurrency, protocol and restart controls; includes 3 actual C++ checks |
| Unchanged research retrieval | 4 | Existing focused regression suite |
| Studio integration | 35 | Real local HTTP, SQLite/artifacts and Python subprocesses; synthetic model tool loop |
| Public-web and local-model transport | 29 | Transport boundaries, deadlines, framing and negative controls |
| Browser accounting successor | 41 | Producer controls and reentrant-accounting regressions |
| **Total scoped test cases** | **152** | Separate suites and source scopes; not whole-system qualification |

UI verification separately exercised **11 groups through 72 actual HTTP requests, including 13 mutations**, using the real UI JavaScript and a minimal DOM test double. Chromium could not start because Unix socket creation was denied, so rendered visual quality was not verified.

The final app archive is `Merlin_Studio_Portable_Alpha.zip`: **98,745 bytes**, SHA-256 `3bb6e3e58f6bd584d1992431fc1f83a9d6e9ce539e179a0817e709887c5f4f2a`, with 30 entries including its manifest. Packaging verification covers 10 groups for deterministic construction, excluded state/credential canaries, tamper rejection, extracted startup and native protocol checks; these groups are separate from the 152 test-case count. This archive includes a Linux x86_64 C++20 protocol binary built with g++ 14.2.0 and glibc 2.41. It requires compatible system libraries and is not a universal binary. Durable app/source/evidence file saving was pending at this checkpoint; GitHub publication remained blocked.

Evidence destinations are `docs/evidence/merlin-studio-continuation-20261121/{runtime,studio,ui,transport}/` and, in the separate browser overlay, `docs/evidence/merlin-browser-ledger-repair-20261121/`. The runtime and Studio manifests pin source hashes, commands, results and failed attempts. Originals, native recovery ledgers and failed differential runs are retained.

The retained failures include nine recovery regressions against the original implementation, the original blocking process read, browser-accounting failures, initial script-binding test changes, the slow-model/port-zero defects, and the first deadline repair's closed-socket regression. Positive ordinary-response checks caught that regression before final acceptance. The retained-capture helper's original serializer mismatch is preserved alongside the separately reviewed correction.

Python 3.10 or newer is required and is not bundled. No model weights or inference runtime are bundled or qualified by these tests. Windows/macOS launch, desktop automation, Windows descendant cleanup, clean-machine offline installation and full research-engine compilation remain unverified. The model tool loop used declared fixtures. Full-host Python privileges, absent OS sandboxing and unqualified desktop behavior remain visible in capability reporting.

## Master-plan progress overlay

| Track | Progress within this checkpoint | Remaining boundary |
| --- | --- | --- |
| P00 | Local worker fault/restart/rollback evidence | OCI service, reboot and off-host recovery gates remain open |
| P01 | Exact source recovery; durable source/artifact identities | Historical semantic review and general retrieval quality remain open |
| P02 | Local request boundary and exact action grants | No OS isolation or broader identity qualification |
| P04 | Bounded local orchestration, worker limits and cancellation | Generic Hermes/MCFC/provider routes are not completed |
| P07 | Chat/workspace/Activity connected to actual durable state | Visual, desktop, Forge, voice and broader learning acceptance remain open |
| P08 | Local model adapter and optional supplied-runtime launch path | Real model/hardware baseline and efficiency comparisons remain open |
| P09 | Public-source transport and browser-accounting repair | New research findings, mathematical claims and discovery remain unestablished |

Simplex is deferred because no measured allocation-optimization problem was evaluated. N-ality is applied only as separate availability, integrity, authority and verification axes. Continuum modeling is deferred because bounded timing controls do not establish an interpolated performance model. Fuzzy logic is not applied to Boolean approval or integrity gates.

## Publication and next acceptance gates

Two publication attempts were rejected by automatic approval review. Existing private-repository access was verified, but the reviewer could not accept recovered prior-chat standing permission as sufficient end-user authorization for uploading the source, tests and detailed project evidence. The blocked operation is recorded; no alternative route was used to bypass it.

1. **Complete publication through the permitted approval path.** Preserve the prepared source/evidence, reconcile the target heads, publish only when accepted, and run required CI on the resulting exact commit. Keep the browser successor separately identified.
2. **Validate an actual local model on a clean offline machine.** Pin runtime/model hashes and license, perform a real chat/tool task, verify the result, restart and recover history, and measure hardware/resource needs within the existing budget.
3. **Finish native-browser acceptance.** Inspect the retained OCI state first, retain the original failed capture, and use the two remaining original NASA/GitHub attempts only through the established host controls. Gateway/handoff and actual source publication remain pending.
4. **Qualify desktop and platform packages.** Exercise approved desktop actions, cancellation and process-tree cleanup on the target operating systems, then verify a clean extraction and startup. Package or signing claims require their own evidence.
5. **Resume provider and domain work.** Bind real coder/evaluator identities, run a held-out baseline/candidate assessment, and continue native CAD/wiring/simulation and mathematics work with task-specific independent references. Preserve Parallax, xenomaths, n-ality, simplex, glyphs and other cataloged ideas without treating this software checkpoint as a research discovery.
