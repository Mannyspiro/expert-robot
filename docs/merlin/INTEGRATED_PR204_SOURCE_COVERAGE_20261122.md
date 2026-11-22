# Merlin draft PR #204: source-path coverage and exclusions (2026-11-22)

This is a **path identity/source inventory**, not a proof of byte-equivalent merges, clean security review, merge resolution, or model/browser/OCI qualification.

## Bounded comparison

Source: GitHub's changed-file path lists for open draft PRs [#193](https://github.com/Mannyspiro/expert-robot/pull/193), [#194](https://github.com/Mannyspiro/expert-robot/pull/194), [#195](https://github.com/Mannyspiro/expert-robot/pull/195), and integrated draft [#204](https://github.com/Mannyspiro/expert-robot/pull/204).

| PR | Reported changed paths | Also changed in #204 | Changed paths not in #204 | Interpretation |
|---|---:|---:|---:|---|
| #193 public Chromium browser | 489 | 18 | 471 | The 18 source/config/test/docs paths are present; most original native evidence archives and supplemental updates are **not imported** |
| #194 Studio and recovery | 252 | 252 | 0 | All paths overlap but many contents were updated during integrated work; path intersection is not byte equality |
| #195 release evidence | 226 | 203 | 23 | The release-evidence checker and much supporting material overlap; **not all ancillary CI/coordination implementation was imported** |
| #204 integrated draft | 298 | 298 | 0 | This review branch is not a signed release or a merge of all upstream PR history |

The #204 file list contains **201 `docs/evidence/` entries**. These are retained research/test archives rather than automatic authoritative evidence. Their provenance, privacy and secret leakage require independent checking before publication/merge.

## PR #195 paths not included in #204

- `.github/workflows/ci.yml`
- `.github/workflows/merlin-portable-staging.yml`
- `.github/workflows/merlin-runner-diagnostic.yml`
- `ci/gitlab-merlin-exact-revision.yml`
- `docs/engineering/merlin-production-decomposition-20261121.md`
- `docs/evidence/merlin-production-gap-register-20261121.md`
- `docs/evidence/merlin-release-gate-checkpoint-20261121.md`
- `docs/merlin-production-checkpoint-2026-11-21-continuation-2.md`
- `docs/merlin-production-checkpoint-2026-11-21.md`
- `docs/merlin/GITLAB_CI_HANDOFF.md`
- `python/merlin_dependency_math.py`
- `python/merlin_loop_coordinator.py`
- `python/merlin_loop_persistence.py`
- `python/merlin_tool_reframing.py`
- `scripts/diagnose_merlin_clone.sh`
- `tests/test_merlin_dependency_math.py`
- `tests/test_merlin_hybrid_preflight.py`
- `tests/test_merlin_loop_coordinator.py`
- `tests/test_merlin_loop_handoff.py`
- `tests/test_merlin_loop_persistence.py`
- `tests/test_merlin_loop_restore.py`
- `tests/test_merlin_loop_serialization.py`
- `tests/test_merlin_tool_reframing.py`

## PR #193 paths omitted

There are 471 paths absent from #204, predominantly original native browser evidence and plan-update records. The full omitted list is large and remains accessible in PR #193; it has **not been discarded**. The source paths imported into #204 match the original PR #193 path names, not a verified complete source/prior-history equality claim.

## Gates and next reconciliation test

1. Freeze the reviewed SHA and re-evaluate identical source blobs for each overlapping changed code file; identify true content changes and conflicts, not only names.
2. Independently inspect each #204 retained evidence ZIP/archive for sensitive data and qualification claims. A scanner for selected signatures is **not** proof that no secrets exist; retain omissions.
3. Run a protected branch comparison/CI against the actual proposed base, because 171 commits and roughly 296 changed paths can hide integration gaps even when one source revision has passing tests.
4. Review excluded PR #195 modules against the consolidated master plan; import only after individually checking dependencies, not because their PR number is high.
5. Keep #193/#194/#195 and #204 open as drafts until reviewers agree on source ownership, native host proof and rollback, production authorization, and a release-signing identity.

## Authority and uncertainty

No merge, deployment, root-host change, model promotion, or credential read was performed by this path comparison. An overlap count measures file names only. It does not assert identical hashes, absence of conflicts, security correctness, source completeness, actual browser operation, model quality, or production readiness.
