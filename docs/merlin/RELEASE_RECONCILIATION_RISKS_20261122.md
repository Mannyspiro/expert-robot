# Merlin draft PR reconciliation — 2026-11-22

This is a **source and release-risk review**, not merge permission, deployment approval or a completed semantic review of every file.

The canonical source of truth remains [master plan v6](https://github.com/Mannyspiro/expert-robot/blob/6d4b5a4a3a5b81210d192554774316c04d2d88ff/config/merlin/production-master-plan.json). The three product PRs are [#193](https://github.com/Mannyspiro/expert-robot/pull/193), [#194](https://github.com/Mannyspiro/expert-robot/pull/194) and [#195](https://github.com/Mannyspiro/expert-robot/pull/195). All are still draft at the inspection checkpoint.

## Measured changed-path collision scope

Using GitHub's paged changed-filename lists:

| Pair | Shared changed paths | Observed implication |
| --- | ---: | --- |
| #193 vs #194 | 0 | No pathname collision, but dependency/behavior compatibility is not proven |
| #193 vs #195 | 0 | No pathname collision, but release-source provenance and browser evidence still need review |
| #194 vs #195 | **197** | Source and historical evidence overlap; merging out of order can silently replace newer changes |

Exact head blobs of eight selected overlapping code paths were compared. `portable/merlin_studio/server.py`, `portable/build_portable.py`, `python/experimental_self_healing.py`, `python/merlin_research_browser.py` and `scripts/verify_portable.py` were identical between the selected inspected branches at this checkpoint. **Three critical product files diverged**:

| Path | #194 inspected blob | #195 inspected blob | Risk |
| --- | --- | --- | --- |
| `portable/merlin_studio/tools.py` | `772b08c3f10b0732c99a13f5268ee18e30292344` | `4756a0ce5c77c889a9488bf5c674fcb986a163a2` | #194's approved worker launch uses `-I -B` to prevent writeable Python bytecode cache corruption; the older #195 version omits `-B` |
| `portable/merlin_studio/model.py` | `4fd59c98ac4819b3034e4c63743c72bd5c8b7586` | `1189682824149fb1a2bf1970b34a9b3b842d6397` | #194 adds typed CPU timeout and output-token controls, plus an opt-in read-only compatibility adapter; the older #195 snapshot lacks these |
| `portable/merlin_studio/engine.py` | `b3e79b0b6e8b3bf8a68185d1680aab55c766e09c` | `c7233506253828f30ec971f1b288d23fe2113056` | #194 adds validated settings and bounded adapted-tool follow-up; the older #195 snapshot lacks them |

Blobs above are source identities *at inspection*, not protected latest-head assertions. Re-check exact heads before reconciliation.

## Mandatory integration path

1. Create a dedicated **nondeploying review branch** from a verified common base. Preserve the newer Studio model, engine, tests, UI and `-I -B` subprocess repair from #194. Do not overwrite them with older overlapping copies.
2. Bring over **only the reviewed additive release-evidence functionality** from #195: `python/merlin_release_gate.py`, its tests, orchestration entrypoint and workflow. Keep negative identity, digest, hardlink, path and source-pin tests. Re-evaluate any existing overlap rather than blanket copying historical evidence.
3. Reconcile #193's authorized public-browser implementation as a separate dependency. No changed pathname overlap is **not** proof of import/ABI/security compatibility.
4. Run exact-revision GitLab `release_evidence`, `studio_budget`, `portable_zip`, and the relevant native OCI model/browser suites on **the same integrated source revision**. Keep all failures, source/adaptor identities, artifact hashes and reviewer decisions.
5. Independently review security, source/third-party licensing, operator isolation, credentials, release provenance, signed artifacts, rollback and user route before deciding whether to take draft status off. All three drafts remain unmerged until their dependencies and release gates close.

## Current scope and falsifiers

This report inspected changed-path inventories and **eight selected current code files**, not every PR diff or private document. Its collision count is factual for the inspected PR states; its proposed integration order is a risk-minimizing plan, not a proven merge result. A change to any selected head invalidates the corresponding blob comparison. Tests on separate branch revisions do not establish integrated-release readiness.

**Skeptical Scientist:** n-ality is used to separate file identity, runtime behavior, permission, evidence and release authority. Simplex is not applicable to Boolean merge gates; continuum latency modeling remains deferred; fuzzy inference cannot override source/authorization failures. The strongest alternative explanation is that Git's automatic merge may preserve nonconflicting lines; test this on a review branch rather than assuming 197 conflicts. Record real conflicts, test failures and unexpectedly shared behaviors before promotion.
