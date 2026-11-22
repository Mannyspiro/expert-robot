# Merlin multi-track production continuation — 2026-11-21

## Canonical context and scope
- Canonical master plan v6: immutable commit `6d4b5a4a3a5b81210d192554774316c04d2d88ff`, 10 tracks / 45 tasks. This checkpoint does not replace it.
- Current main README and release scope describe a bounded private OCI research runtime and a separate C++ trusted core / Python orchestration. The recorded deployed release is not proof that all master-plan tasks are complete.
- User direction: ChatGPT access excluded; general research browsing and full raw project evidence requested. Do not silently expand credentials or promotion authority.
- This PR remains experimental and draft; no deployment or merge.

## Actual implementation delta
1. Research: `python/merlin_research_browser.py` preserves raw HTTP bytes with SHA-256 receipts and budgets; `tests/test_merlin_research_browser.py` covers successful receipt, URL scheme/credentials/private literals, oversized responses, and private redirects.
2. Runtime: `python/orchestrator.py` rejects responses with a mismatched request ID and bounds shutdown with terminate/kill fallback. `tests/test_orchestrator_protocol.py` provides synthetic protocol cases.
3. Self-healing: existing PR #194 includes recovery transaction markers, escalation on interrupted operations, in-process and POSIX cooperating-process evidence locking, and regression tests.
4. CI: the experimental workflow targets the three exact suites rather than repository-wide discovery.
5. Planning: the release and canonical plan remain linked, with incomplete work visible.

## Measured local evidence
- Local command: `python -m unittest discover -s /mnt/data/merlin_work/tests -v`.
- Runtime: Python 3.13.5, isolated container; initial research test run **2 passed / 2 failed**. Root cause: private literal IP validation was skipped when a mock transport was injected. Corrected with unconditional literal IP check. Second run: **4/4 research tests passed**.
- A separate synthetic orchestrator smoke in local harness passed. The local harness is not an exact checkout of the full repository, so it is not accepted as exact-commit native CI or real C++ runtime validation.
- Previous GitHub Actions self-healing runs failed with unavailable step/log details; Avrea separately reported no credits. The CI root cause remains unknown.
- Current source changes were committed through the authenticated GitHub connector; no live browser retrieval, C++ integration, or OCI host changes were executed.

## Explicit limitations
- HTTP retrieval is not a full browser (no JS, DOM, interactive navigation, session or account login). DNS validation is not a substitute for connecting to a pinned validated address; DNS rebinding and proxy trust remain open. This component must not receive privileged internal network access before transport hardening.
- Receipts are local and not integrated into the canonical ArtifactRef/registry/outbox. They are provisional; do not introduce a competing production truth store.
- No independent evaluator, production promotion, actual host restart, or sustained capacity test was performed.

## Next ranked acceptance gates
1. Run all three exact suites on exact branch SHA; capture job logs, interpreter, exit status and test counts. Fix failures without weakening negative tests.
2. Replace the research HTTP transport with an isolated browser service plus explicit network policy, DNS pinning, redirects and source/citation custody; demonstrate public news/database/GitHub retrieval and restart.
3. Bind self-healing supervisor to one actual isolated runtime process and C++ health contract; demonstrate fault injection, timeout, restart, rollback and independent verifier.
4. Integrate raw retrieval receipts into the existing canonical ArtifactRef/registry and off-host backup, with replay and retention controls.
5. Run baseline/candidate two-coder evaluation under an explicit budget; preserve failed attempts and use separate evaluator identity.
6. Resume CAD/wiring/simulation, mathematics (n-ality, simplex, glyphs, xenomaths), creative design, HUD/Forge and security hardening with domain-specific independent acceptance criteria.

## Research lenses
Simplex deferred (no measured optimization problem yet); n-ality applied as separate integrity/authority/availability axes; continuum deferred until latency observations exist; fuzzy not applicable to Boolean integrity and authorization gates.
