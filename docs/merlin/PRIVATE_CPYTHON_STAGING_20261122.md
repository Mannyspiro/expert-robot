# Merlin CPython 3.11 private staging continuation — 2026-11-22

**Scope:** A separately reviewed staging mechanism, not host installation, interpreter startup, Studio validation, model acceptance or release qualification. This evidence supplements canonical Merlin production master v6 (10 tracks, 37 original tasks and eight extensions); no master task is promoted to complete.

## Observations and source identity

- The OCI ARM64 host has existing system Python 3.9.25; Studio requires Python 3.10+. Earlier model acceptance [44985478470](https://github.com/morganaspim/Cace-app/actions/runs/44985478470) stopped before root/provider inspection and made zero model generation requests.
- Read-only host ABI run [44987215821](https://github.com/morganaspim/Cace-app/actions/runs/44987215821): all eight required core host library symbol-version checks were statically observed. Optional `libcrypt.so.1` was absent. Static metadata does not prove dynamic-loader resolution or actual execution.
- Corrected native static archive run [45009078432](https://github.com/morganaspim/Cace-app/actions/runs/45009078432) completed on first attempt against operations commit `cf68aad41c4826548bad080ffaf8fd60358d2f72`. All 35 native synthetic archive controls passed with zero failures/errors/skips. The fixed archive was acquired once, SHA-256 verified, and enumerated into 4,949 archive members, 10 ELF records and 64 notice records. Neither downloaded code nor the interpreter was executed; no installation or model call occurred.
- Verified archive bytes: 49,469,868; SHA-256 `623a370be4489d8c35c7a274be02f3007a030618cda29025780beb416c6c8861`. Decompressed TAR SHA-256: `6675d878150c47cdfab142c218dc2a98ee735ff043247a1e7d770aff4dcfb74b`.
- Entrypoint `python/bin/python3.11`: 56,723,673 bytes; SHA-256 `6cfad927461ace659b09716fad2efa828c6a4b084b7be8181c3982a9f36f464c`. Live archive and executable digests were independently recomputed from original retained artifact [14748604091](https://github.com/morganaspim/Cace-app/actions/runs/45009078432/artifacts/14748604091).
- On a separate Linux x86_64 local container, the new `scripts/merlin_python_private_stage.py` accepted the identical saved archive *as data* and produced a read-only 4,949-member census. With a non-root user and pre-existing UID-owned 0700 scratch parent, a distinct bounded staging run wrote 3,900 regular files and 1,049 symlinks (153,418,201 regular-file bytes), checked the entrypoint hash, then removed the entire temporary staging leaf. No ARM64 binary was executed. This local run is not OCI host acceptance.
- New `tests/test_merlin_python_private_stage.py`: 14/14 cases passed unprivileged with zero skips. Synthetic adversarial cases cover malicious member names, symlink escapes/cycles, hardlinks, special/setid entries, malformed ancestors, source hash mismatch, non-root admission, partial-write fault injection and rollback. Python 3.9 grammar parsing passed locally, but actual CPython 3.9 native test execution remains a separate CI observation.

## Explicit controls and limitations

- A stage requires an existing exact-hash archive, forbids staging as UID0, requires a user-owned mode-0700 parent, writes a new temporary private child, uses conservative file modes, constructs symlinks only after all regular files, and does not launch the interpreter.
- The script does not fetch assets, install packages, change global PATH or system Python, start services, call models, or grant deployment authority. A success receipt explicitly marks `python_startup_verified=false`, `host_system_installation=false`, and `production_qualified=false`.
- The stage directory is not immutable, and same-UID hostile mutation and all possible filesystem races have not been exhaustively tested. Host glibc symbols and a matching file hash do not establish runtime compatibility; optional `_crypt` needs separate testing or an explicit exclusion.
- The exact-revision CI entry now runs these tests through `runuser -u nobody` rather than accepting skipped root-only cases. GitLab pipeline [3099371022](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3099371022) was submitted against source `71e6405a3475eb449d150b961915922edd3e9fb0`; its outcome must be checked separately.

## Ranked next gates

1. Confirm fresh GitLab exact-commit CI result and retain test logs; fix only actual failures on a new exact commit.
2. Perform fixed-source unprivileged OCI private-stage *without interpreter execution*, with isolated output, cleanup, exact source/receipt digests and negative controls. No production host state may change.
3. Independently review the host ABI and the missing optional `libcrypt` behavior. Design a separate explicitly scoped startup-only execution check after stage acceptance; do not infer it from static evidence.
4. With supported interpreter startup and preserved rollback, run Studio's full 111 native cases, package verification, and durable offline/restart user workflow, then the bounded real-model and browser acceptance.
5. Return results to the canonical v6 plan, including rejected approaches, failed/null evidence, residual risks, and actual acceptance before merging or deployment.

## Skeptical-scientist frame

**Hypothesis:** Bounded private staging can remove the Python version blocker without global installation. **Falsifiers:** archive mismatch, path escape, wrong interpreter entrypoint, partial rollback, unexpected service/system change, or failure to run required native Studio tests. **Induction limit:** passing synthetic and one real archive stage does not qualify the OCI application. **N-ality:** retain integrity, compatibility, authority and lifecycle as independent axes. **Simplex/continuum/fuzzy:** not applicable to Boolean release/authorization gates; do not soften missing measurements with a heuristic score. **Bias control:** do not count CI pass as interpreter startup, model quality or production readiness.
