# Production acceptance checkpoint: bounded research supervisor

Status: **COMPLETE within the synthetic, side-effect-free research scope**.

## Evidence

- Source branch: `research/merlin-xenomath-parallax-loop-20261123`.
- Verified source revision: `2cdee5ebf9883c69d664004a1d6f460bca1fed52`.
- Independent GitLab pipeline: https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3104376720
- Job: `merlin-exact-revision` (ID `18290566926`).
- CI reports 393 Python cases, all 33 native C++ tests passed, including four dedicated `research_supervisor` tests.
- Test: `tests/test_merlin_research_supervisor.py`; implementation: `scripts/merlin_research_supervisor.py`.
- Tested: persistent checkpoint recovery, no repeat of completed synthetic tasks, exclusive lock contention, bounded invocation count, symlink checkpoint rejection.
- The suite records `real_model=false` and `production_qualified=false`.

## Acceptance scope and limits

This closes the **bounded, explicitly invoked, deterministic synthetic supervisor** requirement.
It does **not** qualify autonomous background scheduling, general external exactly-once
operations, side-effectful browser actions, actual trained-model experiments, or
whole-product production readiness. A crash during an uncommitted external
operation can still replay it; such operations require durable operation IDs,
outbox acknowledgement and reconciliation.

## Next gated milestone

1. Obtain approved and hash-pinned GGUF weights and `llama-server` on an authorized runner.
2. Run `real_local_model` with a real generation receipt, then independent artifact review.
3. Run Merlin Studio against the verified model and test an authorized read-only task.
4. Restart Studio and verify persistent conversation and research state.

The original plan remains in force. Do not convert this narrow completion
into a claim that the full Merlin production release is complete.
