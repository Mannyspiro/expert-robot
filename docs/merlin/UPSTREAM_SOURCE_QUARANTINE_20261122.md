# Merlin optional source quarantine: Graft and OpenSandbox (2026-11-22)

**Classification:** actual immutable-upstream source audit, not verified production secrets or native execution. The source review is attached to [draft PR #222](https://github.com/Mannyspiro/expert-robot/pull/222), dependent on [integrated PR #204](https://github.com/Mannyspiro/expert-robot/pull/204). No production source promotion or rights clearance is implied.

## Four upstream scans were completed

After correcting the fail-fast source audit to preserve other independent outcomes, [GitHub Actions run 45110396974](https://github.com/Mannyspiro/expert-robot/actions/runs/45110396974) tested actual pinned checkouts. Its original [metadata-only artifact 14789580743](https://github.com/Mannyspiro/expert-robot/actions/runs/45110396974/artifacts/14789580743) records four per-source reports and hashes. Matched credential-pattern bytes are intentionally absent.

| Source and immutable revision | Tracked paths | Selected-pattern findings | Omitted paths | Gate |
| --- | ---: | ---: | ---: | --- |
| AirLLM `7e2e8cfe2810dc0559461504f6ba5c0ece960ba8` | 107 | 0 | 0 | Pattern scan passed within selected rules |
| OpenBot `019b4c65f488af06ce1a1cfb741cd825129a4c1a` | 84 | 0 | 0 | Pattern scan passed within selected rules |
| OpenSandbox `2ff37a988e4df129babaa6f07bb616394ef94086` | 3,457 | 1 | 1 | **Failed closed** |
| Graft `c77155dcac2d7988fa27268c5ea78c23b651d5ab` | 1,751 | 7 | 39 | **Failed closed** |

Graft's metadata-only findings were in these source locations:

- `apps/server/src/database.integration.test.ts`: one `openai_api` pattern
- `packages/core/src/acquire-job/redaction.test.ts`: one `private_key` pattern
- `packages/env/src/schema.test.ts`: two `private_key` patterns
- `packages/evals/src/github-vendor.ts`: one `github_classic` pattern (**non-test filename; review carefully**)
- `packages/mcp/src/answer-ask.test.ts`: one `openai_api` pattern
- `packages/stock-build/src/build.test.ts`: one `github_classic` pattern

The 39 Graft omissions were principally tracked symlinks under `.claude/skills/` and `CLAUDE.md`. The scanner did not dereference them or pretend to cover them. The single OpenSandbox finding is a localhost-key fixture documented as test-only by its pinned upstream README; its `server/CLAUDE.md` symlink remains unexamined. **A pattern match is not proof of a live credential, but none of these matches are cleared.**

## Fixed source-export boundary

The earlier optional OpenSandbox/Graft workflow generated a source ZIP even when the independently run source scanner had failed. That is an avoidable defect class: a source transfer cannot be qualified by unrelated protocol-unit success. The revised workflow deliberately **does not package or upload the raw OpenSandbox or Graft upstream trees**. It uploads only the exact Gitlink commit identities, fixed adapter source hashes, parent commit and an explicit `source_review_status=blocked` policy record. An additional negative check requires only four small metadata files and no source bundle.

AirLLM/OpenBot retain their independently passing original-source checks. Graft remains **research-only** (no automatic acquired tools) and Z.ai remains opt-in with no live cloud credentials or charges in this review. Existing source ZIPs from historical workflow runs remain historical artifacts and are not relabeled as cleared. The new source export guard applies only to later exact-source workflow executions.

This protects package provenance but does **not** close the actual upstream security audit. Before source redistribution or promotion, independently verify each suspicious fixture/token context, confirm package and runtime code paths cannot use public test keys, validate every symlink alias without escaping the source tree, review licenses and transitive dependencies, and rerun the exact source scanner. No suppression or implicit approval is introduced. Native kernel isolation, real model quality and release authority remain separate hard gates.
