# Merlin real agent tool and integrated release-gate checkpoint — 2026-11-22

**Engineering validation only; do not merge or deploy from this checkpoint.** Canonical source of task intent remains [master plan v6](https://github.com/Mannyspiro/expert-robot/blob/6d4b5a4a3a5b81210d192554774316c04d2d88ff/config/merlin/production-master-plan.json): 10 tracks, 37 original tasks, eight extensions. [Append-only update](../../config/merlin/plan-updates/20261122-native-tool-and-release-integration.json). No task completion, production qualification, budget expansion, source promotion or formal approval follows merely from these results.

## First successful real model-selected read-only tool episode

[OCI run 45029591463](https://github.com/morganaspim/Cace-app/actions/runs/45029591463) **passed** and retains [raw artifact 14757615895](https://github.com/morganaspim/Cace-app/actions/runs/45029591463/artifacts/14757615895).

Actual source and runtime: request commit `3b6d3787ebe5efdaab5c89a1e7a175ac6270d39d`, exactly pinned product-overlay commit `4f77046562097a6a429ae235d46c010d6153c548`, source archive commit `8497597f297bba83189afef2026c27f9244537ce`, local Qwen2.5 Coder 1.5B Q4_K_M under a private rootless loopback-only network namespace, and a previously verified private CPython 3.11.18 stage (interpreter SHA-256 `6cfad927461ace659b09716fad2efa828c6a4b084b7be8181c3982a9f36f464c`). No system Python installation, provider mutation, external model calls, public network access, or host-service deployment.

The model received a prompt to read `receipt.txt`; its random `MERLIN_TOOL_<32-hex>` marker was generated **only after** setup in a fresh private workspace and was **not supplied in the prompt**. The model emitted one strict read-only JSON tool call. Merlin's opt-in adapter converted that to a real `read_file` operation via the existing ToolSet permissions. The independent verifier saw the actual `model_tool_adapter`, `tool_started` and `tool_result` events. The tool read exactly one workspace file with content SHA-256 `db4d512f9426eb644169af9920093574dea8dfd8f511883bb8207e08e44e7c9a`. A **second actual model response** returned the exact marker; the answer SHA-256 matched the independently derived marker SHA-256 `99314df966352e3cac52043bbcc8a619302c1d780c8596f5e3e9ce20a4c8959b`.

Acceptances: **one and only one** real `read_file`; two real model requests; no unsafe tool selection; ten independent positive/negative synthetic evidence controls; two persisted conversation messages; server restart recovered those messages; the old session token was rejected; the local model and Studio processes terminated; private staging was removed. The scoped model episode elapsed **149.871 seconds**, which is not a latency distribution, benchmark, speed guarantee or general intelligence validation. Verification marker and auth token are not published as plain text.

### Retained attempts that failed before the pass

| OCI run | Original observed result |
| --- | --- |
| [45026045848](https://github.com/morganaspim/Cace-app/actions/runs/45026045848) | JSON was printed as assistant text; no actual read |
| [45026308650](https://github.com/morganaspim/Cace-app/actions/runs/45026308650) | Fenced JSON described a tool without native tool_call |
| [45028465585](https://github.com/morganaspim/Cace-app/actions/runs/45028465585) | Adapter executed three redundant reads and exhausted agent steps |
| [45028909477](https://github.com/morganaspim/Cace-app/actions/runs/45028909477) | One read succeeded; final model answer refused instead of marker |
| [45029277773](https://github.com/morganaspim/Cace-app/actions/runs/45029277773) | First model request timed out; continuation hypothesis not tested |
| [45029591463](https://github.com/morganaspim/Cace-app/actions/runs/45029591463) | **Passed**, with complete real tool/answer/restart checks |

The successful run does not erase failures or retrospectively promote those attempts. A **second new random-marker replication** has been requested at GitHub commit `0b6014a0ba41d022600f9e2fa8766660738d25e6`; its outcome must be measured independently before counting a second success.

## Read-only compatibility controls and release scope

The experimental Studio setting `tool_compatibility=read_only_json` is opt-in; `native` remains default. The adapter rejects malformed JSON, repeated keys, disallowed traversal paths, unsupported names and any file modification, Python, desktop or network commands. Model-facing tool schemas are reduced to `read_file` and `list_files` in this mode, and the model execution path separately rejects native provider write calls, including when global settings change while a read-only run is in progress. Explicit **user** commands such as `/write` retain their existing permission semantics. A single adapted read is followed by one tool-free model continuation and event custody. This is not an approval bypass or general model reliability claim.

The read-only compatibility, budget/deadline, model authority, interrupted worker, and UI settings have focused GitLab tests in [pipeline 3099717585](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099717585), which passed eight earlier model-budget cases plus **15 compatibility cases**. The updated Linux ZIP acceptance [pipeline 3099718982](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099718982) passed **36 extracted Studio tests**, deterministic archive rebuilding and offline HTTP restart.

## PR integration without regressing working Studio

[Paged changed-path review](RELEASE_RECONCILIATION_RISKS_20261122.md) found zero overlaps of PR #193 against PR #194/#195 and **197** overlapping paths between PRs #194 and #195, including earlier source versions that could regress the `-I -B` native Python-worker repair.

A **separate nondeploying review branch** [`merlin/integrated-release-review-20261122`](https://github.com/Mannyspiro/expert-robot/tree/merlin/integrated-release-review-20261122) was created from the latest source commit `4f77046562097a6a429ae235d46c010d6153c548` of PR #194. Only these four previously absent files were brought over from PR #195 commit `52c3f3d6277d5628ba7833152b97bcaa3660f321`: `python/merlin_release_gate.py`, `tests/test_merlin_release_gate.py`, `scripts/run_merlin_release_checks.py` and `.github/workflows/merlin-release-evidence.yml`. Nine selected resulting file blobs were compared with their exact parent sources and all matched; no pre-existing Studio file was overwritten.

At integrated commit `e997f4a823c1f509ef026b1b4cfa8cf5929be2e7`, **three independent GitLab jobs on that same SHA passed**:

- [3099722145](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099722145): Python 3.11 release-evidence positive/negative checks with the missing-evidence fail-closed CLI reference.
- [3099722180](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099722180): eight budget/deadline tests plus 15 adapter/authority tests, JavaScript syntax.
- [3099722235](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099722235): reproducible Linux x86-64 ZIP, verified native protocol worker, **36 packaged Studio tests**, offline commands, actual HTTP startup, restart and expired-token rejection.

These jobs prove the tested *source slices* work at one integrated revision; they do not close the semantic review, institutional scope, full browser/agent/OS coverage or the nine release-evidence production gates. The ZIP **excludes Python distributions, licensed model weights and inference executable**, so it is not yet a self-contained cross-platform offline AI product.

## Ranked next experiment and production blockers

1. **Replicate tool use with a second random, prompt-hidden marker**; preserve all attempts. Then test a distinct held-out file-retrieval problem, wrong/missing files, prompt injection inside untrusted file content and non-read-native call rejection.
2. Connect the **actual public browser** with explicit egress and DNS/redirect constraints; preserve raw source bytes, DOM, citations and an independent source-answer reference. Public HTTP receipts are not JS browser acceptance.
3. Produce a self-contained **offline local-model package** for a specific target OS/architecture, bundling a vetted Python interpreter and licensed inference/model weights, then test extraction, startup, model inference, GUI, backup and rollback without credentials or hidden downloads.
4. Reconcile **PRs #193, #194, #195** with fresh exact-source review and license/security checks; verify release evidence against actual receipt semantics and independent reviewer. Do not merge or deploy while draft gates remain.
5. Resume the remaining master v6 research/evaluator, CAD/wiring/simulation, math (n-ality, simplex, glyphs, continuum) and Forge/HUD/voice work against separate measurable acceptance protocols rather than treating these Studio slices as completion of all 45 tasks.

**Scientific caveat:** The falsifier is a native second-file case where the actual model fails to select the read, the read digest is wrong, the final answer is incorrect, or restart/token controls fail. Each such failure belongs in the canonical evidence ledger and must not be converted into success by synthetic models or inferred capability. N-ality keeps runtime, tool authority, source custody, model answer and release independent. Simplex optimization and continuum performance modeling are deferred pending defined measurements; fuzzy membership cannot soften binary security or release gates.
