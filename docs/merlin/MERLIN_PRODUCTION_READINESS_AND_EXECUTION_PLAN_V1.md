# Merlin production-readiness and execution plan

Snapshot: 2026-11-05
Status: integrated development build; production readiness is not established.
Current implementation PR: Mannyspiro/expert-robot #82, draft and unmerged.
Operating invariant: capability grows; authority never expands.

This is the cross-chat implementation handoff for Merlin, Expert Robot, Hermes, Avrea, CACE, Lean, Titan/PQC, Engineering IR/CAD, ngspice and the read-only HUD. It is a navigation/status document, not execution or qualification evidence. Always re-query exact live refs and runs before acting.

## Non-negotiable execution policy

- No merge, deploy, production promotion, canonical overwrite, force-push, deletion or garbage collection without the applicable explicit approval.
- Workers receive execution-only capabilities, bounded resources, active MCFC leases and task-scoped approval. They never receive proof-promotion, merge or deployment authority.
- Restore into unique quarantine paths. A rollback is a new versioned CAS operation, never destructive history mutation.
- A hash or signature establishes identity/provenance, not mathematical truth or cryptographic security.
- PASS, FAIL, NOT_RUN, STALE and INCONCLUSIVE remain distinct. Missing logs, absent jobs and skipped verifiers are not PASS.
- Prefer already-connected/free services and the existing Avrea/OCI infrastructure. Do not introduce a paid service or card trial as a prerequisite.
- Every attempted PR must have an exact-head test run, preserved stdout/stderr, command exit codes, a machine-readable manifest and a retained artifact. If no job starts, record not_started/no_job_records; do not invent a test result. Any head change requires fresh evidence.

## Current exact evidence

### Expert Robot / Merlin PR #82

- Branch: feat/merlin-preservation-implementation-p0p1-20261105
- Latest verified head at this snapshot: 8f8ce9375af1a7e31881ebd5eb1c84fde14f6ae8
- Exact-head evidence run: https://github.com/Mannyspiro/expert-robot/actions/runs/42108300060
- Result: dependency installation exit 0; python -m compileall -q python tests exit 0; python -m unittest discover -s tests -v ran 481 tests, all passed, exit 0.
- Retained artifact: https://github.com/Mannyspiro/expert-robot/actions/runs/42108300060/artifacts/13452423539, SHA-256 f861af0fa0d9624b77f71d49459b2295ccedadc8e6f810fce96c8100c542202e, 30-day retention.
- This qualifies the current Python baseline suite only. It does not qualify live Avrea execution, CACE signer identity, OCI worker operation, Lean dispatch, CAD/ngspice E2E or deployment.
- PR #82 remains draft/unmerged. The PR includes 116 commits relative to its base and 25 changed paths at this snapshot; inspect the actual diff before any promotion.

### Titan ACVP run and independent CACE bundle check

Avrea-hosted ACVP projection-vector run:
- Repository: Mannyspiro/expert-robot; branch feat/titan-pqc-foundation-20261105; source commit 8e40cb034864f80e58aef7602c4cc4dd1e41ed57.
- Run: https://github.com/Mannyspiro/expert-robot/actions/runs/42090360334, completed success.
- Pinned provider: liboqs 0.16.0, commit 5a1a854b0dc9f2141bdc771c555ee60c37950183.
- Pinned Python binding: liboqs-python 0.16.0.2, commit 64c76ad0a80d6c69f2003219eb27b253782a3d68.
- Vector source: NIST ACVP-Server tag v1.1.0.41, commit b121fee031dc65d32c96f4109a42a10dacbe2076.
- Test log: 54 passed, 1395 skipped; selected suites: ML-KEM/FIPS 203 9/9, ML-DSA/FIPS 204 9/9, SLH-DSA/FIPS 205 36/36, zero failures. These are selected ACVP projection-vector tests, not FIPS 140 module validation or a complete implementation certification.
- Artifact: https://github.com/Mannyspiro/expert-robot/actions/runs/42090360334/artifacts/13445845802, SHA-256 0cd2040e9a426079bda9311937e55da9ae8b57d832908ff42f2e2c41c8d02eb6.

Independent CACE archive/bundle verification:
- CACE repository: morganaspim/Cace-app; run https://github.com/morganaspim/Cace-app/actions/runs/42091465065, completed success on cace-oci-a1.
- CACE source commit: 67d45ec9f040788d86d4368f3512c75b5a005376.
- CACE independently reconstituted the Avrea archive and verified the original archive digest plus four extracted artifact digests. Its evidence says cace_bundle_verification=pass, qualification_status=research_only, signature_status=not_checked, proof_effect=none, promotion_authority=false.
- Artifact: https://github.com/morganaspim/Cace-app/actions/runs/42091465065/artifacts/13443664931, SHA-256 b1035510ed783fa0cf049141f9b16adbc687ef37f01963abbbe741cd85b8a352.
- This is actual independent artifact-bundle rehash evidence. It is not yet an ML-DSA signed receipt and is not proof of cryptographic or mathematical correctness.

### CACE ML-DSA v2 feature branch

- Repository: morganaspim/Cace-app.
- Branch: feat/titan-mldsa-attestation-v2-20261105.
- Latest observed branch head: deb022c0966f015d7aa4656cb24c28ef586fe151.
- No open PR was found for this branch at the snapshot.
- The branch contains additive cace-signed-attestation-v2 ML-DSA-65 code, schema, pqc-keygen, pqc-sign, and pqc-verify CLI paths, plus tests over the actual Avrea archive. Ed25519 v1 remains unchanged.
- Run 42092942992 installed the pinned native provider and Python binding, but the test job failed. Its retained manifest records test exit 1. The branch handoff attributes the earlier failure to provider informational stdout contaminating JSON parsing; code was changed to redirect provider chatter to stderr.
- Later run 42093924533 failed on commit ae903c7829fde3da35ab3cdecb823d291f12e190; the Jobs API returned a job with no step records, the log endpoint returned 404, and no artifact was present. The latest branch head deb022c is a documentation-only follow-up and did not trigger the workflow path filter.
- The branch handoff reports subsequent OCI attempts blocked by disk exhaustion on cace-oci-a1. Do not infer that the latest code has passed ML-DSA receipt tests.
- Remaining: restore runner disk capacity through a reviewed, non-destructive inventory; rerun the exact branch head; capture full stdout/stderr and the signed receipt; verify with a pinned trusted verifier/key ID; independently review the profile; test against a second vetted implementation; define key custody/rotation/revocation. Do not put private signer keys in Git or CI artifacts.

## Architecture and readiness gates

| Area | Existing implementation | Production acceptance still required |
|---|---|---|
| Project/artifact registry | SQLite content-addressed blobs, immutable version history, recovery points, CAS heads, migration checks | Migration/rollback drills against copied legacy DBs; concurrency/fault injection on real supported storage; backup/restore and independent rehash |
| Preservation/recovery | Git/ZIP/registry recovery adapters, tree manifests, change manifests, quarantine restore | Full first-parent history and untracked/ignored inventory on actual runner roots; repeatable disaster-recovery drill; signed restore receipts |
| Hermes | Durable SQLite outbox, leases, idempotency, retries, acknowledgements, repair supervisor | Real publisher/consumer roundtrip; crash between claim/ack; retry/dead-letter; restart recovery; real isolated worker receipt |
| MCFC | Resource-budget and lease validator interfaces | Durable lease authority, expiry/revocation tests, concurrency limits and no-dispatch-after-expiry on the actual scheduler |
| Avrea | Injected dispatch/collect transport with approval, lease, image/tool identity and artifact hash gates | Actual Avrea job from Merlin, exact worker image/tool versions, exit status, retained output and independently verifiable dispatch/result receipts |
| CACE | Injected verification transport; receipt identity/subject fields and content hash checks | Replace hash-only receipt acceptance with cryptographic signature verification; pin verifier identity/key; verify actual subject bytes, bundle, repo and commit; record key status/revocation; CACE signature_status=verified |
| ML-DSA/Titan | Structural protocol model; separate ACVP vector run; CACE bundle rehash; additive ML-DSA-65 branch | Complete exact-head CACE receipt test on OCI; signed receipt roundtrip; trusted key pin; second implementation review; FIPS 140 claims remain prohibited unless separately validated |
| Hermes-to-Lean | Existing proof/theorem dispatch components and CACE formal boundary | Trace the actual dispatch boundary; pin Lean/Mathlib/source commit; retain full build/axiom logs; bind theorem, assumptions, axiom dependencies and artifact; CACE independently verifies exact evidence |
| Engineering IR/CAD | Typed geometry, coordinate-frame, parts/nets, connectivity and netlist contracts; ngspice unit-level tests | FreeCAD import/export roundtrip; exact engineering-IR digest; netlist generation; actual ngspice binary/version, deck, logs and deterministic results |
| Research | OpenAlex public metadata and Titan protocol structural vectors | Source/license provenance; explicit hypotheses; reproducible numerical/experimental results; provider/API constraints; distinguish simulation from public quantum hardware execution |
| HUD | Read-only event projector, CACE/Avrea/recovery projections and WSGI routes | Durable event feed, restart replay, authentication, pagination/retention, stale/out-of-order handling; no control/promotion actions |
| Service/deployment | Python core and API/UI integration points | Threat-model review, authenticated API/session layer, isolated proof/worker services, packaging/upgrade/rollback, supported OS matrix, observability and restore drill |

## Ranked build sequence

### P0 — establish canonical reproducible runtime
1. Keep PR #82 draft while the exact-head Python baseline remains green.
2. Establish a single typed capability registry and canonical project/artifact IDs shared by Merlin, Hermes and CACE.
3. Add signed, exact-commit Git receipts; do not trust caller-supplied SHA strings alone.
4. Make run manifests include exact commit, command, tool versions, environment, timestamps, exit status, stdout/stderr digests and output artifact digests.

### P1 — complete the execution loop
1. Wire Hermes event outbox to a real publisher and durable acknowledgement consumer.
2. Wire MCFC lease issue/renew/expire/revoke into the dispatch boundary.
3. Dispatch one minimal Avrea job from Merlin, collect exact result bytes and prove a full roundtrip.
4. Keep every repair result in quarantine until CACE verification and separate human approval.

### P2 — signed CACE evidence
1. Treat the CACE ML-DSA v2 feature branch as experimental until a new exact-head workflow succeeds and a draft PR is reviewed.
2. Add a Merlin-side verifier that invokes the pinned CACE verification interface and checks the complete signed statement: verifier ID, key ID, bundle digest, repository, commit, artifact digest, artifact kind/schema, run ID, provider/vector commits and scope.
3. Reject unknown keys, wrong subjects, wrong commits, replayed/stale receipts, unsupported schemas, invalid signatures and missing revocation/trust state.
4. Preserve signature_status=not_checked as not verified; never promote it to pass.

### P3 — Hermes-to-Lean and proof qualification
1. Identify the real Hermes-to-Lean dispatch function and remove any shadow/duplicate path.
2. Bind every job to exact Lean toolchain, Mathlib commit, source commit, target theorem, assumptions, axiom audit and output artifact.
3. Run one low-cost conditional theorem first; keep unresolved UFT residuals as explicit assumptions/obligations.
4. CACE independently rehashes and verifies the exact proof artifact and receipt. Provenance signatures never replace Lean kernel checking.

### P4 — engineering and simulation
1. Complete FreeCAD file import and conversion into typed Engineering IR.
2. Validate units, coordinate frames, component identity, pins and connectivity.
3. Generate deterministic SPICE netlists from IR.
4. Execute a small passive circuit with a pinned ngspice version; retain deck, binary/tool version, logs and results.
5. Only then expand to MCFC wiring, more complex assemblies and CAD automation.

### P5 — read-only observability
1. Consume durable outbox events into a replayable read model.
2. Project task, worker, resource, artifact, recovery, CACE and Lean verification states.
3. Add authentication and bounded query interfaces before exposure.
4. Keep all controls out of the HUD; it is not an authority surface.

### P6 — research and provider integrations
- Public quantum APIs/simulators are optional research backends after typed provider adapters, resource caps and provenance are stable. Clearly distinguish simulator results from actual hardware jobs.
- Titan FIPS 203/204/205 vectors remain a separate cryptographic qualification stream; no custom cipher or hybrid combiner enters production.
- UiPath may be integrated as an optional workflow adapter for both Windows Desktop and Studio Web after the canonical API/capability contracts stabilize. It must not become part of the trusted scientific core.

### P7 — production candidate
- Repeat clean install and upgrade/rollback on supported Windows and Linux environments.
- Run full unit/integration/E2E tests and independent provider tests.
- Complete secrets custody, key rotation/revocation, least privilege, authentication, backup/restore, incident logs and resource limits.
- Verify no automatic authority expansion, merge, deployment or canonical mutation.
- Require exact-head CI artifacts and independent review before a separately approved release.

## Definition of production-ready

Merlin is not production-ready until the canonical data model, durable orchestration, actual Avrea worker roundtrip, signed CACE verification, Lean qualification, CAD/ngspice execution, replayable read-only HUD, security/packaging, backup/restore and exact-head evidence are all demonstrated on the same pinned release candidate. A green Python unit suite is necessary but not sufficient.
