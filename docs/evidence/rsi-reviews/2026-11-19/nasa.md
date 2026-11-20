# NASA interchange and meshing follow-up

| Source | Software terms | Patent or licensing status | Verified Merlin evidence |
| --- | --- | --- | --- |
| [LASP cdflib 1.3.16](https://github.com/lasp/cdflib/releases/tag/1.3.16), cf7553fe93c0684ae461fffb1df0a0b9daa23219 | MIT at tagged source | Separate patent review outside this component trial | November 18 synthetic EPOCH16 exact round-trip scored 2/10 on release and 10/10 with the isolated repair. The repair matches the mechanism of [87f2980](https://github.com/lasp/cdflib/commit/87f2980f3f2e55d5b0429d458e6417115e90d514). No new release or default-branch delta observed in this window. |
| [NASA SPDF CDF](https://cdf.gsfc.nasa.gov/) | [NASA redistribution and modification notice](https://cdf.gsfc.nasa.gov/html/CDF_copyright.html) | Separate NASA notice, patent status unassessed | Prior bundled native library 3.9.1 independently recovered both repaired records. Current site has a separate newer release; that release was not exercised. |
| [NASA refine, 1563f71](https://github.com/nasa/refine/commit/1563f71f224d59c8712e2181369ff93440957b0f) | See pinned repository terms before integration | Independent patent status unassessed | Default-branch delta query was empty. No native mesh run in this review. |
| [NASA GridEx LAR-16423-1](https://software.nasa.gov/software/LAR-16423-1) | Catalog shows U.S. Release Only. No license grant obtained. | Separate from patent licensing | Catalog entry screened for CAD meshing relevance. |
| [NASA CBAERO TOP2-254](https://technology.nasa.gov/patent/TOP2-254) | No software license from the patent entry | Prior review recorded Patent Pending. Today's direct listing lookup returned 404, so current status is unverified. No patent license obtained. | No integration evidence. |
