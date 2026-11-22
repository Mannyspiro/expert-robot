# Merlin five-lane integrated production engineering checkpoint — 2026-11-22

**Verified tests, not a release approval.** The immutable [master plan v6](../../config/merlin/production-master-plan.json) was restored without changing any of its 10 tracks, 37 original tasks or eight extensions. The [append-only evidence record](../../config/merlin/plan-updates/20261122-unified-five-lane-ci.json) contains exact source IDs, failures, limitations and ranked next actions. No PR was merged, no host production service was modified, and the release gate remains closed.

## Five successful GitLab CI lanes at one exact revision

**Reviewed GitHub source SHA:** `680594a90746a9375592a28e24507b5764b7e055`.

| Mode | Run | Verified scope |
| --- | --- | --- |
| Full native offline | [3099773331](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099773331) | Native preflight; loop, dependency, reframing, release and policy tests; CMake/C++ build; CTest; runtime smoke and retained exit/status artifacts |
| Fixed live HTTPS source / research | [3099776809](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099776809) | Anonymous bounded fixed public HTTPS source capture, six procedural research stages, raw source + canonical ArtifactRef/registry, exact arithmetic reference and counterexample |
| Release evidence | [3099776894](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099776894) | Source-identity and evidence-digest validation with negative controls; not independent semantic validation of every receipt |
| Studio and model compatibility | [3099776943](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099776943) | Token/time budgets, explicit opt-in read-only JSON bridge, native write denial, authority kept across settings changes, synthetic model tests and JS syntax |
| Linux portable ZIP | [3099776985](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099776985) | Byte-identical archive rebuild, file verification, Linux x86-64 protocol core, 36 shipped Studio tests, actual local HTTP startup, offline help, persisted conversation restart and old-token rejection |

The public-source run retrieved the exact fixed public source `https://raw.githubusercontent.com/python/cpython/v3.12.1/Lib/fractions.py`, 38,057 bytes, SHA-256 `8e8332fbb22d666ee48e1aae31d7e1c19a2508c0e3ceb5e9f7f043efbe529a08`. Its arithmetic fixture checks `1/3 + 1/6 = 1/2` against integer arithmetic and rejects `1/3 + 1/5 = 1/2`. This is source custody and a reference fixture, **not a verified new scientific finding, live AI research conclusion, or unrestricted graphical Internet browser**.

The full native job retains logs and SHA-256 receipts under [job 18258743393](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/jobs/18258743393). The source-only portable ZIP (no bundled Python, model inference binary or GGUF model) is available as a retained [GitLab artifact](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099776985). A separate ABI-compatible actual model and Python interpreter remain required for full offline AI.

## Scoped real OCI work retained separately

- [Actual local Qwen inference through Merlin Studio](https://github.com/morganaspim/Cace-app/actions/runs/45024776511): two real arithmetic answers, four persisted messages, backend restart/token rotation and process cleanup under rootless ARM64 loopback.
- [Real model-selected file-read](https://github.com/morganaspim/Cace-app/actions/runs/45029591463): one true read, two model requests, independent file and hidden-marker digest, exact marker-only response, persisted restart and cleanup.
- [Connected Chromium + Studio backend](https://github.com/morganaspim/Cace-app/actions/runs/45031412022): 112 native product cases and real Chromium JavaScript/DOM/screenshot with connected local HTTP backend, no external network and capability drop before browser execution.

These runs used **different pinned source revisions** than the GitLab integrated SHA and do not establish a single production host package. A second Qwen file-read trial recovered correct hidden data but added an unwanted prefix; later strict-output and adversarial trials failed due timeout or wrong final response. Negative results and the corrected exact-output oracle remain recorded. Do not infer statistical reliability or untrusted-input robustness from the first successful task.

## Why the earlier CI runs failed

An attempted full native run failed because the newer draft branch lacked historical preflight and loop-test files. The fixed public-source lane first lacked `scripts/merlin_public_https_acceptance.py`, then `scripts/merlin_cited_research_cycle.py` and dependent research/loop modules. These were restored **additively** from exact reviewed GitHub commits with preserved blob identities. The tested source now also includes the original immutable v6 master plan. No existing Studio source was overwritten to do this.

The earlier failures remain available:
- [Native incomplete source test 3099768274](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099768274)
- [Research missing source 3099756569](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099756569)
- [Research source captured but cycle missing 3099759204](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099759204)

## Highest-ranked remaining release gates

1. **Self-contained offline AI profile:** vet model licensing, suitable ABI/platform Python distribution and actual local inference executable, then assemble an integrity-checked OS-specific ZIP and demonstrate offline real-model chat/tool use with restart, backup and rollback. Merely showing the unbundled UI ZIP is insufficient.
2. **Connected public graphical browser:** demonstrate source-bound real external page research with strict egress policy, DNS/redirect rebinding protection, JS/DOM receipts, citation custody and independently checked answer. This gate has not passed.
3. **Model accuracy and adversarial resilience:** verify strict output on new data, negative/malicious file controls and latency distributions with predeclared sample size/budget, avoiding optional-stopping success counts.
4. **Release security:** reconcile draft [PR #193](https://github.com/Mannyspiro/expert-robot/pull/193), [PR #194](https://github.com/Mannyspiro/expert-robot/pull/194), [PR #195](https://github.com/Mannyspiro/expert-robot/pull/195) and GitLab MR!1, including the 197 overlapping changed paths between #194/#195, signatures, credentials, third-party licensing, encrypted state, independent review and rollback before any explicit promotion.
5. **Full Merlin scope:** advance persistent agents, the broader creative/CAD, mathematical research and self-improvement tools with separate task-specific acceptance criteria. Five CI lanes do not complete all 45 master-plan tasks.

**Scientific discipline:** All five jobs succeeded against the same exact checkout, but only within their named scope. N-ality separates integrity, capability, latency, autonomy and human approval. Simplex and fuzzy logic do not replace binary release gates; continuum latency analysis is deferred until repeated measured samples. Retain all failed/null results and the independent reference criteria. Production qualification and promotion authority remain **false**.
