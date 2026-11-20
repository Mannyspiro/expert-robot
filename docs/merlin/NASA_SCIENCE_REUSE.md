# Public scientific components for Merlin

The first integration uses OpenMDAO to normalize measurement units before Merlin evaluates a prediction. The remaining candidates address scientific data exchange, mesh adaptation and instrument measurement. Each has a distinct acceptance test.

| Priority | Candidate | Decision and evidence |
|---|---|---|
| 1 | NASA OpenMDAO | Use the optional unit adapter for bounded scalar measurements. Convert absolute temperature centers with their offsets and scale uncertainty widths separately. Retain the existing comparator. |
| 2 | NASA Common Data Format | The optional CDFlib trial preserved 4,096 synthetic samples, units and missing-data masks. Compressed storage fell from 241,453 to 35,430 bytes on this regular fixture. NASA CDF 3.9.1 independently read both outputs and passed all 24 checks per file. [Receipt](../evidence/nasa-cdf-roundtrip-20261118.json) |
| 3 | NASA refine | Compare an adapted triangular mesh and a uniform mesh at a common vertex budget. Check declared units, element orientation and interpolation error at independent sample points. |
| 4 | NASA patent 9,264,154 | Revisit this high-dynamic-range measurement concept only against a documented instrument requirement and the applicable licensing terms. NASA lists a licensing route. A published patent is a research reference. |

OpenMDAO 3.45.2 and NASA refine publish Apache-2.0 source. The native NASA CDF distribution has its own terms. The OpenMDAO test profile uses Python 3.12. A separate scientific runtime can call the optional adapter without adding an optimizer to the learning server. [OpenMDAO source](https://github.com/OpenMDAO/OpenMDAO/tree/64175aa55fb541355b2fb279a6bcfde01e17a878) · [Merlin measurement lab](OPENMDAO_MEASUREMENT_LAB_V1.md)

Merlin examined public source windows for these decisions through its existing context bridge. A search scoped to each source reproduced the bytes and digest of the selected passage in all five cases. This establishes where the cited material came from. Software behavior comes from the separate measurements. [NASA software catalog](https://software.nasa.gov/software/LEW-19994-1) · [CDF](https://cdf.gsfc.nasa.gov/) · [CDF terms](https://cdf.gsfc.nasa.gov/html/cdf_copyright.html) · [refine](https://github.com/nasa/refine) · [NASA patent listing](https://technology.nasa.gov/patent/LEW-TOPS-47)
