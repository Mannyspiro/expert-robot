# Atlas v2.1 — NOAA CO₂ cross-method measurement check

**Status: LOCAL NUMERICAL ANALYSIS ONLY — NOT QUALIFIED IN THIS REPOSITORY**

The noncommercial Human Knowledge Atlas v2.1 repository contains a reproducible comparison of two NOAA Mauna Loa CO₂ observational streams: monthly flask sampling and quasi-continuous in-situ monthly data (2018–2022). From 60 flask months and 59 valid in-situ months, 59 calendar-month pairs were compared; December 2022 in-situ is excluded as a NOAA missing-value sentinel.

- Mean flask minus in-situ = **−0.0371186441 ppm**
- Mean absolute difference = **0.1818644068 ppm**
- Root-mean-square difference = **0.2359079108 ppm**
- Monthly-level Pearson r = **0.9982000448** (trend/seasonality confounding; do NOT interpret as instrument calibration validation)
- Year-specific mean differences change sign: 2018 +0.140; 2019 −0.0558; 2020 −0.155; 2021 −0.1075; 2022 −0.0045 ppm (11 matched months).
- Separate NumPy and Decimal calculations reproduce principal paired-difference summaries; 16 local integrity/schema/adversarial software checks passed.
- Year-block bootstrap uncertainty is exploratory with only 5 years; bias range is NOT a definitive accuracy certificate.

**Data origins / usage rights**

- [NOAA GML in-situ monthly record](https://gml.noaa.gov/aftp/data/trace_gases/co2/in-situ/surface/txt/co2_mlo_surface-insitu_1_ccgg_MonthlyData.txt)
- [NOAA GML flask monthly record](https://gml.noaa.gov/aftp/data/trace_gases/co2/flask/surface/txt/co2_mlo_surface-flask_1_ccgg_month.txt)
- [NOAA Mauna Loa history and 2022 site interruption](https://gml.noaa.gov/ccgg/trends/)

NOAA identifies source measurements as **CC0-1.0**. The extract was manually transcribed from web-visible official text because direct dataset downloads were unavailable. Its local SHA-256 fingerprint does NOT authenticate the complete upstream files. Review original raw files, revision metadata and calibration conventions before greater evidentiary promotion.

**Independence warning:** Both series originate at NOAA and share laboratory/calibration lineage. This is a cross-technique consistency observation, **not independent-laboratory replication**, external physics verification, climate causality, or a new global CO₂ estimate.

**Project boundary:** The Atlas exports an optional task using the existing fail-closed `atlas.bridge.v1` schema. `status=PROPOSED_ONLY`, `network=NONE`, `privileges=NONE`, and `qualification=MUST_REVERIFY_AT_PINNED_TARGET` remain mandatory. This note does not authorize cloud computation, modify generation promotion rules, or certify Lean/CACE outcomes.

**Concrete next experiments**
1. Formalize `abs(mean d) <= mean(abs d)` in pinned Lean without `sorry` and audit permitted axioms and theorem dependency extraction.
2. Numerically certify interval bounds on the paired-data statistic or an explicitly stated PDE toy model, with genuine CACE solver/residual outputs before calling it a certificate.
3. Run blinded temporal hold-out and seasonal-sensitivity comparisons, and compare independently administered NOAA/Scripps measurements only after rights and common calibrations are checked.
4. Keep the demonstrated bias metrics in `REPRODUCED_NUMERICALLY` and any empirical or theoretical conclusions quarantined pending their actual verifier.

The complete Atlas v2.1 ZIP is distributed separately; do not check answer keys, cloud credentials, or large media into this repository.
