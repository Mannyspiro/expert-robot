# Private research release — 21 November 2026

**Merlin’s bounded private research runtime is merged, deployed and independently inspected on the existing Oracle ARM host. The original-task assessment retained the baseline, and the deployed service preserves the evidence and existing private access boundary.**

This is a bounded private Merlin release on the existing Oracle ARM host. The [machine-readable checkpoint](../../config/merlin/plan-updates/20261121-private-research-release-result.json) records the complete evidence lineage, including unsuccessful attempts and remaining gates. Its parent is the [immutable PR189 checkpoint](https://github.com/Mannyspiro/expert-robot/blob/6d4b5a4a3a5b81210d192554774316c04d2d88ff/config/merlin/plan-updates/20261121-storage-completion-local-result.json). The [canonical master plan v6](https://github.com/Mannyspiro/expert-robot/blob/6d4b5a4a3a5b81210d192554774316c04d2d88ff/config/merlin/production-master-plan.json) remains unchanged.

## Release gates and current outcome

| Gate | Actual evidence | Result and boundary |
| --- | --- | --- |
| Product source | [PR190](https://github.com/Mannyspiro/expert-robot/pull/190), source `761756025fb88f7e722c799ca91964e3ad24c53a` | All 130 selected files match the frozen source map. The PR changes 128 paths, preserves all 241 unselected main files and deletes none. |
| Local software | Exact source/inventory | 599 passed in 57.078 s; no skips, failures or errors. |
| Native software and integration | [Run 44919201279](https://github.com/morganaspim/Cace-app/actions/runs/44919201279) | 599 passed in 172.112 s, plus eight kernel cases and six context/recovery cases. The selected source is the tested scope. |
| Local model bootstrap | [Run 44914708164](https://github.com/morganaspim/Cace-app/actions/runs/44914708164) | One real inference, 12 independent clamp checks, service restart and post-restart health/model-list observations. This smoke does not qualify general model quality. |
| Original task assessment | [Run 44923397429](https://github.com/morganaspim/Cace-app/actions/runs/44923397429) | Baseline and retained A each pass 12 selection and six final exact-rational cases. Four native workers; no new model or metadata calls; retain the baseline. |
| Live release validation | [Run 44925050753](https://github.com/morganaspim/Cace-app/actions/runs/44925050753) | Exact 25-file runtime bundle, accepted native/assessment identity, current provider, all 39 historical records and complete private context/handoff reads observed. Independent review accepted 77 checks and 26 controller controls. No activation, host configuration change, canonical write or model call. |
| Source merge | [PR190](https://github.com/Mannyspiro/expert-robot/pull/190), merge `2dc6fb85b865efe868c68ca92cfc2400696e871f` | All 371 merged files match the accepted source head; all 241 unselected main files remain preserved. |
| Deployment | [Run 44925842904](https://github.com/morganaspim/Cace-app/actions/runs/44925842904) | Actual runtime status `upgraded`; active/enabled private service; exact retained state/report/handoff after restart; four fixed probes pass. Separate 45-check independent and 31-check root reviews accepted the activation. |
| Post-deployment inspection | [Run 44926064599](https://github.com/morganaspim/Cace-app/actions/runs/44926064599) | Fresh fixed read-only inspection accepted the exact deployed runtime, provider, full report/handoff and retained failure statuses. Separate 36-check independent and 22-check root reviews passed. Zero new inference, canonical writes or host configuration changes. |

The selected source-map SHA256 is `548194d9fddd5a587feeb5384bf6b71f9fe7cee4976dab519725251fb2ca3654`. The runtime bundle SHA256 is `ef5c8d65782e8b746d3002d1f407596b4d9c765059ec46271d446d4e9bc63f82`. Documentation publication must preserve the distinction between the tested product commit, its later merge commit and the Cace-app operations commit.

## Scientific outcome: retain the existing solver

The research task asked the pinned local model to propose an exact-rational linear solver. The original independent reference was fixed before generated output and kept its six training, six held-out selection and six untouched final cases. The assessment checked exact expected rational output, residuals in the original equations, preservation of inputs and singular-system behavior.

The first generation run [44917400072](https://github.com/morganaspim/Cace-app/actions/runs/44917400072) failed on a complete JSON Markdown fence. The narrowly tested parser repair accepts one complete fence losslessly and retains strict decoding. The successor [44919773657](https://github.com/morganaspim/Cace-app/actions/runs/44919773657) stored a valid A program equal to the baseline. B's complete provider envelope contained generated text truncated at its 900-token cap; no complete candidate, score or worker execution was invented.

The distinct retained-response assessment then ran the baseline and A separately on the 12 selection cases and six final cases. Each passed all 18. A is the same program, so the recorded conclusion is **no admissible improvement; retain the baseline**. B remains `rejected_output_truncated`. Both generation sessions remain incomplete, with their exact original status results preserved. The separate four-worker assessment does not pass or replace the earlier completed-dual-coder acceptance contract.

Selection, final evaluation and read-only replay ran in fresh processes. Replay made no model or worker call, added no artifact and preserved the database/inventory identities. All 39 historical records remain preserved. The complete 6,481-byte report and session handoff were read through the private Unix route after finalization and replay. The evidence supports this finite original task and recovery behavior; it establishes no general solver proof, model-quality gain, speedup, memory improvement or independent CACE qualification.

## Actual host and provider

The pinned Qwen2.5-Coder-1.5B-Instruct Q4_K_M model runs through the pinned native llama.cpp runtime under its dedicated service. Release validation observed the expected model and executable identities, active/enabled service, 150% CPU quota, 3 GiB memory limit, zero swap and a 32-process limit. The model endpoint is numeric loopback. The deployed private Merlin daemon remains a separate active/enabled service with `PrivateNetwork=yes`, `RestrictAddressFamilies=AF_UNIX` and `NoNewPrivileges=yes`. Activation retained the exact service configuration, unit, grants and private registry state; it changed the active runtime package. The health, mathematical-lenses, research-contract and research-episode fixed probes passed after startup, while `job_submit` remained denied.

The external model budget is **$0**. The failed generation attempts consumed all three admitted research model calls; bootstrap smoke is counted separately. The retained assessment and live validation made zero new inference calls. The finite wall-time amendment is retained as a measured operational choice; a longer allowance can consume more CPU-seconds and is not an efficiency gain.

## Access and durable state

The demonstrated route is **authenticated fixed GitHub operations to the existing private Unix socket** on the selected host. Validation and the actual activation’s post-restart reads verified the complete assessment report and handoff result digests, all 39 preserved historical records and both unchanged incomplete generation statuses. Startup reached readiness in two attempts, measured at about 0.201 seconds by the activation probe. Configuration, unit and grants remained exact. This is an operational observation within the fixed probe, not a general latency benchmark.

At the recorded release validation, direct remote HTTP/MCP/ChatGPT registration was unconfigured. The user has since excluded ChatGPT access from Merlin; adding it is not a remaining integration target. The new direction is broad general browser access to information databases, news and GitHub for research and self-improvement. Those browser effects require their own actual implementation and measurements; the existing private socket evidence does not establish a browser capability. See the [current direction and explicit publication authorization](BROWSER_RESEARCH_DIRECTION_20261121.md).

## Repository and plan reconciliation

The product cohort is in `Mannyspiro/expert-robot`. The generated controller, provider inspector, controller controls and fixed operations workflow are in the Cace-app operations branch `merlin/dot-ops/branch-release-20261120`; validation used commit `99a44ba263f4e624443a87dd99276fd479404588` and deployment used `b1bbf7c20ef7354a79ecc6ae437a498eca9dae13`. The runtime archive is the exact 25-file projection of the accepted 130-file product source, plus its manifest.

The selected storage/private-runtime work from PR189 is carried forward by exact file identity into PR190. Unrelated ancestor work and historical evidence remain at their original refs. This does not merge the recorded 2,345 branch-only commits or authorize blanket ancestor closure. The [release scope note](PRIVATE_RESEARCH_RELEASE_SCOPE_20261121.md) retains all ten master-plan tracks and 45 unequal tasks; no global completion percentage is inferred.

## Next acceptance

The five actual release gates—assessment, validation, merge, deployment and inspection—are recorded in the checkpoint. The post-deployment inspection [run 44926064599](https://github.com/morganaspim/Cace-app/actions/runs/44926064599) passed separate 36-check independent and 22-check root reviews. Validation retains its 77-check independent review; deployment retains its separate 45-check independent and 31-check root reviews. These are review checks, not additional software tests. Operations reran the 26 controller controls and reused the exact bound native599 evidence. The retained receipts, API metadata, review summaries and exact archives accompany this checkpoint under the linked evidence manifest. Continue with the next explicit master-plan acceptance gate. The documentation pull request records its own publication separately from the completed product release.

## Retained release evidence

The [repository evidence manifest](../evidence/merlin-private-release-20261121/manifest.json) identifies the exact retained receipts, API metadata, assessment result and review evidence. Its hashes make the retained records checkable without relying solely on the expiry of Actions artifacts.

## Current publication authorization

The user explicitly approved publication of the full raw release evidence and gave standing authorization for relevant evidence publication to any connected repository with existing permissions. The [authorization checkpoint](../../config/merlin/plan-updates/20261121-browser-direction-and-evidence-authorization.json) preserves the exact wording and immutable parent. The prior pending-permission state is historical. This package records that approval without claiming a change to global application or repository permissions.
