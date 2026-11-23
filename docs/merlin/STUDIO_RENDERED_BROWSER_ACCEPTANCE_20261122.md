# Merlin Studio rendered browser acceptance — 2026-11-22 (UTC 2026-11-23)

**Status:** Actual headless Chromium UI acceptance passed on a disposable Ubuntu 24.04 GitHub runner. The interactive UI is not deployed to the user's target computer. This is a draft, not a release approval.

## What changed

Merlin's prior Python approval card always warned that scripts execute with local-user permissions, including when the selected backend was an isolated OpenSandbox container. That statement described the default host mode, not the opt-in sandbox mode. This branch changes the wording in Settings and approval cards to distinguish:
- Host Python: explicitly approved code has the local user's permissions and is **not** an OS sandbox.
- OpenSandbox: the approved source runs in an **operator-configured container**; source digest, image and controller are bound to approval, but the container is not a guarantee of kernel security.
- Recovery/setup blocked: Python remains disabled; it will **not** silently fall back to the host.
It also preserves the provisional "Stopping — verifying cleanup…" state and disables duplicate Stop clicks while cancellation is being verified.

## Actual Chromium evidence

- [Draft PR #217](https://github.com/Mannyspiro/expert-robot/pull/217), verified implementation source SHA 61afece6f38ecadfb5290702d3fa166ee2ca7a3b.
- [Rendered browser GitHub Actions 45102877416](https://github.com/Mannyspiro/expert-robot/actions/runs/45102877416): **success** on Ubuntu 24.04, Node.js 22, Playwright 1.56.0 and bundled Chromium 141.
- [Screenshots, JSON test receipt and SHA-256 checksum artifact 14786053023](https://github.com/Mannyspiro/expert-robot/actions/runs/45102877416/artifacts/14786053023), expires 2026-12-07.
- Ten test cases passed: real desktop boot; visible approval dialog and host permission warning; click Decline and verify no script execution; Activity records declined action; click Approve Once then confirm real synthetic host Python output and canonical ArtifactRef; click Stop during a long-running host script and verify no completed tool result; simulated provisional cancelling visual and duplicate-stop disable; reload recovers conversation messages; simulated capability status for sandbox and recovery-blocked wording; 390px mobile layout and no horizontal overflow. Seven screenshots captured.
- The UI-only **cancelling held state** and the alternate sandbox/recovery capability labels used **intercepted browser JSON fixtures** to make otherwise fleeting states deterministically visible. Those do not constitute real Docker observations. Native HTTP cancellation and controller-outage recovery were separately verified in the upstream PR #216.
- The browser's real code execution was a synthetic script on the disposable GitHub runner under the normal host Python backend, *not* on a user's computer or in an actual OpenSandbox container. No model weights or remote accounts were used.

## Failed attempts retained and repaired

1. [Initial browser CI 45102603957](https://github.com/Mannyspiro/expert-robot/actions/runs/45102603957) failed because GitHub defaulted to Ubuntu 26.04, unsupported by the pinned Playwright 1.56 package. The dedicated browser job was pinned to supported Ubuntu 24.04.
2. [Second browser CI 45102676062](https://github.com/Mannyspiro/expert-robot/actions/runs/45102676062) installed Chromium and passed initial approval/Activity steps, but the **test harness prematurely injected** its simulated cancelling state before clicking Stop, correctly disabling the button. The test now injects the visual fixture only **after** the genuine HTTP Stop request succeeds. No safety condition was weakened.

## Related independent gates

On the same source SHA: [portable Studio CI 45102877610](https://github.com/Mannyspiro/expert-robot/actions/runs/45102877610) and [self-healing unit CI 45102877396](https://github.com/Mannyspiro/expert-robot/actions/runs/45102877396) passed. Native OpenSandbox workflow 45102877394 was still running when this evidence was written and must be checked independently. Generic CI 45102877456 was canceled due to branch concurrency and must **not** be reported as passed.

## Remaining production work (ranked)

1. Verify that the user-selected, **real OpenSandbox** mode can be driven through the rendered browser on the intended OCI host, using proper isolated model/backend credentials and independent Docker evidence.
2. Bind a real locally running, authorized model checkpoint; demonstrate model-selected research/read/write action through actual UI and approvals with independently checked evidence and stable ArtifactRef.
3. Reconcile the long chain of draft PRs and GitLab/OCI release controls, including architecture, supply-chain identity, rollback, migration, and published package. A browser-success receipt alone does not authorize deployment.
4. Measure startup latency, peak memory and resource use across repeated model and sandbox tasks on target hardware, compare to the existing host-worker baseline.
5. Only after independent acceptance, obtain explicit release approval and complete the audited deployment.

## Skeptical-scientist decision

Hypothesis: the rendered approval UI accurately explains authority and can carry a real click-based action from request to saved receipt. Observation: this passed in Chromium for a controlled host-Python fixture; sandbox permission states were simulated in-browser. Alternative: a different target browser, actual OpenSandbox controller or real-model context could behave differently. Falsifier: UI says "stopped" while owner intent remains, missing approval or wrong source digest, screen incorrectly labels sandbox as host Python, or no result ArtifactRef. N-ality keeps rendered UI, backend, approvals, model, controller, persistence and host platform independent. Simplex/continuum deferred until calibrated target-hardware data; fuzzy scores are not acceptable for authorization.
