# Scientific interchange review, 2026-11-18

The same two-record EPOCH16 input produced four wrong records in upstream Python cdflib 1.3.16. Its writer decomposed each complex record into separate numbers before the normal encoder. Applying the enclosed MIT patch to an isolated extracted wheel retained seconds and picoseconds as one complex128 until serialization. The upstream November 13 commit implements this mechanism. This patch is a small review artifact for the released wheel, not an installation or a claimed new upstream discovery.

| Item | Pinned identity and terms | Integration evidence |
|---|---|---|
| LASP cdflib | 1.3.16, MIT, Regents of University of Colorado. [PyPI October 21 release and build attestation](https://pypi.org/project/cdflib/1.3.16/) lists commit cf7553fe93c0684ae461fffb1df0a0b9daa23219 and wheel 54d3f525651e9293b65a71b29b6b0b737cfe8e8f2a9191dcb686d261b77fc4f1. [Upstream fix](https://github.com/lasp/cdflib/commit/87f2980f3f2e55d5b0429d458e6417115e90d514) dated Nov 13, 2026. | Bench-tested published wheel and locally patched copy, in separate processes. |
| SpacePy | 0.7.0 Linux x86-64 [PyPI distribution](https://pypi.org/project/spacepy/0.7.0/) hash 61b160bb422e3a85dac2e5ee163d3f01112524d7f30da1d64ae839ebad7cbd27. Distribution includes the Triad National Security SpacePy license and bundled component notices. | Used its raw variable interface with the bundled NASA native reader. |
| NASA SPDF native CDF | [NASA lists 3.9.2, May 2026](https://cdf.gsfc.nasa.gov/). Separate [NASA redistribution and modification notice](https://cdf.gsfc.nasa.gov/html/CDF_copyright.html). | Actually exercised bundled 3.9.1 (not 3.9.2), exact shared library hash in native receipts. [NASA TT2000 time semantics](https://cdf.gsfc.nasa.gov/html/time_datatypes.html). |
| NASA GridEx software catalog | [LAR-16423-1](https://software.nasa.gov/software/LAR-16423-1), U.S. Release Only. No software license grant obtained. | Listing reviewed only. |
| NASA Technology Transfer | [CBAERO TOP2-254 / ARC-15819-1](https://technology.nasa.gov/patent/TOP2-254) lists Patent Pending. No patent license obtained, scoped to this entry, without an opinion on freedom to operate. | Listing reviewed only. No code or patent incorporated. |
| NASA refine | [Default-branch revision](https://github.com/nasa/refine/commit/1563f71f224d59c8712e2181369ff93440957b0f), committed 2022-11-17, also in the previous Merlin mesh study. | Apache-2.0 at the pinned revision. No new native mesh experiment this run. |

The GitHub REST default-branch commit queries for lasp/cdflib and nasa/refine both returned empty arrays from Nov 17 00:00 through Nov 18 15:00 UTC. The November 13 change predates this interval and motivates today's synthetic regression. This window check does not cover all branches or unindexed material.

## Reproduction

Use Python with NumPy and the two checksum-verified wheels above. Extract cdflib separately into BASE and CANDIDATE. Keep both outside the production environment. In CANDIDATE apply cdflib-1.3.16-epoch16.patch with patch -p1. The original/patched writer digests and protocol hash are recorded in epoch16-base.json and epoch16-candidate.json. Run epoch16-evaluate.py in fresh Python processes with PYTHONPATH set to each corresponding tree. Run cdf_leap.py with the wheel path; it creates its own temporary original installation. Run native_read.py with each extracted writer tree and the pinned SpacePy wheel to reproduce the independent decoding. Only the local test harnesses and reviewed open-source patch execute; no model proposal, network listener, production data, secret or remote target is used. No third-party binary is redistributed.

The prior Merlin measure_cdf_roundtrip.py ran on both isolated trees. Both plain and gzip numeric/vector/blank fixtures remained exact and the deliberately altered checksum was rejected in each. Results are recorded in old-suite-base.json and old-suite-candidate.json. Timings are single local observations. No package-wide conformance or speed claim follows.

NASA also lists data acquisition technology LEW-TOPS-47, US patent 9,264,154, with an application-to-license route (https://technology.nasa.gov/patent/LEW-TOPS-47). No implementation tested or license acquired. The CBAERO page was inconsistently retrievable during this review.
