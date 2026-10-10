# Atlas v2.2 — NOAA/Scripps measurement-audit handoff (documentation only)

**Qualification state: PROPOSED_ONLY. No cross-laboratory replication was executed.**

## Local completed analysis

The Atlas spreadsheet release v2.2 re-analyzes the inherited *curated* NOAA monthly flask/in-situ CO₂ series at Mauna Loa for 2018–2022 (59 valid pairs; December 2022 in-situ missing). The complete original NOAA file bytes have not been retrieved in the Atlas session, so these are local numerical checks on v2.1 manually transcribed rows.

- Overall signed flask minus in-situ bias **−0.037119 ppm**, MAE **0.181864 ppm**, RMSE **0.235908 ppm**.
- Before April 2019 (15 months): **+0.092667 ppm**; April 2019 and afterward (44 months): **−0.081364 ppm**.
- A fixed bias correction fit only on 2018–2020 (36 months, estimated bias −0.023611 ppm) reduced 2021–2022 holdout MAE (23 months) **0.170435 → 0.163249 ppm**. This marginal descriptive improvement is not an accredited calibration.
- The split coincides with an instrument change NOAA documents in April 2019, but the design does not establish causal attribution.
- Integer-hundredths versus float computation agrees; **19 local software tests passed**. Exploratory year-block bootstrap uses only five yearly blocks.

## External institutional comparison (NOT recomputed)

NOAA's primary measurement-methods documentation reports an average monthly Scripps/NOAA difference of **0.07 ppm for 1974–2019**, from independent measurement programs at the same observatory. Do not compare this as an equivalent, same-period metric with the v2.2 NOAA/NOAA difference.

Scripps Mauna Loa CO₂ data are **CC BY 4.0**; retain attribution to the Scripps Institution of Oceanography, UC San Diego. The original Scripps CSV download failed in the Atlas session, so **zero matched Scripps months were calculated**. An offline parser exists in the Atlas ZIP and requires actual locally supplied original source files, excludes interpolated NOAA months and Scripps filled/fit values, records SHA-256 hashes, and labels output exploratory until comparability review.

Sources:
- https://gml.noaa.gov/ccgg/about/co2_measurements.html
- https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.txt
- https://scrippsco2.ucsd.edu/data/atmospheric-co2-data/sampling-station-records/mauna-loa-observatory-hawaii/

## Scoped follow-up

- **SGK:** formalize the triangle inequality for the mean of finitely many signed differences, through the pinned Lean kernel with no sorry and audited axioms; no proof claimed.
- **CACE:** construct a genuinely verified numerical toy-model residual bound and attach traceable execution artifacts; no existing certificate claimed.
- **Expert Robot:** run pre-registered train/holdout and seasonal ablations once actual raw data are authenticated, maintain identical/reduced authority and qualification gates.

Keep data-only Atlas work packages untrusted; never auto-promote results from external JSON, and never grant compute, credential, network, or filesystem authority based on these notes. The workbook and its CSV/scripts are distributed in a separate v2.2 ZIP release. No hidden keys or media assets in this document.
