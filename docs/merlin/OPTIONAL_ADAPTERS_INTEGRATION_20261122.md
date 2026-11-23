# Merlin PR #222 — optional-provider integration and adversarial evidence (2026-11-22)

**Review only — not a production deployment, automatic tool acquisition, local model intelligence benchmark, or release approval.** This document extends canonical Merlin master plan v6 without changing its 37 original tasks, eight extensions, or ten work tracks.

## Exact source ownership

The parent integrated review branch [PR #204](https://github.com/Mannyspiro/expert-robot/pull/204) is pinned to `bc9da779dcdcd76bcffdd73e9f51cbb605233b9e`. [Dependent draft PR #222](https://github.com/Mannyspiro/expert-robot/pull/222) adds opt-in AirLLM/OpenBot and OpenSandbox/Z.ai components. The reviewed earlier source phase `8d5e34ccf50138feb750b10d7b872563af4c7da0` has a distinct native CI result; the patched source phase `69f04096733e06c8078fc9d5e0a4d0348a4ed60a` requires a new exact-revision run. Keep those phases separate.

The integration does **not** replace PR #204's Studio engine, model adapter, host Python tools, login/session rules or approval contracts. The optional AirLLM and OpenBot adapters are not a replacement default backend. OpenBot uses separate state and approvals; Graft is pinned source for research only, not an acquired active tool; cloud Z.ai requires explicit opt-in and may charge/share text. No Z.ai calls or real AirLLM model-weight inference were made in this integration.

| Upstream | Git commit pinned in Gitlinks | Source rights label in current manifests | Qualification |
| --- | --- | --- | --- |
| AirLLM | `7e2e8cfe2810dc0559461504f6ba5c0ece960ba8` | Apache-2.0 | Source-selected; benchmark and dependencies pending |
| OpenBot (pmwasim) | `019b4c65f488af06ce1a1cfb741cd825129a4c1a` | MIT | Synthetic model/protocol, restart verified on separate draft; real model pending |
| OpenSandbox | `2ff37a988e4df129babaa6f07bb616394ef94086` | Apache-2.0 | Separate native Docker control evidence exists, not on this newly combined source |
| getmodern-ai/Graft | `c77155dcac2d7988fa27268c5ea78c23b651d5ab` | Apache-2.0 | Source-only research; no automatic tool acquisition |

The original third-party license/NOTICE files must be preserved. Manifest claims and gitlink identities do not establish redistributed dependency/license clearance or secure code.

## Independent CI ledger

- Base PR #204 at exact `bc9da...`: all eight named GitLab lanes passed: [offline 3101136958](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3101136958), [release evidence 3101137063](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3101137063), [Studio 3101137159](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3101137159), [ZIP 3101137343](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3101137343), [browser 3101137460](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3101137460), [offline profile 3101137590](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3101137590), [source scanner 3101137687](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3101137687) and [Linux platform 3101137768](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3101137768). These test the named scopes, not live model/native Chromium or full release.
- Initial provider integration: [full offline 3101143704](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3101143704) failed 1 of the nine OpenSandbox/Z.ai cases after 6/6 AirLLM/OpenBot tests passed. This is a real missing `sandbox_id` result-contract defect, not a timeout or injected auth bypass. All prior core Studio, release, public-browser and lifespan tests preceding it passed.
- Other initial provider lanes [Studio 3101143821](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3101143821), [ZIP 3101143990](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3101143990), [release 3101144140](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3101144140) and [browser 3101144373](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3101144373) passed their independent scopes.
- [Initial source-pattern audit 3101144265](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3101144265) failed **correctly** as partial: selected token rules saw zero findings across 711 inventoried tracked paths (four were unscanned Gitlinks) and 273 scanned ZIP members, but did **not** inspect the four Git submodule source trees. This cannot be represented as full secrets clearance or a complete independent security review.

## Root-cause repairs

**R1 — missing sandbox provenance.** The operator-driven OpenSandbox wrapper omitted `sandbox_id` from its returned evidence, despite the focused integration contract requiring it. It now validates a bounded identifier immediately after creating the instance and before transferring source bytes. Invalid/missing identifiers fail closed and invoke `destroy()` in `finally`. A negative test covers missing, malformed, nonstring, path-like and overlong identities. Retain the original failure artifact. Only a subsequent passing new CI run can close the fixture gate; the SDK identity is still self-reported and not kernel proof.

**R2 — hidden third-party audit omission.** Git's `160000` index entries refer to *external commits*, not ordinary local files. The scanner now parses immutable staged gitlink identity and annotates each skipped source as `external_gitlink_content_not_scanned`, retaining the exact external SHA. Importantly, `status=partial` and the nonzero exit stay unchanged. This is diagnosis, not a weakening of the negative test. New fixture controls ensure malformed gitlink refs fail closed.

**R3 — independent upstream-source coverage.** The new pull-request source gate `.github/workflows/merlin-optional-source-audit.yml` actually checks out the four exact Git revisions, verifies their licenses/source pins, and scans their Git-tracked bytes individually with redacted results. A missing, oversized or suspicious source fails the gate and retains metadata-only artifacts. The two inherited optional-provider workflows separately run OpenBot's real Node tests plus a synthetic local model/restart, and the OpenSandbox/Z.ai injected SDK/HTTP tests. Until each workflow has an actual passing receipt, do not count it as accepted.

## Acceptance still required

1. On the exact repaired source, independently rerun full offline CI and focused optional fixture suites; retain stdout/status, source hashes, failed cases and count floors.
2. Independently inspect *all four* upstream source trees plus runtime dependencies, licenses, NOTICE and suspicious matches, not merely their Gitlink pins; keep any omissions visible.
3. Reconcile draft PR #222 against its PR #204 parent and upstream PRs #193/#194/#195/#206/#207. Do not auto-merge source, overwrite approvals, or claim independent review merely because a feature branch is mergeable.
4. Run one real local-model task on equivalent AirLLM and llama.cpp hardware/models/tasks to compare reference correctness, CPU/GPU RAM, disk, latency and tokens/s. Synthetic model protocol tests are not weighted model inference.
5. Verify a native sandbox source-approval, revoke, egress, CPU/RAM limit, crash and cleanup episode with independent kernel/host evidence. Real OCI public Chromium remains blocked by its disabled supervisor and orphan socket until approved reversible reconciliation.
6. Independently qualify Python/inference/GGUF included offline distribution, platform signatures/licensing, installation and rollback, native browser UI and operator ownership before any release promotion.

**Skeptical Scientist:** These dimensions form independent n-ality axes (source bytes, legal review, real model correctness, tool authorization, process containment, recovery and release authority). No fuzzy score or simplex weighted average can replace a missing source/approval/safety gate. A continuum latency model is deferred until repeated controlled timings exist. Alternative explanation for the original failure was an out-of-date contract fixture; adding an explicit source-derived sandbox ID and strict negative test discriminates that explanation without suppressing the original failure. The audit's pinned sources are *not* automatically scanned sources.

No merge, deployment, model call or account data disclosure occurred as part of the source integration.
