# Merlin integrated Studio, browser research and release evidence — 2026-11-22

**Engineering acceptance, not production authorization.** This record supplements the immutable [master production plan v6](https://github.com/Mannyspiro/expert-robot/blob/6d4b5a4a3a5b81210d192554774316c04d2d88ff/config/merlin/production-master-plan.json) and [append-only checkpoint](../../config/merlin/plan-updates/20261122-integrated-browser-source-release.json). Preserve its 10 tracks, 37 original tasks and 8 extensions. Source and data coverage remain partial; the initial wider project context was not entirely reread in this work session.

## Integrated source and evidence classes

The nondeploying review branch `merlin/integrated-release-review-20261122` combines Studio/source from draft [PR #194](https://github.com/Mannyspiro/expert-robot/pull/194), additive release evidence from draft [PR #195](https://github.com/Mannyspiro/expert-robot/pull/195), and the tested public-browser modules/handoff from draft [PR #193](https://github.com/Mannyspiro/expert-robot/pull/193). The [collision review](RELEASE_RECONCILIATION_RISKS_20261122.md) counts 197 overlapping changed paths between #194 and #195; this branch deliberately retains the newer Studio worker's `-I -B` setting and does not perform a blanket merge. All three PRs remain draft/unmerged.

| Gate | Independent evidence | What was actually proved |
| --- | --- | --- |
| Real isolated Qwen Studio chat | [OCI 45024776511](https://github.com/morganaspim/Cace-app/actions/runs/45024776511) | 2/2 bounded arithmetic answers, 4 persisted messages, restart and token rotation, no host provider mutation |
| Real model-selected file read | [OCI 45029591463](https://github.com/morganaspim/Cace-app/actions/runs/45029591463) | 1 real `read_file` execution, 2 local-model requests, exact unpredictable marker, authoritative event and source digest, restart; tested in the precursor branch, **not current integrated build** |
| Native Chromium Studio UI render | [OCI 45028546153](https://github.com/morganaspim/Cace-app/actions/runs/45028546153) | Pinned HTML/JavaScript rendered; no connected backend browser or current optional browser toggle rendering claim |
| Integrated offline product/C++ checks | [GitLab 3099772659](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099772659) | 202 Python tests and 33 C++ CTest cases at prior integration SHA `a63a5789deb7110901f2b811970eb1291b346af5`; no real model/browser |
| Browser service and scientific handoff | [GitLab 3099768109](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099768109) | 89 browser-related synthetic tests, 3 fake source captures, fresh-process replay; **zero live Chromium calls** |
| Integrated release checker | [GitLab 3099722145](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099722145) | Full and empty-evidence negative controls; missing evidence rejected |
| Live primary-source HTTPS research | [Failed 3099787345](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099787345), [passed 3099790588](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099790588) | Two real official-source raw-body captures and independent rehash; a mistaken all-three-domain IANA hypothesis was falsified. Revised *source-specific* expectation passed. No AI generation or rendered Chromium |
| Read-only Studio browser bridge | [GitLab 3099796856](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099796856), [3099796903](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099796903) | Explicit opt-in, fixed host UID, Unix socket and listener prerequisite, source/capture identity, cross-run restrictions, fail-closed negative fixtures, replay and native Studio source build; **not live host** |
| Combined portable ZIP | [GitLab 3099796972](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099796972) | Reproducible Linux ZIP, 36 packaged Studio tests, offline HTTP startup, persisted conversation and restart; model weights/interpreter/browser supervisor **not bundled** |
| Latest full offline/native and integrated real-model check | [GitLab 3099797058](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099797058), [OCI 45034470736](https://github.com/morganaspim/Cace-app/actions/runs/45034470736) | In progress when this document was first authored. Do not infer a pass until the corresponding artifact and job outcome are independently checked |

## Actual OCI browser state (a production blocker)

A strictly **read-only** inspection [OCI Actions 45034030691](https://github.com/morganaspim/Cace-app/actions/runs/45034030691) retrieved its exact [artifact 14759290090](https://github.com/morganaspim/Cace-app/actions/runs/45034030691/artifacts/14759290090). The inspected bounded receipt `root-evidence/state-inspection.json` is timestamped **2026-11-22T14:39:58Z** and describes one host state snapshot (not atomic across subsystems):

- `merlin-public-browser.service` exists as a unit but is **inactive**, **dead**, **disabled**, `MainPID=0`.
- The expected installed release and `/opt/merlin-public-browser/current` are **absent**.
- A root-owned `/run/merlin-public-browser/browser.sock` filesystem socket is **present**, mode 0660, gid 1000, yet **zero** corresponding live listener rows were observed in `/proc/net/unix`.
- Inspection performed **0 application mutations, 0 connections, 0 acquisitions, 0 model calls**, and granted **no acceptance or deployment authority**.

This is a **stale/orphan socket state**. Do not infer service readiness from `Path.is_socket()` or metadata. The subsequent Studio bridge fix requires an exact listener row in `/proc/net/unix` as a *necessary but not sufficient* precondition; real operations must still authenticate peer UID0 and response identities. Preserve the original failed deployment evidence. Do not assume restarting the service works when the release path is missing. A separately reviewed installation/reconciliation/rollback is needed before actual connected Chromium is available.

## Model / tool and permission invariants

- Studio default `browser_enabled=False`; a user must enable network and browser independently and run under UID982 with a fixed, root-owned, accessible listener and available Merlin public-browser client modules. Ordinary ZIP installs remain offline with no browser.
- Only native provider tool calls can select `browser_open` and `browser_read`. The experimental JSON compatibility fallback remains restricted to `read_file` and `list_files`, never browser/desktop/Python/write.
- Browser episode identity is `studio-<32 lowercase hex run id>`; capture reads are restricted to the *same* active Studio run. Browser authority is frozen at model-run startup, so switching Settings mid-run cannot grant a new model permission.
- Source results require canonical `ArtifactRef` v1, exact project namespace, SHA-256 and normalized paths, public normalized source URL, validated UTF-8 byte offsets, digest and matching observation ID. Retrieved content never modifies system instructions.
- An orphan socket, missing supervisor, peer mismatch, unexpected source or uncertain episode leaves a **blocked** or reconciliation-needed receipt, not a fabricated success. The Python model and registered supervisor are distinct; the browser service does not call a model.
- The ZIP excludes system Python, GGUF model weights, inference binaries, browser runtime and credentials. The only included native worker is a C++ health-protocol utility, not the full Merlin engine.

## Failure families and next ranked acceptance

1. **P00/P04 first — reconcile dormant browser supervisor.** Read exact existing unit, release markers, authorized package and containment policy; prepare a signed/integrity-pinned reversible install and rollback plan, then require independently approved host mutation and a real UID982 peer handshake. Do not automatically start privileged services based on these tests.
2. **P07/P08 next — actual integrated Studio local model.** Require one real GGUF inference run on this *combined* code, browser absent/disabled on UID1000, after-restart readback and negative host grant. Cross-check local model/tool event receipts and cleanup.
3. **P09 — native Chromium research-to-answer acceptance.** Once supervisor and operator controls are qualified, run one anonymous public-browser episode with bounded source custody and independently check a novel question, citations and answer quality; test prompt injection, DNS rebound and failures before increasing scope.
4. **P00/P07 — offline self-contained release profiles.** Package approved Python interpreter, inference runtime and model by target ABI/license; measure size, signature, download integrity, installation, end-user startup, state restore and rollback on Windows/macOS/Linux separately.
5. **P01/P03/P05 — source coverage, independent coder/reviewer and formal checks.** Preserve v6 task ownership and all previously queued private context. Reconcile all source/evidence original records, evaluate held-out research cases and obtain independent reviewers before merging draft PRs.

**Scientific lenses:** n-ality separates independent axes of source integrity, worker liveness, model quality, UI rendering, package completeness, authority and deploy state. A valid digest does not validate text truth or the presence of a live service. Simplex and fuzzy grading are inapplicable to Boolean source/permission/release gates; continuum latency estimation is deferred pending repeated native samples. Retaining `reference_disagrees` prevents motivated rejection of counterevidence. Release decisions require independent authentication, rights and credential review, not these fixture passes.

**Authority:** no production deployment, merge, signing, privilege expansion, user-data exfiltration, model-training change or service modification performed in this recorded work.
