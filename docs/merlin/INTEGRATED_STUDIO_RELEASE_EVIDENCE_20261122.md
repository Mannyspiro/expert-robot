# Merlin integrated Studio release review — measured checkpoint (2026-11-22)

## Claim boundary

This record covers only the source and test outcomes named below. It does **not** declare a production-accepted deployment, an active Chromium browser service, a fully bundled/offline model release, a correct model-selected native tool episode, scientific discovery, or authority to merge/promote.

The integration source is \`Mannyspiro/expert-robot\` branch \`merlin/integrated-release-review-20261122\`, reviewed execution SHA \`c5b029956ded7594485bcbe1772294676cbb1322\` (subsequent documentation commits do not retroactively extend tested scope). It consolidates bounded browser modules, the canonical source-research handoff, Studio, release evidence checker, and candidate-only offline profile tooling. Originating draft PRs #193, #194 and #195 remain separate and open.

## Observed evidence and scope

| Slice | Exact evidence | Measured outcome | Boundary |
|---|---|---|---|
| Integrated Python/native | [GitLab 3099870001](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099870001) | 248 Python unittest cases; 33/33 native C++ CTests | Offline/fake-browser; no model, live Chromium or deployment |
| Browser wire and source handoff | [GitLab 3099869833](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099869833) | Successful 41-case public-browser contract lane, 23-case handoff lane, lifecycle/control cases, and Studio bridge controls | Synthetic captures/restart; not native isolated Chromium acceptance |
| Studio Python/security | [GitLab 3099869736](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099869736) | Pass, including browser capability default deny, exact run binding, readback, and rejection of stale Unix listener and client ABI | Fixtures, not model-quality or live host availability |
| Portable ZIP | [GitLab 3099869922](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099869922), [GitHub 45038944781](https://github.com/morganaspim/Cace-app/actions/runs/45038944781) | Independently built 109,389-byte ZIP, SHA-256 \`6601121073904c52596995eb0b7ffbf16239a7ca11c9e40673a8bbfb4c1f0119\`; identical rebuild; 36 Studio tests, startup and restart | Linux x86-64 source-only UI, Python/system libraries required; no bundled GGUF/inference engine |
| Real local-model chat | [GitHub 45034470736](https://github.com/morganaspim/Cace-app/actions/runs/45034470736) | Two simple local Qwen answers correct; four persisted messages; restoration and stale session rejection; model and Studio processes terminated | Constrained ARM64 private loopback; not representative of broad reasoning or model-tool reliability |
| Real public source intake | [GitLab 3099790588](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099790588) | Two real primary HTTPS sources, independently rehashed; revised source-specific proposition accepted | HTTP bytes not rendered Chromium, factual guarantee or model research |
| Real model-selected source tool | [GitHub 45038092059](https://github.com/morganaspim/Cace-app/actions/runs/45038092059) | One read-file event and JSON compatibility adapter; final output had an extra label and failed exact-only criterion | **Blocked**; do not count as qualified tool use |
| Adversarial model-selected file | [GitHub 45038275814](https://github.com/morganaspim/Cace-app/actions/runs/45038275814) | One read-file event; final output again included extra label | **Blocked**; no adversarial success claim |
| Revised format prompt | [GitHub 45038555637](https://github.com/morganaspim/Cace-app/actions/runs/45038555637) | Read completed but second model response exceeded deadline; result retained | **Blocked**; no model output format or timeout qualification |
| OCI browser host read-only inspection | [GitHub 45034030691](https://github.com/morganaspim/Cace-app/actions/runs/45034030691) | \`merlin-public-browser.service\` inactive/disabled, release/current paths absent, stale root-owned socket inode present, zero matching Unix listeners | No live host service, no new capture |
| Prior OCI browser continuation | [GitHub 44956695079](https://github.com/morganaspim/Cace-app/actions/runs/44956695079) | Privileged continuation stopped on \`existing continuation or active state requires explicit reconciliation\` | Retained failure, not authorization to delete the socket or retry |

## Defect-family repair ledger

1. **Wrong per-file execution mode:** \`extract_offline_profile.py\` carried an inventory loop's final \`mode\` into the extraction loop. Each extracted file now re-reads its own \`ZipInfo.external_attr\`, checks its type and sets the exact allowed executable/nonexecutable mode. Regression inspects manifest, ZIP mode, Python runtime, llama-server, ordinary files and safe-symlink rollback. Pass on CI 3099870001.
2. **Orphan socket mistaken for capability:** expected path ownership and file type alone cannot prove a listening service. Studio additionally checks the exact pathname and connected listener shape in bounded \`/proc/net/unix\`, and still authenticates the real supervisor via \`SO_PEERCRED\`. Synthetic negative control includes stale socket and source-substitution cases. OCI inspection confirms this distinction matters.
3. **Stale installed API:** separately deployed \`merlin.browser_client.request_browser\` may not accept the new bounded \`timeout_seconds\` parameter. Studio now withholds the browser capability unless the exact required client call signature and public URL policy are present. This check does not replace an independent installed-module SHA pin at deployment admission.
4. **Readback authority/retry:** browser \`status\` is now a read-only, same-Studio-run operation. Exact retained completed references may be returned without a second \`submit\`. Ambiguous, failed, missing or partially failed episodes are not promoted to success. Negative tests prevent cross-run replay and invented evidence.
5. **Small local model strict-format failures:** three host attempts exposed either a label-prefix deviation or a second-turn timeout. The model-generated final answer remains unqualified; fixed source hints do not establish broader reasoning reliability. Separate a real model's observed output from a deterministic parser or synthetic test. Do not silently strip prefixes to game the acceptance criterion.

## Remaining release gates

**G-OCI-BROWSER:** A fixed, authorized host coordinator must independently reconcile prior installation/ledger state and stale socket without silent deletion; verify approved installed source hashes, native isolated Chromium document and screenshot capture, evidence publication, two independent readbacks after restart, stopped process proof and rollback. Missing service is an actual blocker.

**G-MODEL-TOOL:** Predeclare an independent held-out multi-task set and source-only exact-copy metric with falsifiers; compare small-model responses with larger/alternate providers, native tool calls and explicit costs. Preserve failed attempts. The demonstrated Qwen session verifies basic chat and a tool event, not exact final tool use.

**G-PORTABLE-OFFLINE:** Reproducible source-only package is available. The self-contained AI profile still needs pinned architecture-compatible Python/llama.cpp/GGUF, complete third-party notices/rights review, native start/stop, model latency and memory, safe extraction, and independent restart/restore on target OS. Do not label the current ZIP self-contained.

**G-RELEASE:** Reconcile PR #193/#194/#195 and intersecting draft DAG, independent security review, source provenance, CI artifacts, release version, signed artifact ownership, and explicit merge/deployment authorization. None is implied by this checkpoint.

## Ranked continuation

1. Validate exact OCI browser service installation/reconciliation plan with a nonmutating host preflight, then a separate approved one-operation startup and capture gate.
2. Qualify one held-out real-model source-to-citation answer under strict deadlines; do not weaken an exact answer contract to pass a flaky small model.
3. Build and independently review a genuinely bundled offline AI ZIP with architecture and redistribution evidence, then test first-run, restart, tool and browser-unavailable behavior.
4. Review and integrate the draft PR release DAG, retain independent source/result hashes and production rollback.
5. Resume selected CAD, formal math, Ideonomy and creative-agent extensions only with original-domain discriminating predictions and actual native tests.

## Skeptical scientist / representation assessment

Premise: a file path is not a running listener, an artifact hash is not source truth, a mock model tool is not a real model/tool success, and code present in a repository is not installed on a host. Alternative explanations for the failed model answers include small-model instruction following, prompt-format ambiguity, inference latency and template behavior; no one cause was independently isolated. The next comparison must predeclare the prompts, provider, output constraints and falsifiers before sampling.

Simplex: **not applicable** to the discrete archive/authorization invariants. N-ality: **deferred** to explicitly typed multi-channel scientific research, not used as an access gate. Continuum: **not applicable** to binary source identity and host status. Fuzzy representation: **not applicable** to qualification, permissions or digest equality; it may rank reversible future experiments but cannot soften Boolean release criteria.

This is an append-only observational checkpoint under [master plan v6](https://github.com/Mannyspiro/expert-robot/blob/6d4b5a4a3a5b81210d192554774316c04d2d88ff/config/merlin/production-master-plan.json), not a replacement for that plan.
