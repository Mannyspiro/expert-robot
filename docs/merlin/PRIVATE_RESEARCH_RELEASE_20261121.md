# Private Merlin release — 21 November 2026

**The selected private research runtime is merged, deployed and inspected on the existing Oracle ARM host.** The finite research assessment retained the baseline.

## Recorded release gates

| Gate | Existing repository evidence | Outcome |
| --- | --- | --- |
| Source | [PR190](https://github.com/Mannyspiro/expert-robot/pull/190) | Merged as `2dc6fb85b865efe868c68ca92cfc2400696e871f`. All 371 merged files match the reviewed head `761756025fb88f7e722c799ca91964e3ad24c53a`. The selected cohort has 130 files and preserves all 241 unselected main files. |
| Native validation | [44919201279](https://github.com/morganaspim/Cace-app/actions/runs/44919201279) | 599 software tests, eight kernel cases and six context/recovery cases passed within the recorded scope. |
| Model bootstrap | [44914708164](https://github.com/morganaspim/Cace-app/actions/runs/44914708164) | The pinned local provider performed an actual inference and passed its bounded bootstrap/restart checks. |
| Retained-response assessment | [44923397429](https://github.com/morganaspim/Cace-app/actions/runs/44923397429) | Baseline and retained A each passed the original 18 cases; four bounded workers; no new model calls; baseline retained. |
| Release validation | [44925050753](https://github.com/morganaspim/Cace-app/actions/runs/44925050753) | Accepted the exact 25-file runtime projection and existing provider/state/access prerequisites. |
| Deployment | [44925842904](https://github.com/morganaspim/Cace-app/actions/runs/44925842904) | Runtime activation and service restart succeeded; fixed tools and retained evidence remained available. |
| Fresh inspection | [44926064599](https://github.com/morganaspim/Cace-app/actions/runs/44926064599) | Confirmed the deployed runtime, service profile and private report/handoff access. |

The validation, deployment and inspection made **zero additional model calls**. The external model budget remains **$0**. Each operation ran 26 controller controls; its 599-test software evidence remains bound to the original native run, rather than being counted as a new software-suite execution.

## Research outcome and preserved limits

The [first generation](https://github.com/morganaspim/Cace-app/actions/runs/44917400072) failed on a JSON fence. Its narrowly tested parser repair was included in the reviewed source. The [successor generation](https://github.com/morganaspim/Cace-app/actions/runs/44919773657) retained a valid A program identical to the baseline; B's generated content was truncated at its fixed token cap.

The separate retained-response assessment evaluated baseline and A on 12 selection and six final exact-rational cases. Both passed, but A was unchanged, so the decision is **retain the baseline**. B has no accepted candidate, score or execution. Both generation sessions remain incomplete. The assessment preserves all 39 historical records and demonstrates fresh-process finalization/replay without repeating model or worker effects. These findings establish this finite task and recovery behavior, not general model improvement or a completed two-coder generation cycle.

## Access and next work

The demonstrated route is authenticated fixed GitHub operations to the existing private Unix service. Direct remote HTTP/MCP/ChatGPT access remains unconfigured and requires real identity/resource/allowed-user configuration followed by an actual caller test.

The [scope note](PRIVATE_RESEARCH_RELEASE_SCOPE_20261121.md) and [checkpoint](../../config/merlin/plan-updates/20261121-private-research-release-result.json) preserve remaining production gates. The existing master plan remains the canonical navigation source.

This documentation includes summarized outcomes and links to already-existing runs. Raw private assessment receipts, original archives and operational metadata were prepared for retention, but their additional publication into this repository is pending explicit approval.
