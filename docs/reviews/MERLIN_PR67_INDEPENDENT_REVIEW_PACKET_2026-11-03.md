# Merlin PR #67 — independent review packet

## Purpose
Request a genuinely independent review of the Merlin CPU fabric loader, randomized paired evaluator, telemetry graph HUD, and telemetry test-isolation changes. This packet is evidence for a reviewer, not a review result.

## Repository state
- Repository: Mannyspiro/expert-robot (private)
- Review branch: feat/merlin-hermes-kokoro-qualified-20261102
- PR: #67 (draft; do not merge as part of this review)
- Review base: e311a00fafb0d90fdfec5708e9911efe97c28c5a
- Review head at packet creation: 2b6122862252e0b3544200675eade1ba241354a9
- Earlier runner merge commit: feb641fdcf21410f3442e952675f15677423ed5e
- No promotion or deployment authorized.

## Required reviewer independence
Reviewer must use a separate human or agent identity and a fresh context that does not rely on this implementation conversation. Do not treat another persona in the same model session as independent. Reviewer should fetch the base and head directly, inspect the complete diff, and independently reproduce the commands below. Reviewer must report identity/context, commit inspected, exact commands, environment, results, and findings.

## Review scope
1. python/merlin/cpu_fabric/catalog.py
   - Verify registration streams and hashes without materializing artifact bytes.
   - Verify activation enforces max_artifact_bytes separately from resident budget.
   - Verify one open descriptor is used and the exact snapshot passed to loader is the snapshot that was hashed.
   - Inspect memory peak implications of bytearray allocation, chunk buffer, loader behavior, exception cleanup, and concurrent artifact mutation.
   - Check that callers relying on bytes rather than bytearray remain compatible.
2. python/merlin/cpu_fabric/strategy_eval.py
   - Verify per-seed candidate order randomization is reproducible.
   - Verify paired differences match identical seeds and baseline is explicit.
   - Verify development/held-out seeds are disjoint and held-out outcomes are not used for candidate selection.
   - Assess whether normal-approximation intervals are adequately caveated for small sample sizes.
3. web/merlin_hud.html
   - Verify selected node inspection and explicit edge navigation.
   - Verify no causal relationships are inferred or implied.
   - Verify safe rendering/escaping and empty graph behavior.
4. tests/research/test_merlin_api.py
   - Verify isolated EventStore makes telemetry count test independent of request-boundary runtime telemetry.
5. tests/test_module_catalog.py and tests/test_strategy_eval.py
   - Verify new contracts and failure paths are covered.

## Reproduction commands
Run from repository root with the project Python import layout:
```bash
python3 -m unittest tests.test_module_catalog tests.test_strategy_eval -v
python3 -m unittest discover -s tests/research -v
python3 -m unittest discover -s tests/engineering -v
```
If package discovery does not support dotted test module names, use:
```bash
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_module_catalog.py' -v
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_strategy_eval.py' -v
```

## Existing runner evidence (not equivalent to validation of current head)
Raw log: artifacts/avrea/2026-11-03-run-41675662882/avrea-ci-run-41675662882-job-126055582609.log
Metadata/report: artifacts/avrea/2026-11-03-run-41675662882/README.md
That run used Avrea 8-vCPU AMD EPYC 4585PX / 29 GiB RAM. C++ build and 33 CTest tests passed; research Python tests had one failure because the shared class-level EventStore accumulated HTTP-boundary runtime events (expected 1, observed 23). The test was subsequently isolated in commit f6cb194b4e1114262bdae834c356b31497658e96. The run predates that fix and predates the final catalog corrections. Do not report it as a passing test run for this head.

## Current evidence status
- The initial Avrea run is preserved as a raw log with machine metadata.
- A subsequent Avrea CI run 41676542294 was observed queued after the first catalog correction. Its final status and exact checked-out merge SHA must be added here once available.
- No successful execution of the newly added loader/strategy unit tests is yet established.
- Independent review is pending. Do not mark reviewed/qualified until a separate reviewer submits reproducible findings.

## Non-negotiable project invariant
Capability grows, authority never expands. Evaluation and review are evidence only; no automatic promotion, deployment, merge, or authority expansion.

## CI iteration update
A CI attempt including the new engineering CPU-fabric tests initially failed at import time because the test used `merlin.*` while this repository's runner imports the package as `python.merlin.*`. Commit 55ccfaa9c769bfcce3afe5a1e8885f0f06a9b18e corrected the test imports. The corrected engineering test file must still be executed on Avrea before its result is considered verified.

## Latest bounded Avrea verification
CI run 41677435187 (job 126061727081) completed successfully on the Avrea 8-vCPU AMD EPYC 4585PX runner. CTest passed 33/33; voice contracts 6/6; engineering tests 14/14 including all four new CPU-fabric regression tests; research/API tests 26/26. Raw log and metadata are archived under `artifacts/avrea/2026-11-03-run-41677435187/`. The checked-out merge commit was 9d63bec, merging 731ecef into the PR base. The only post-run change was evidence documentation/log archival; source files in scope were already present in the tested merge commit.

## Independent review status
No PR reviews are currently recorded. The packet is prepared, but a genuinely independent reviewer has not yet submitted a review. Do not describe the code as independently reviewed or qualified.
