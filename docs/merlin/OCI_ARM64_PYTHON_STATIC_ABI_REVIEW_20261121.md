# Merlin OCI ARM64 Python 3.11 static ABI review — 21 November 2026

**Status: measured archive inspection, native compatibility not qualified.** No interpreter, library, or model was installed, imported, activated or executed on the OCI host in this review.

The next real-model acceptance gate is currently blocked because fixed native host interpreter probes saw Python 3.9.25, below Studio's Python 3.10 minimum (CACE Actions run [44985478470](https://github.com/morganaspim/Cace-app/actions/runs/44985478470)). A separate ARM64 Python 3.11.18 archive was acquired earlier in CACE run [44960327067](https://github.com/morganaspim/Cace-app/actions/runs/44960327067); its original static parser rejected valid implicit tar directories. The stronger repaired CACE parser passed native fixture run [44962547217](https://github.com/morganaspim/Cace-app/actions/runs/44962547217), **101 checks** including 35 Python archive controls.

## Verified original archive and ELF observations

- Official pinned CPython 3.11.18 aarch64 GNU archive, release `20261110`; size **49,469,868 bytes**, SHA256 **`623a370be4489d8c35c7a274be02f3007a030618cda29025780beb416c6c8861`**, independently rehashed from the archived acquisition artifact.
- Retained original tar: **4,949 entries** (3,900 regular-file inventory records plus 1,049 symlinks); no explicit directory headers. The repaired CACE parser derives 255 logical parent directories and retains that derivation separately from actual archive members.
- **10 observed ELF files**, all reported AArch64. The executable `python/bin/python3.11` has SHA256 `6cfad927461ace659b09716fad2efa828c6a4b084b7be8181c3982a9f36f464c`, ELF interpreter `/lib/ld-linux-aarch64.so.1`, and RPATH `$ORIGIN/../lib`.
- Referenced library names absent from the tar's complete file/symlink basenames: `ld-linux-aarch64.so.1`, `libc.so.6`, `libcrypt.so.1`, `libdl.so.2`, `libgcc_s.so.1`, `libm.so.6`, `libpthread.so.0`, `librt.so.1`, `libutil.so.1`. These are **host/library checks to perform**; absence from the archive does not mean absence on the host.
- Optional `_crypt.cpython-311-aarch64-linux-gnu.so` references **`libcrypt.so.1`**, which was not bundled. A missing optional `_crypt` dependency does not necessarily prevent Studio's core imports.
- Tcl/Tk libraries include absolute RUNPATHs `/tools/deps/lib`; investigate if those optional components are used, rather than assuming deployment paths are valid.

The original CACE archive bytes, receipt and ELF observation records were read; no archive member was executed. Local derived report SHA256 **`8febfdc79ca1b95438925a155c6aedb054fb682e4e97b794b2e0f7dc180ba359`**. It has separately named fields for archive measurements, host dependency unknowns, execution flags, and promotion authority.

## Next exact acceptance gate

Before any new isolated interpreter installation, require a separate reviewed, rollbackable native operation, including: fixed destination and absent-only discovery link; rehashing original archive bytes; full member/link/permission/notice checks; fresh root-owned path/loader/library identity; native ABI/symbol compatibility checks; native unprivileged SSL, sqlite3, multiprocessing, and launch probes. Keep system Python 3.9 and the model provider unchanged. If `libcrypt.so.1` or another library is missing, report an unresolved dependency without installing a substitute automatically.

Only a verified supported runtime can unblock the **separate** fixed two-request real-model acceptance. Passing static ELF checks never means a model inference, scientific research qualification, or full production release has occurred.

This is an append-only note under `MERLIN-PRODUCTION-MASTER-20261117` v6. No master task is marked complete.