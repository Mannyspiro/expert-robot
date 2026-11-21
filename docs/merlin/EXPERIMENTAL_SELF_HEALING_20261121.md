# Experimental self-healing — implementation checkpoint (2026-11-21)

## Scope
This is an isolated, opt-in Python supervisor prototype, **not** a live production integration. It does not invoke shell commands or change credentials, network access, deployment settings or approval policy. Experimental autonomy applies inside a caller-confirmed sandbox only; a boolean flag is not a security boundary and the host must enforce actual isolation.

## Evidence and limitations
- Read main-branch README, Merlin release navigation, browser direction, orchestrator and smoke test via GitHub connector on 2026-11-21.
- New module: `python/experimental_self_healing.py`.
- New regression tests: `tests/test_experimental_self_healing.py`.
- Evidence: append-only hash-linked JSONL with fsync. This detects accidental edits but is not tamper-proof against an attacker who can rewrite the file and hashes; external anchoring is future work.
- **Not yet executed**: native Python tests, fault injection against actual C++ runtime, restart/replay, concurrency, integration or deployment.
- Independent verification here means a separately supplied callable, not an independently isolated evaluator; production requires a distinct trusted verifier and recorded artifact identity.
- Existing release and master-plan documents remain authoritative; this checkpoint does not assert a new production release.

## Ranked next gates
1. Run unit tests on exact branch SHA; capture interpreter version, stdout/stderr, exit code, hashes.
2. Strengthen ledger with exclusive writer locking, corruption recovery, schema/version, and external receipt anchoring.
3. Add supervisor to one actual sandboxed C++ subsystem behind a feature flag; validate crash, stall, probe timeout, repeated fault and rollback.
4. Test persistence after restart and verify a separate independent evaluator cannot be replaced by a candidate.
5. Run repository native CI, compare with baseline and request review before any promotion.

## Scientific lenses
- Simplex: deferred; no mixture optimization is necessary for this deterministic recovery gate.
- N-ality: applied conceptually to independent health, repair cost and verification axes; no scalar score overrides authorization.
- Continuum: not applicable to discrete repair transitions; latency distributions deferred until measured.
- Fuzzy: deferred for anomaly triage; never controls Boolean sandbox or promotion gates.

## Known risks
A malicious or buggy caller could lie about sandbox status or supply colluding verifier callbacks. Ledger writes are not concurrency-safe. No real process timeout or watchdog exists yet. These are open defects, not accepted production behavior.
