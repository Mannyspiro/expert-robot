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

## Continuation checkpoint — same day, PR #194

- Previous exact commit `df3eed934361538885aa4d2b546da7de457b9211`: dedicated GitHub Actions test workflow run `44947926672` concluded **failure**; repository CI run `44947926595` concluded **cancelled**. The failed job reported no step summaries and its log retrieval returned BlobNotFound, so the failure mechanism is unknown. Avrea separately reported no available credits.
- Added `.github/workflows/experimental-self-healing.yml` on GitHub-hosted runner. Its actual success has **not** been demonstrated.
- Added in-process RLock around evidence ledger append/verification; this is not multi-process safety and does not provide crash-atomic records.
- Added thread-write, restart-chain, healthy-path, probe-error, rollback-error, verifier-alias and recurrence advisory tests. Current test count: 12; execution pending.
- Added `python/experimental_fault_advisory.py`: a deterministic repeated-fault count with investigation-only advice. It does not diagnose causality, predict future failures or grant repair authority.
- **P3 actual runtime integration remains unimplemented**. The current supervisor still relies on a caller-provided sandbox boolean and callables, not a verified isolation boundary.
- **P4 recovery after process restart remains unproven**. Ledger continuity test alone does not establish resumption of an interrupted recovery transaction.
- **P1 CI remains blocked** until an actual successful job is observed and its logs/exit code retained.
- Do not merge or deploy on the basis of these additions. Next acceptance gate: obtain successful 12-test run, then add multi-process ledger protection and a real isolated C++ runtime fault-injection slice.

## Additional checkpoint — probe failure handling

- At commit `515b79680363594b96c0d88201caadaf96f6f287`, self-healing workflow run `44948272500` completed with failure; general CI `44948272267` cancelled. The self-healing job `136980304997` has no exposed step summaries or log URL. No passing run observed.
- Corrected the supervisor's initial probe-exception path: an unavailable health probe now emits `probe_error` and `escalate` and returns without executing a repair. This avoids modifying a component with an unknown baseline.
- Strengthened the existing probe-exception regression to prohibit `verified_recovery` evidence on that path.
- Verification pending; GitHub checkout from the available container failed because `github.com` DNS resolution was unavailable. Connector read/write is functional, but it is not a Python execution environment.
- Remaining priority is to obtain native test logs/runner execution, then integrate an actual isolated subsystem. No promotion or production release is authorized by this checkpoint.
