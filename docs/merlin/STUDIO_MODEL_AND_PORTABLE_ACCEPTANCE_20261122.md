# Merlin Studio real-model and portable ZIP acceptance — 2026-11-22

**Scoped production engineering evidence, not a release approval.** Canonical [master v6](https://github.com/Mannyspiro/expert-robot/blob/6d4b5a4a3a5b81210d192554774316c04d2d88ff/config/merlin/production-master-plan.json) still has ten tracks, 37 original tasks and eight extensions. All previous source/evidence records remain in place. [Append-only plan revision](../../config/merlin/plan-updates/20261122-studio-model-portable-acceptance.json).

## Exact real-model acceptance

[OCI ARM64 GitHub Actions run 45024776511](https://github.com/morganaspim/Cace-app/actions/runs/45024776511) **passed**, retaining [artifact 14754694449](https://github.com/morganaspim/Cace-app/actions/runs/45024776511/artifacts/14754694449). The source bundle was pinned by Git blob, exact source commit and UTF-8 byte count; the original 36-source-member archive was checked before applying six explicit source overlays, from Merlin product overlay commit `00d31a5d4a357888cae32ec23f8b567eb6696642`.

- The existing local `llama-server` and Qwen2.5 Coder 1.5B Q4 model were used inside an unprivileged, loopback-only network namespace. Runtime binary SHA-256 `af4c10f1f4a1e7f0878dc9b3896bb742f65170861276ef04ddecdf2a9be3cd82`; model SHA-256 `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`. The existing provider was not modified.
- The exact previously inspected CPython 3.11.18 ARM64 archive was staged privately; executable SHA-256 `6cfad927461ace659b09716fad2efa828c6a4b084b7be8181c3982a9f36f464c`. There was no system Python replacement or privileged installation.
- The native Studio chat loop performed **two real model-generation calls**, answered two independently specified arithmetic reference checks correctly with `42`, and persisted four messages. The same conversation was recovered after a server restart. The previous session token was rejected. Both Studio and model processes were stopped and temporary staging was removed.
- The explicit CPU profile used `max_output_tokens=64`, `model_timeout_seconds=120`, one agent step, and no Python/desktop/connected Internet tools. Total measured episode time was **51.768 seconds**, not a calibrated latency/quality distribution.
- The exact product settings include default **45 seconds**, optional **10–120-second** model deadline and **16–2,048** maximum output tokens, with typed validation. The default 45-second bound remains unchanged for users who do not opt in.
- [GitLab pipeline 3099608116](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099608116) passed eight focused Python budget/deadline/UI contract cases and JavaScript syntax on product commit `00d31a5d4a357888cae32ec23f8b567eb6696642`.

This is real inference and durability evidence under a single narrow configuration. It is **not** an intelligence benchmark, general model capability qualification, actual tool-selection success, distributed deployment, or a production release.

## Reproduced failure-and-repair chain

| Observed run | Actual failure | Repair / boundary |
| --- | --- | --- |
| [45021792856](https://github.com/morganaspim/Cace-app/actions/runs/45021792856) | Controller assumed absent `/usr/bin/python3.11` | Stage verified interpreter privately without touching host Python |
| [45023562308](https://github.com/morganaspim/Cace-app/actions/runs/45023562308) | Controller expected hyphenated 36-character IDs, Studio persisted 32-hex IDs | Corrected route/response checks; three explicit regression tests |
| [45023783538](https://github.com/morganaspim/Cace-app/actions/runs/45023783538) | Default 45-second model timeout hit in a real CPU call | Preserve failure receipt and inspect timeout/prompt confounders |
| [45024308876](https://github.com/morganaspim/Cace-app/actions/runs/45024308876) | New source overlay pins used character count, not UTF-8 bytes | Pinned exact UTF-8 sizes and Git blobs |
| [45024428754](https://github.com/morganaspim/Cace-app/actions/runs/45024428754) | 64-token output budget still hit 45-second response deadline | Added validated explicit 120-second CPU profile, default unchanged |
| [45024776511](https://github.com/morganaspim/Cace-app/actions/runs/45024776511) | None in scoped acceptance | 2/2 actual replies correct, four messages retained, restart and cleanup verified |

Earlier failed artifacts remain intact. No failure was converted into success by weakening its negative controls.

## Reproducible offline ZIP test

[GitLab pipeline 3099631693](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099631693) / [job 18257947997](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/jobs/18257947997) **passed** on exact source commit `8458ed77154cf92fad0fd6231acad4b6499d4d3a`.

- Rebuilt the allowlisted `Merlin_Studio` ZIP twice from identical source/environment; the two archives matched byte-for-byte.
- Included and verified the Linux x86-64 C++ **protocol health worker only**. The worker is not a model runtime or general Merlin engine.
- Verified ZIP inventory, member sizes, digests, modes and extracted files against `PACKAGE_MANIFEST.json`.
- All **36 shipped Studio integration tests** passed after extraction.
- The independent `scripts/merlin_portable_zip_smoke.py` started a real local HTTP server from a newly extracted ZIP, used `/api/health`, made a conversation, completed `/help` offline, restarted the process, recovered persisted messages, rejected the old token, and cleaned up its temporary state. The test made **zero external model/network calls**.
- [Download the tested Linux x86-64 Studio ZIP](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/jobs/18257947997/artifacts/file/portable-package/Merlin-Studio-linux-x86_64.zip).

The current package **does not include a Python interpreter, model GGUF weights or inference binary**. On a machine with compatible Python 3.10+ it starts offline for local chat UI/workspace and slash commands; full offline AI inference requires separately supplied compatible binaries and model data. Windows and macOS have not yet passed corresponding native-package acceptance. Do not represent this ZIP as a self-contained cross-platform offline AI release.

## Remaining production gates and ranked next tests

1. Prove one **real model-selected tool** episode, with source-bound evidence and an independent task-specific check, without exposing user data or unsafe host/network authority.
2. Run the *current* token/deadline UI through a real Chromium desktop/mobile renderer, keyboard/mouse, offline/online transitions, and restart. Static JavaScript syntax is not rendered UI acceptance.
3. Bind an authorized connected public browser with DNS rebinding, network egress, timeout, source-custody and registry checks; independently test a source-cited research answer.
4. Assemble and test per-platform **self-contained** offline profiles (Python + approved inference runtime + licensed model) with size, ABI, signature, integrity, isolation and rollback evidence. Keep model weights and credentials out of test artifact downloads without explicit authorization.
5. Reconcile draft product PRs [#193](https://github.com/Mannyspiro/expert-robot/pull/193), [#194](https://github.com/Mannyspiro/expert-robot/pull/194), [#195](https://github.com/Mannyspiro/expert-robot/pull/195), canonical v6 task ownership, GitLab CI MR [!1](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/merge_requests/1), release licensing and human review. No unreviewed merge or deployment.

**Skeptical-scientist check:** These observations distinguish actual inference, fixture tests, artifact hash checks and release qualification. N-ality is useful for preserving independent axes of source identity, authority, runtime, model quality, UI and packaging. Simplex and fuzzy scores do not authorize release; continuum latency modeling is deferred until a controlled sample exists. Confirmation bias is mitigated by retaining all failed attempts and their original artifacts. The tests do not establish general AI reasoning, proof, self-improvement, autonomous desktop skills or production authorization.
