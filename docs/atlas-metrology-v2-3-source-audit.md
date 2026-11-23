# Atlas v2.3 — pending independent metrology evidence gate

Status **PROPOSED_ONLY**. This is a noncommercial, spreadsheet-first research note; **not** a formal proof, solver certificate, cross-laboratory replication, or approved dataset promotion.

## Actual work completed
- Web-visible official NOAA 2018–2019 trends values were cross-checked for 24 months against the Atlas v2.2 inherited *NOAA* in-situ data. Mean (inherited minus trends) = **+0.003750 ppm**, MAE = **0.017083 ppm**, max |difference| = **0.060000 ppm**, 8/24 exact values.
- The NOAA trends series applies center-of-month correction, so differences cannot be assumed to be errors. The excerpt is not a SHA-256 authenticated complete original raw file; the inherited comparison data were manually transcribed in v2.1.
- Current Scripps raw-monthly official file now points to `https://keelinglabsites.ucsd.edu/websitedataco2/monthly_in_situ_co2_mlo.csv`, indexed by its official UCSD directory. The old `/assets/data/...` path returns 404. Full raw downloads remained unavailable in this session.
- 16 local fail-closed fixture tests pass (record formats, missing/fit exclusion, duplicate months, 1974 data-lineage boundary, 2022-12–2023-07 relocation, no promotion).

## Sources / attribution
- NOAA: https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.txt
- NOAA methods: https://gml.noaa.gov/ccgg/about/co2_measurements.html
- Scripps directory: https://keelinglabsites.ucsd.edu/websitedataco2/
- Scripps CC BY 4.0 (credit **Scripps Institution of Oceanography at UC San Diego**): https://scrippsco2.ucsd.edu/data/primary-mauna-loa-co2-record/

NOAA trends pre-April 1974 comes from Scripps, therefore these are **not independent lab observations**. Due to the Mauna Loa eruption, NOAA notes Maunakea backup station data from Dec 2022 until July 2023; explicitly exclude that period when measuring same-site agreement.

## Next executable experiment, not yet performed
1. Download the two whole original public monthly files **only** from verified official HTTPS hosts (not user-supplied mirrors), retain whole-file SHA-256, origin URL, release metadata and receipt date.
2. Pair nonimputed, observed same-station months (e.g., 2018-01 to 2022-11). Exclude Scripps fitted/filled columns and NOAA interpolation flags.
3. Check calibration scales, monthly time centering, station operating periods, estimated uncertainty, temporal autocorrelation and institution-level independence.
4. Run a separate verified code path on pinned dependencies; audit evidence and return `EXPLORATORY`, with knowledge promotion and authority change **disabled**.
5. For SGK, kernel-check the mathematical inequality with audited axioms; for CACE, require actual solver residual + validated certificate; for Expert Robot, require preregistered blinded holdout and unchanged-or-less authority.

The complete v2.3 scripts, spreadsheets, and 16 adversarial tests are available in the separate Atlas ZIP, not checked into this repository branch. Do not infer proof qualification from this note.