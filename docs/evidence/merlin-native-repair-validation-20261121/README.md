# Merlin production repair checkpoint — 21 November 2026

The exact reviewed archive parser and browser lifecycle repairs are published. Their fixed native fixture operation passed all **101 required cases** on the existing OCI runner. This closes the repaired-source fixture gate; supported-runtime installation, live browser acceptance, Studio/model acceptance and release qualification remain open.

## Published source and operation

| Item | Exact identity |
| --- | --- |
| Product browser lifecycle repair, PR193 | `5f279deaea018ad45644837633acd16adc997907` |
| Operations parser repair and frozen fixture definitions | `7586eb7a39e94494cfbb4b29ae05771d479aea1f` |
| Single additive fixture request | `cc869730382fdf171865f41f76aa2f9b0cdd21c5` |
| Request ID | `7f9fe949-20d2-4d71-b564-9295b8bcba6b` |
| Native run / attempt | `44962547217` / `1` |
| Native job | `137024308032` |
| Reviewed package SHA256 | `08b8d19977a2ac4adaec1031cbbf9c2bd7195b7c94b926e9fc2c14f13000e592` |

The user approved the concrete review package and its one test operation after the earlier automatic publication denials. All 53 original package entries and two minimal authorization records were verified against immutable Git blobs and modes. Definitions were published separately from the one-file request. Definition-only publication caused no workflow run.

The request coordinator initially discarded a request-envelope path while decoding a local JSON result. GitHub rejected the resulting blank-path tree call with HTTP422 before creating the tree. The coordinator corrected the envelope decoder, asserted the path, and preserved the same request UUID. This did not cause an additional native run. The original error and repair are retained in `publication-receipt.json`.

## Measured native result

[Original run](https://github.com/morganaspim/Cace-app/actions/runs/44962547217) executed as UID1000 on `cace-oci-a1`, Python3.9.25. The original archive, all 35 members, job log, identities, suite receipts and cleanup receipts are preserved alongside this document.

| Fixed suite | Required | Passed | Failures / errors / skips | Suite and cleanup seconds |
| --- | ---: | ---: | --- | ---: |
| Static archive inspector | 35 | 35 | 0 / 0 / 0 | 0.492 |
| Existing browser contracts | 41 | 41 | 0 / 0 / 0 | 3.540 |
| Real Unix-socket lifecycle | 13 | 13 | 0 / 0 / 0 | 4.207 |
| Signal/process/ownership controls | 12 | 12 | 0 / 0 / 0 | 2.075 |
| **Total** | **101** | **101** | **0 / 0 / 0** | |

All suites also had zero expected failures and zero unexpected successes. Discovery, execution and required counts agree. All four command receipts show exit0, no controller error and `cleanup.complete=true`. The archive-inspector suite left one adopted fixture descendant; the coordinator identified and reaped that child (PID2722169, start time582532775 ticks), and completed cleanup. Thus native child cleanup was exercised, not merely inferred from a mock. These observations apply to this bounded trusted-fixture operation; they do not establish a general-purpose process sandbox.

Independent artifact review verified every one of the 18 pinned executable source files, the full workflow, the exact request and all suite receipts. The original ZIP has **106,026 bytes**, **35 members**, SHA256 **`e6895d85732c03658d8cfa020d634e86630bdaf16d04beb47b8e903b6a4618a7`**, GitHub artifact ID **14729809420**. Its digest matches the upload record.

## What the repairs establish

The static parser now infers directory ancestors from validated actual archive members while retaining explicit path-conflict, link-resolution, size and traversal guards. Local replay of the earlier retained exact CPython archive passed with 4,949 actual members. The native 35-case suite validates the repaired parser and its negative controls on Python3.9; it does not execute or install the downloaded interpreter.

The browser supervisor handles orderly SIGTERM/SIGINT shutdown, preserves foreign replacement paths, cleans only its own recorded socket identity, reaps its launched worker and preserves child signal delivery during launch. The 13 real Unix-socket cases now pass natively, resolving the local AF_UNIX restriction as a validation blocker. Root admission/chown are fixture doubles; real unit activation, UID982 access and production rollback remain separate gates. SIGKILL or a host crash still requires explicit state reconciliation.

## Next dependency order

1. Construct and review supported-interpreter provisioning from the retained exact archive, with file-only privileged installation, unprivileged compatibility probes and identity-bound rollback. System Python and the existing provider remain protected.
2. Construct a fixed reversible transaction for the retained production socket. Fresh lock-bound state checks must match before a no-replace quarantine move. The 23:08UTC inspection is historical and cannot substitute for fresh predicates.
3. Prepare a deterministic browser runtime derivative containing the newly repaired supervisor. The prior acceptance bundle still embeds the old lifecycle; clearing the socket and replaying that unchanged route would not validate the repair.
4. Complete supported-runtime Studio source validation (111 required cases plus compilation/package checks), then the bounded real-model/provider and live browser acceptance gates. Finish rendered UI, offline/restart/platform and release recovery checks before promotion.

Canonical master v6 remains intact: ten tracks, 37 original tasks and eight extensions. This update advances one prerequisite and promotes no entire task or track. The original failed native inspections remain failed records. No interpreter installation, existing production socket cleanup, service change, public acquisition, model call, paid spend, merge or production promotion occurred in this operation.
