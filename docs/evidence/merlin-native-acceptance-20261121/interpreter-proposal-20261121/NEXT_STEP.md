# Proposed next step: one isolated supported interpreter

**Decision now: keep the model request stopped.** Native source validation run
`44955762960` found no supported interpreter in the fixed candidate list. This
document proposes a separate future provisioning operation. It does not extend
the current routes' explicit no-install authority, and nothing described below
has been downloaded, installed or executed on the host. Complete the approved
browser gate before deciding on this proposal.

## 1. What the fresh evidence establishes

The exact native receipts are under
`approved-production-20261121/source-validation-44955762960/artifact/`.
`NATIVE_BLOCKER_REVIEW.json` records their hashes and relevant fields.

| Observation | Consequence |
| --- | --- |
| The 20 controller controls passed with zero failures, errors or skips | The fixed controller ran on the existing administrative Python; this does not qualify the product runtime. |
| `/usr/bin/python3` resolves to root-owned `/usr/bin/python3.9`, version 3.9.25; all fixed 3.10–3.13 candidates are absent; `selected=null` | The supported-interpreter prerequisite failed. Other locations were not searched. |
| Product tests are `not_run`, with 0 of the required 111 executed | There is no native product-suite pass to promote. |
| Model, binary and unit hashes match; service is active/running at PID 2623747 | Ordinary installation identities match the pins. |
| Reading `/proc/2623747/exe` was denied to UID 1000 | Live provider process identity remains unverified. The approved read-only root inspector resolves this separate boundary only after the interpreter/source prerequisites are met. |
| Tokenization and generation counts are both zero | The model budget remains unused; the prepared model request remains on hold. |

The frozen package README, Unix/Windows launchers and package manifest require
Python 3.10 or newer. The native controller additionally probes sqlite3, SSL and
other standard-library imports. A newer interpreter must satisfy that contract;
the absence of an observed Python 3.9 application crash is not evidence that the
contract can be lowered.

## 2. Single proposed distribution

Use the publisher's prebuilt GNU/Linux aarch64 CPython **3.11.18** installation
archive from release **20261110**:

`cpython-3.11.18+20261110-aarch64-unknown-linux-gnu-install_only.tar.gz`

Published SHA256:

`623a370be4489d8c35c7a274be02f3007a030618cda29025780beb416c6c8861`

The [official release listing](https://github.com/astral-sh/python-build-standalone/releases)
publishes that filename and digest. The authoritative GitHub release metadata,
retained unchanged in `PUBLISHER_ASSET_METADATA.json`, identifies release
**441136779**, asset **733710616**, and an exact expected archive size of
**49,469,868 bytes**. This is the publisher-reported size; no downloaded bytes
have been measured here. The listing's rounded display remains 47.2 MB.

The [pinned release](https://github.com/astral-sh/python-build-standalone/releases/tag/20261110)
points to build-repository commit
`9244801782b78e4c4afc5c82a4524aa2101d3298`. `CANDIDATE.json` records the fixed asset
URL, metadata identity and proposed bounds. The archive has not been acquired,
independently hashed or inspected here.

An additional bounded acquisition-route review queried the official workflow
listing for that exact build commit, then inspected the artifact page for its
[Release run 42936121880](https://github.com/astral-sh/python-build-standalone/actions/runs/42936121880).
The listing returned six runs; the inspected Release run returned no Actions
artifacts. The available Actions download tool requires an Actions artifact ID,
so this review established no supported route to the exact pinned release
bytes. The review stopped after those two metadata lookups; other identified
build runs' artifact pages were not inspected. This is a bounded search result,
not a claim that no copy exists elsewhere. The release workflow's recorded
failure does not by itself invalidate the separately published release asset.
`ACQUISITION_ROUTE_REVIEW.json` retains the selected metadata and claim limits.
Local static acquisition was permitted for this review, but no binary was
downloaded or executed and no archive, member, license or ELF facts were measured.
Native host acquisition and provisioning remain outside the current authority.

This version exceeds the existing 3.10 minimum and uses an already listed
versioned candidate path. Its compatibility with Merlin on this host is a
pending measurement, to be established by the unchanged native source gate.

The publisher documents a GNU aarch64 build and recommends GNU builds when
dynamic extension loading is needed. Most such targets require glibc 2.17 or
newer. **Exact ELF loader/dependency requirements and current host compatibility
have not yet been measured.** Python 3.12 and earlier additionally need
`libcrypt.so.1` for the deprecated `crypt` module; do not install that library or
any other dependency automatically if a required check fails.
See the [publisher's runtime requirements](https://docs.astral.sh/python-build-standalone/running/).

## 3. Proposed installation boundary

The future operation would create a root-owned, versioned tree at:

```text
/opt/merlin-studio-runtime/releases/623a370be4489d8c35c7a274be02f3007a030618cda29025780beb416c6c8861/python/
```

After verification, it would create exactly one new discovery entry:

```text
/usr/local/bin/python3.11
  -> /opt/merlin-studio-runtime/releases/623a370be4489d8c35c7a274be02f3007a030618cda29025780beb416c6c8861/python/bin/python3.11
```

The displayed target must be confirmed as the archive's actual versioned
executable before implementation is frozen. `/usr/local/bin/python3.11` is
already a fixed candidate in both source and model controllers; adding this
entry therefore requires no search-path expansion or frozen route change.
The entry must still be absent at activation; any pre-existing file or symlink
causes a stop, never replacement.

Keep `/usr/bin/python3`, `/usr/bin/python3.9`, unversioned `python`/`python3`,
system alternatives, system package databases, global PATH and loader
configuration unchanged. The current system-Python executable hash is
`59acf176bc9571b65545d2d08f9db5271d14855431f9ccafc1239bc81b5a8e8d`.
Create no provider files, users, services or permissions; do not restart or
reconfigure the model provider. Run no fetched executable as root.

This is an isolated additional interpreter, not a replacement system Python.
The proposed versioned entry is a deliberate host write that requires a new
provisioning decision. The current no-install controllers cannot perform it.

## 4. Bounded future transaction to review

1. **Freeze a separate provisioning definition.** Bind the exact archive URL,
   published SHA256, expected version/architecture, destination, absent-only
   entrypoint and rollback paths. Use the existing operations serialization;
   prepare no model request or inference action in this transaction.
2. **Acquire one archive as an unprivileged user.** Proposed ceilings: 64 MiB
   compressed, 180 seconds, at most two redirects, zero retries. Accept only
   the fixed GitHub release asset and its approved HTTPS asset host. Reject a
   digest mismatch, received byte count other than the publisher's expected
   49,469,868 bytes, unexpected origin, incomplete response or size/deadline
   overrun. The 64 MiB ceiling does not replace the exact expected size check.
   Do not execute a convenience installer, uv, pip, ensurepip or a package
   manager.
3. **Inspect before installing.** Record the exact received byte count, member
   inventory, each member's hash/type/mode, all license texts and ELF metadata.
   Proposed extraction ceilings are 512 MiB expanded, 20,000 members and 64 MiB
   per member; these are bounds, not measured sizes. Require a single `python/`
   tree. Reject traversal, duplicate names, device/FIFO entries, sparse files,
   setuid/setgid bits, unsafe hardlinks and links escaping the tree. Permit only
   reviewed relative symlinks whose targets remain inside the release.
4. **Install by verified bytes only.** A separately reviewed root file-operation
   helper must reverify the held archive through a safe descriptor, avoid
   following writable staging paths, create only the new versioned prefix, and
   leave every installed file root-owned and non-writable to group/others.
   Preserve the archive's required layout and notices. Do not copy mutable
   unprivileged staging files on trust.
5. **Probe the final path as UID 1000 before activation.** Require exact version
   3.11.18, Linux aarch64, the expected resolved executable, and successful
   imports of sqlite3, ssl, http.client, multiprocessing and resource. Record
   executable SHA256, ELF loader/dependencies, SQLite/SSL versions and prefix.
   Verify a small SQLite in-memory round trip and standard-library thread/process
   operation without network access. A failure stops; it does not authorize
   dependency installation or a different build.
6. **Activate the absent versioned entry atomically.** Recheck protected system
   Python/provider file identities and service PID/state, then create only the
   fixed `/usr/local/bin/python3.11` link. Record its target and ownership.
   Re-probe that entry as UID 1000 with isolated Python flags. Record a
   provisioning receipt before declaring this new prerequisite satisfied.

The expected compressed size and SHA256 are now known from publisher metadata.
The locally received byte count and SHA256 remain unmeasured because no archive
has been downloaded. The executable hash, member inventory and license-file
hashes are also unknown and must be recorded from the approved artifact. This
document is not an executable installer or a completed provisioning review.

## 5. Licenses and retained notices

The [official CPython 3.11.18 license documentation](https://docs.python.org/3.11/license.html)
identifies the PSF License Agreement and separately licensed incorporated
software. Preserve the supplied PSF and historical notices and all bundled
dependency license texts.

The standalone publisher states that dependencies have varied licenses and
archives contain license texts. Its
[archive documentation](https://docs.astral.sh/python-build-standalone/distributions/)
says `install_only` omits `PYTHON.json` and build artifacts; do not claim that
file is available in this candidate. The exact bundled-license inventory and
its hashes remain uninspected until authorized acquisition. A missing required
notice or an unresolved redistribution condition stops packaging/activation;
no blanket license clearance is claimed here.

## 6. Verification and rollback after a new provisioning decision

After successful provisioning, review its receipt, then submit one new source
validation request using the unchanged frozen route. Require the expected
selected executable identity and all 111 product cases with zero failures,
errors or skips, plus compilation/package verification. Do not rerun the
blocked GitHub attempt or count its 20 controller controls as product tests.

The provider's cross-UID process boundary remains separate. Only after the
interpreter/source gates succeed may the already reviewed model route perform
its fixed before-inspection, tokenization, at most two generation requests and
after-inspection. Its 4,096 requested output-token budget, zero retries and
existing timeouts remain unchanged.

Rollback affects only this new interpreter transaction. Remove the versioned
link only if it still has the exact target created by the transaction. Remove
only the newly created release tree if its recorded identities still match and
no active job is using it; otherwise stop for review. Do not remove a pre-existing
path, follow an unexpected symlink, delete a different release, or touch system
Python/provider state. Keep acquisition, inventory, probe and rollback receipts.
Failed verification before link creation leaves no activated entrypoint.

The next decision is whether to prepare and authorize this separate bounded
provisioning operation after the browser gate finishes. The current model
request remains stopped.
