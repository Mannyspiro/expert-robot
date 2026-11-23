# Merlin upstream optional-source audit — preserved findings and next controls

Recorded during PR #222 review on 2026-11-22 local / 2026-11-23 UTC.

**Evidence classification:** exact source-pinned, real GitHub Actions checkout and static pattern scan, no production execution. This is not a dependency vulnerability audit, a statement that a private key is a production credential, or a release clearance.

## Original unchanged observation

[GitHub source-audit run 45109846732](https://github.com/Mannyspiro/expert-robot/actions/runs/45109846732), source commit `9e3b4cb9c77375e78a9a462233c20f292ab7bb21`, original metadata-only [artifact 14788214398](https://github.com/Mannyspiro/expert-robot/actions/runs/45109846732/artifacts/14788214398). The archive contains four original JSON reports; it does **not** contain the matched private-key bytes.

| Pinned upstream source | Recorded paths | Pattern findings | Omitted paths | Original outcome |
| --- | ---: | ---: | ---: | --- |
| AirLLM `7e2e8cfe` | 107 | 0 | 0 | No selected patterns detected |
| OpenBot `019b4c65` | 84 | 0 | 0 | No selected patterns detected |
| OpenSandbox `2ff37a98` | 3,457 | 1 | 1 | Failing source-pattern audit |
| Graft `c77155dc` | Not scanned | Unknown | Unknown | Not reached because previous step failed |

The OpenSandbox finding is **one `private_key` signature** at byte offset 0 in `components/egress/tests/resolver/fixtures/test-localhost-key.pem`, with SHA-256 fingerprint `3021d90eb9437b2d8f30e8363695c4418b5e5f1870801b5c317e9398ee0f572d` of the *matched pattern* (not an assertion about the whole file). The omission is `server/CLAUDE.md`, recorded `unreadable_ValueError` because it is a symlink. No matched bytes are printed here. The scan exercised 66 ZIP members within the OpenSandbox source budget.

The exact pinned upstream [fixture README](https://github.com/opensandbox-group/OpenSandbox/blob/2ff37a988e4df129babaa6f07bb616394ef94086/components/egress/tests/resolver/fixtures/README.md) documents that the pair is a **test-only, self-signed localhost certificate and key**, not to be trusted outside local resolver tests. The README itself has Git blob SHA `d6099602eca2775c584b39795c7eaf00eef3f935`. This is contextual evidence that the finding may be intentional. It is **not** an independently verified assertion that the fixture cannot enter a production build or service. No source-scanner suppression, credential masking of the reported finding, or production approval was made.

## Changes and remaining gates

The separate PR #222 source audit was correctly failing closed. Its original fail-fast script stopped before Graft. The corrected workflow attempts each of the four pinned submodule scans, preserves **each** independent report, and still returns failure if **any** scan reports a finding, skipped source, budget error or invalid identity. The selected token-pattern audit cannot prove absence of secrets outside its rules.

The OpenSandbox CLI contract had a separate three-step fault chain in exact-source CI: an omitted sandbox instance ID (original optional CI `3101143704`), 45-second instance TTL below the readiness-plus-execution gate (subsequent `3101155644`), and a decimal-vs-octal SDK WriteEntry mode mismatch (`3101170284` and GitHub `45110028774`). Original failures are preserved. The current source repair retains fail-closed instance-ID validation before source transfer; a 60-second bounded instance lifetime; and numeric `mode=600` matching the native Studio `portable/merlin_studio/sandbox_backend.py` at source `8149933a30f81f70e3ee2ee5d52e57fcb9a853f8`. Subsequent independent exact-revision CI must still pass; do not backdate success.

Acceptance requires reviewing the actual fixture's dependency/dataflow and symlink target, completing the Graft scan, and separately evaluating third-party licenses, runtime dependencies, real Docker network isolation, resource limits, cleanup and any distributed package contents. **No production release, service mutation, cloud/model spend, credential use or automatic tool promotion is authorized by this note.**
